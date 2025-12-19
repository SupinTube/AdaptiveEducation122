import os
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
import joblib
from sklearn.naive_bayes import MultinomialNB




RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


@dataclass
class Course:
    """Опис навчальної компоненти."""

    code: str
    name: str
    ects: float
    semester: int
    kind: str  # "обов'язкова" або "вибіркова"
    block: str  # "загальна", "професійна", "вільний вибір"
    req_math: int
    req_prog: int
    req_ai: int
    req_soft: int
    prerequisites: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


def read_free_electives(xlsx_path: str) -> List[str]:
    """Зчитування дисциплін вільного вибору з Excel."""
    df = pd.read_excel(xlsx_path)
    return [str(x).strip() for x in df.iloc[:, 0].dropna().tolist()]


def load_catalog(catalog_csv: str, electives_xlsx: str) -> List[Course]:
    """Читаємо каталог дисциплін із CSV; назви вибіркових курсів підтягуються з XLSX."""
    df = pd.read_csv(catalog_csv)
    free_electives = read_free_electives(electives_xlsx)
    free_iter = iter(free_electives)

    courses: List[Course] = []
    for _, row in df.iterrows():
        name = str(row["name"]) if pd.notna(row["name"]) else ""
        if row["kind"].startswith("вибіркова") and (not name or "вибору" in name.lower()):
            name = next(free_iter, name or row["code"])

        prerequisites = []
        if pd.notna(row.get("prerequisites")) and str(row["prerequisites"]).strip():
            prerequisites = [x.strip() for x in str(row["prerequisites"]).split("|") if x.strip()]

        tags = []
        if pd.notna(row.get("tags")) and str(row["tags"]).strip():
            tags = [x.strip() for x in str(row["tags"]).split("|") if x.strip()]

        courses.append(
            Course(
                code=str(row["code"]),
                name=name,
                ects=float(row["ects"]),
                semester=int(row["semester"]),
                kind=str(row["kind"]),
                block=str(row["block"]),
                req_math=int(row["req_math"]),
                req_prog=int(row["req_prog"]),
                req_ai=int(row["req_ai"]),
                req_soft=int(row["req_soft"]),
                prerequisites=prerequisites,
                tags=tags,
            )
        )
    return courses


