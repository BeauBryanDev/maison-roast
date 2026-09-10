import os

from django.apps import AppConfig


class BasilConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'basil'
    verbose_name = 'Basil (AI concierge)'

    def ready(self):
        # Warm the ONNX session onc so the first upload is
        # not slow.  A missing model file must not stop the site booting.
        if os.environ.get('RUN_MAIN') == 'false' or 'test' in os.sys.argv:
            return

        from django.conf import settings
        if not settings.BASIL_MODEL_PATH.exists():
            return

        try:
            from .vision.infer import get_session
            get_session()
        except Exception:
            pass
