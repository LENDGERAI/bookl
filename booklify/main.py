from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from booklify.api.routes import router
from booklify.core.config import get_settings
from booklify.core.database import Base, engine
from booklify.services.container import build_services

# Register SQLAlchemy models before metadata creation.
from booklify import models as _models  # noqa: F401


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(bind=engine)
        app.state.services = build_services(settings)
        try:
            yield
        finally:
            if hasattr(app.state, "services"):
                app.state.services.shutdown()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()

