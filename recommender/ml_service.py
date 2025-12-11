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


def recommend_for_profile(student: StudentProfile, taken_codes: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
    """Будуємо рекомендації для профілю студента на основі збереженої моделі."""
    model, _ = load_model()
    if model is None:
        raise RuntimeError("Модель не знайдено. Спершу натренуйте її командою train_sbm_model.")

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

    for label, p in zip(labels, proba):
        course = courses.get(label)
        if not course or course.kind != "вибіркова":
            continue
        if label in taken_codes:
            continue
        if not prereq_map.get(label, set()).issubset(set(taken_codes)):
            continue
        results.append((label, float(p)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def taken_courses_for_student(student: StudentProfile) -> List[str]:
    return list(
        StudentCourseEnrollment.objects.filter(student=student, status="completed").values_list("course__code", flat=True)
    )