def generate_student_profiles(n_current: int, n_new: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Створення синтетичних студентів з навичками та інтересами."""
    interests_pool = ["ai", "data", "web", "systems", "security", "management", "ux", "science"]

    def make_student(idx: int, status: str, forced_year: int | None = None) -> Dict:
        year_weights = [0.28, 0.26, 0.24, 0.22]
        year = forced_year if forced_year else int(np.random.choice([1, 2, 3, 4], p=year_weights))
        base_skill = year / 4
        skills = {
            "math": np.clip(np.random.normal(base_skill, 0.15), 0, 1),
            "prog": np.clip(np.random.normal(base_skill + 0.1, 0.15), 0, 1),
            "ai": np.clip(np.random.normal(base_skill - 0.05, 0.2), 0, 1),
            "soft": np.clip(np.random.normal(0.45 + 0.1 * (year - 1), 0.2), 0, 1),
        }
        interest = random.sample(interests_pool, k=3)
        student = {
            "student_id": f"{status.upper()}_{idx:04d}",
            "status": status,
            "year": year,
            "math_level": round(skills["math"], 3),
            "prog_level": round(skills["prog"], 3),
            "ai_level": round(skills["ai"], 3),
            "soft_level": round(skills["soft"], 3),
            "interests": ",".join(interest),
        }
        return student

    current = pd.DataFrame([make_student(i, "current") for i in range(1, n_current + 1)])
    newcomers = pd.DataFrame([make_student(i, "new", forced_year=1) for i in range(1, n_new + 1)])
    return current, newcomers


def pick_courses_for_student(student: Dict, catalog: List[Course]) -> List[str]:
    """Генерація списку пройдених дисциплін для студента відповідно до курсу та інтересів."""
    current_sem = student["year"] * 2
    mandatory = [c.code for c in catalog if c.kind == "обов'язкова" and c.semester <= current_sem]

    elective_candidates = [c for c in catalog if c.kind == "вибіркова" and c.semester <= current_sem]
    taken_electives = []
    for c in elective_candidates:
        take_prob = 0.4 + 0.1 * (student["year"] - 1)
        if any(tag in student["interests"] for tag in c.tags):
            take_prob += 0.15
        if random.random() < take_prob:
            taken_electives.append(c.code)

    return mandatory + taken_electives


def build_enrollments(students: pd.DataFrame, catalog: List[Course]) -> pd.DataFrame:
    """Створення таблиці пройдених курсів студентами."""
    records = []
    for _, row in students.iterrows():
        passed = pick_courses_for_student(row, catalog)
        for code in passed:
            records.append({"student_id": row.student_id, "course_code": code})
    return pd.DataFrame(records)


def prepare_training_data(students: pd.DataFrame, enrollments: pd.DataFrame, catalog: List[Course]) -> Tuple[pd.DataFrame, List[str]]:
    """Формування навчальної вибірки для рекомендацій: один запис = вибраний вибірковий курс."""
    elective_codes = {c.code for c in catalog if c.kind == "вибіркова"}
    joined = enrollments[enrollments.course_code.isin(elective_codes)].merge(students, on="student_id")
    return joined, sorted(list(elective_codes))


def encode_features(df: pd.DataFrame) -> np.ndarray:
    """Перетворення характеристик студентів у вектор ознак."""
    interest_cols = ["ai", "data", "web", "systems", "security", "management", "ux", "science"]
    features = []
    for _, row in df.iterrows():
        interest_vec = [1 if tag in row.interests.split(",") else 0 for tag in interest_cols]
        features.append(
            [
                row.year,
                row.math_level,
                row.prog_level,
                row.ai_level,
                row.soft_level,
                *interest_vec,
            ]
        )
    return np.array(features, dtype=float)


def train_sbm_model(train_df: pd.DataFrame, elective_codes: List[str]) -> MultinomialNB:
    """Навчання простої байєсівської моделі (SBM) над вибірками."""
    X = encode_features(train_df)
    y = train_df.course_code.values
    model = MultinomialNB(alpha=0.5)
    model.fit(X, y)
    return model


def save_model(model: MultinomialNB, meta: Dict, model_path: str) -> None:
    """Збереження моделі та метаданих."""
    joblib.dump({"model": model, "meta": meta}, model_path)


def load_model(model_path: str) -> Tuple[MultinomialNB, Dict] | Tuple[None, None]:
    """Спроба завантажити збережену модель."""
    if not os.path.exists(model_path):
        return None, None
    payload = joblib.load(model_path)
    return payload.get("model"), payload.get("meta", {})


def recommend_for_student(student: pd.Series, model: MultinomialNB, catalog: List[Course], taken: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
    """Рекомендації вибіркових дисциплін для конкретного студента."""
    elective_catalog = {c.code: c for c in catalog if c.kind == "вибіркова"}
    features_df = pd.DataFrame([student])
    X = encode_features(features_df)
    proba = model.predict_proba(X)[0]
    labels = model.classes_
    scored = []
    for label, p in zip(labels, proba):
        course = elective_catalog.get(label)
        if not course or label in taken:
            continue
        prereq_ok = all(pr in taken for pr in course.prerequisites)
        if not prereq_ok:
            continue
        scored.append((label, float(p)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def export_catalog(catalog: List[Course], out_dir: str) -> None:
    rows = []
    for c in catalog:
        rows.append(
            {
                "code": c.code,
                "name": c.name,
                "ects": c.ects,
                "semester": c.semester,
                "kind": c.kind,
                "block": c.block,
                "req_math": c.req_math,
                "req_prog": c.req_prog,
                "req_ai": c.req_ai,
                "req_soft": c.req_soft,
                "prerequisites": "|".join(c.prerequisites),
                "tags": "|".join(c.tags),
            }
        )
    pd.DataFrame(rows).to_csv(os.path.join(out_dir, "courses_catalog.csv"), index=False, encoding="utf-8")


def export_students(df: pd.DataFrame, fname: str, out_dir: str) -> None:
    df.to_csv(os.path.join(out_dir, fname), index=False, encoding="utf-8")


def export_enrollments(df: pd.DataFrame, out_dir: str) -> None:
    df.to_csv(os.path.join(out_dir, "student_enrollments.csv"), index=False, encoding="utf-8")


def save_students_to_data(current: pd.DataFrame, new: pd.DataFrame, enrollments: pd.DataFrame, data_dir: str) -> None:
    """Зберігаємо стабільні дані студентів і їхніх проходжень у каталозі data."""
    current.to_csv(os.path.join(data_dir, "students_current.csv"), index=False, encoding="utf-8")
    new.to_csv(os.path.join(data_dir, "students_new.csv"), index=False, encoding="utf-8")
    enrollments.to_csv(os.path.join(data_dir, "student_enrollments.csv"), index=False, encoding="utf-8")


def load_students_from_data(data_dir: str) -> Tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
    """Читає студентів з файлів, якщо вони є."""
    curr_path = os.path.join(data_dir, "students_current.csv")
    new_path = os.path.join(data_dir, "students_new.csv")
    enroll_path = os.path.join(data_dir, "student_enrollments.csv")
    current = pd.read_csv(curr_path) if os.path.exists(curr_path) else None
    new = pd.read_csv(new_path) if os.path.exists(new_path) else None
    enroll = pd.read_csv(enroll_path) if os.path.exists(enroll_path) else None
    return current, new, enroll


def ensure_student_data(data_dir: str, catalog: List[Course]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
    """Гарантує наявність стабільних даних студентів; генерує їх лише якщо файлів немає."""
    current, new, enroll = load_students_from_data(data_dir)
    generated = False
    if current is None or new is None or enroll is None:
        current, new = generate_student_profiles(320, 25)
        enroll = build_enrollments(current, catalog)
        save_students_to_data(current, new, enroll, data_dir)
        generated = True
    return current, new, enroll, generated


def write_model_report(report_path: str, reused: bool, meta: Dict) -> None:
    """Текстовий звіт про вибір та використання моделі."""
    lines = [
        "Звіт про модель рекомендацій вибіркових дисциплін",
        f"Статус: {'використано наявну модель' if reused else 'натреновано нову модель'}",
        f"Кількість записів у тренуванні: {meta.get('train_records', 'н/д')}",
        f"Кількість студентів у тренуванні: {meta.get('train_students', 'н/д')}",
        f"Кількість вибіркових дисциплін: {len(meta.get('electives', [])) if meta.get('electives') else 'н/д'}",
        "Ознаки: рік навчання, рівні math/prog/ai/soft, бінарні інтереси",
        "",
        "Чому Multinomial Naive Bayes (SBM):",
        "- працює з невеликими та розрідженими вибірками ознак, швидко навчається;",
        "- придатний для багатокласової класифікації (кожна дисципліна — окремий клас);",
        "- інтерпретований: можна переглянути ваги/ймовірності по класах;",
        "- проста базова модель для синтетичних даних; легко перевчити при оновленні датасету.",
        "",
        "Зауваження:",
        "- якщо змінилися каталоги курсів чи студенти — видаліть sbm_model.joblib, щоб натренувати заново;",
        "- для продакшену рекомендовано додати крос-валідацію та більш складні моделі (наприклад, факторизацію).",
    ]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    data_dir = "data"
    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)
    model_path = os.path.join(out_dir, "sbm_model.joblib")
    report_path = os.path.join(out_dir, "model_report.txt")

    catalog_csv = os.path.join(data_dir, "courses_catalog.csv")
    electives_xlsx = os.path.join(data_dir, "Дисципліни вільного вибору.xlsx")
    catalog = load_catalog(catalog_csv, electives_xlsx)

    current_students, new_students, enrollments, generated_students = ensure_student_data(data_dir, catalog)
    train_df, elective_codes = prepare_training_data(current_students, enrollments, catalog)

    sbm_model, meta = load_model(model_path)
    reused_model = sbm_model is not None
    if not reused_model:
        sbm_model = train_sbm_model(train_df, elective_codes)
        meta = {
            "train_records": len(train_df),
            "train_students": train_df["student_id"].nunique(),
            "electives": elective_codes,
            "features": ["year", "math_level", "prog_level", "ai_level", "soft_level", "interests"],
            "students_generated": generated_students,
        }
        save_model(sbm_model, meta, model_path)

    recommendations = []
    for _, student in new_students.iterrows():
        taken = []
        recs = recommend_for_student(student, sbm_model, catalog, taken, top_k=5)
        for code, prob in recs:
            recommendations.append({"student_id": student.student_id, "course_code": code, "score": round(prob, 4)})

    export_catalog(catalog, out_dir)
    export_students(current_students, "students_current.csv", out_dir)
    export_students(new_students, "students_new.csv", out_dir)
    export_enrollments(enrollments, out_dir)
    pd.DataFrame(recommendations).to_csv(os.path.join(out_dir, "recommendations_new_students.csv"), index=False, encoding="utf-8")

    write_model_report(report_path, reused_model, meta)

    print("Каталоги, рекомендації та модель збережено в директорії:", out_dir)


if __name__ == "__main__":
    main()
