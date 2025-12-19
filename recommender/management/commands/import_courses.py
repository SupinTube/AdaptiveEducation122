from django.core.management.base import BaseCommand
from django.conf import settings

import build_sbm_project as core
from recommender.models import Course


class Command(BaseCommand):
    help = "Імпорт каталогу дисциплін з CSV/XLSX у базу даних."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Очистити таблицю Course перед імпортом (УВАГА: це видалить і пов'язані дані студентів).",
        )

    def handle(self, *args, **options):
        data_dir = settings.BASE_DIR / "data"
        catalog_csv = data_dir / "courses_catalog.csv"
        electives_xlsx = data_dir / "Дисципліни вільного вибору.xlsx"

        courses = core.load_catalog(str(catalog_csv), str(electives_xlsx))
        if options.get("wipe"):
            Course.objects.all().delete()

        # Створення курсів без пререквізитів
        created = {}
        for c in courses:
            obj, _ = Course.objects.update_or_create(
                code=c.code,
                defaults={
                    "name": c.name,
                    "ects": c.ects,
                    "semester": c.semester,
                    "kind": c.kind,
                    "block": c.block,
                    "req_math": c.req_math,
                    "req_prog": c.req_prog,
                    "req_ai": c.req_ai,
                    "req_soft": c.req_soft,
                    "tags": ",".join(c.tags),
                },
            )
            created[c.code] = (obj, c.prerequisites)

        # Додаємо пререквізити
        for code, (obj, prereq_codes) in created.items():
            prereq_objs = [created[p][0] for p in prereq_codes if p in created]
            obj.prerequisites.set(prereq_objs)

        self.stdout.write(self.style.SUCCESS(f"Імпортовано/оновлено {len(created)} дисциплін."))
