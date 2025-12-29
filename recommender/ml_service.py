import os
from typing import List, Tuple, Dict

import joblib
import pandas as pd
from django.conf import settings

import build_sbm_project as core
from .models import Course, StudentProfile, StudentCourseEnrollment


def model_path() -> str:
    return str(settings.SBM_MODEL_PATH)


def load_model() -> Tuple[object, Dict] | Tuple[None, None]:
    path = model_path()
    if not os.path.exists(path):
        return None, None
    data = joblib.load(path)
    return data.get("model"), data.get("meta", {})


def recommend_for_profile(
    student: StudentProfile,
    taken_codes: List[str],
    taken_grades: Dict[str, int] | None = None,
    top_k: int = 5,
) -> List[Tuple[str, float]]:
    """Будуємо рекомендації для профілю студента на основі збереженої моделі та оцінок."""
    model, _ = load_model()
    if model is None:
        raise RuntimeError("Модель не знайдено. Спершу натренуйте її командою train_sbm_model.")

    taken_set = set(taken_codes)
    taken_grades = taken_grades or {}
    grade_values = [g for g in taken_grades.values() if g is not None]
    overall_avg_grade = (sum(grade_values) / len(grade_values)) if grade_values else None
    interests = {i.strip() for i in (student.interests or "").split(",") if i.strip()}

    df = pd.DataFrame(
        [
            {
                "year": student.year,
                "math_level": student.math_level,
                "prog_level": student.prog_level,
                "ai_level": student.ai_level,
                "soft_level": student.soft_level,
                "interests": student.interests,
            }
        ]
    )
    X = core.encode_features(df)
    proba = model.predict_proba(X)[0]
    labels = model.classes_

    courses = {c.code: c for c in Course.objects.all()}
    prereq_map = {c.code: set(c.prerequisites.values_list("code", flat=True)) for c in courses.values()}
    results: List[Tuple[str, float]] = []

    def avg_grade_for_codes(codes: set[str]) -> float | None:
        vals = [taken_grades.get(c) for c in codes if taken_grades.get(c) is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    for label, p in zip(labels, proba):
        code = str(label)
        course = courses.get(code)
        if not course or course.kind != "вибіркова":
            continue
        if code in taken_set:
            continue
        prereqs = prereq_map.get(code, set())
        if not prereqs.issubset(taken_set):
            continue

        base_score = float(p)
        course_tags = {t.strip() for t in (course.tags or "").split(",") if t.strip()}
        interest_weight = 1.15 if (course_tags & interests) else 1.0

        prereq_avg = avg_grade_for_codes(prereqs)
        if prereq_avg is None:
            prereq_avg = overall_avg_grade

        if prereq_avg is None:
            grade_weight = 1.0
        else:
            grade_weight = 0.75 + (prereq_avg / 100.0) * 0.5

        results.append((code, base_score * interest_weight * grade_weight))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def taken_courses_for_student(student: StudentProfile) -> List[str]:
    return list(
        StudentCourseEnrollment.objects.filter(student=student, status="completed").values_list("course__code", flat=True)
    )
