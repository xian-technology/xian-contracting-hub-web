import reflex as rx

from contracting_hub.config import get_settings

settings = get_settings()
settings.ensure_local_paths()

config = rx.Config(
    app_name="contracting_hub",
    db_url=settings.database_url,
)
