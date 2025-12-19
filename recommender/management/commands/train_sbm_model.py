from django.core.management.base import BaseCommand
from django.conf import settings
import joblib

import build_sbm_project as core


class Command(BaseCommand):
    help = "Навчання SBM моделі на основі каталогів та синтетичних студентів із data/."

    def handle(self, *args, **options):
        data_dir = settings.BASE_DIR / "data"
        model_path = settings.SBM_MODEL_PATH

        catalog_csv = data_dir / "courses_catalog.csv"
        electives_xlsx = data_dir / "Дисципліни вільного вибору.xlsx"
        catalog = core.load_catalog(str(catalog_csv), str(electives_xlsx))

        current_students, new_students, enrollments, generated_students = core.ensure_student_data(str(data_dir), catalog)
        train_df, elective_codes = core.prepare_training_data(current_students, enrollments, catalog)
        model = core.train_sbm_model(train_df, elective_codes)

        meta = {
            "train_records": len(train_df),
            "train_students": train_df["student_id"].nunique(),
            "electives": elective_codes,
            "features": ["year", "math_level", "prog_level", "ai_level", "soft_level", "interests"],
            "students_generated": generated_students,
        }
        joblib.dump({"model": model, "meta": meta}, model_path)

        self.stdout.write(self.style.SUCCESS(f"Модель збережено у {model_path}"))
