from django.apps import AppConfig
from django.core.signals import request_started
from django.db.models.signals import post_migrate
from django.db.utils import OperationalError, ProgrammingError


def _ensure_default_groups(**kwargs) -> None:
    from django.contrib.auth.models import Group

    for name in ["Student", "Teacher", "Admin"]:
        Group.objects.get_or_create(name=name)


def _ensure_default_groups_once(**kwargs) -> None:
    if getattr(_ensure_default_groups_once, "_done", False):
        return

    try:
        _ensure_default_groups()
    except (OperationalError, ProgrammingError):
        return

    _ensure_default_groups_once._done = True


class RecommenderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recommender'

    def ready(self) -> None:
        post_migrate.connect(_ensure_default_groups, sender=self)
        request_started.connect(
            _ensure_default_groups_once,
            dispatch_uid="recommender.ensure_default_groups_once",
        )
