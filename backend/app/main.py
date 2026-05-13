"""Entry point for the claw backend."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agents.manager import seed_defaults_if_empty
from app.api import agents as agents_api
from app.api import connectors as connectors_api
from app.api import models as models_api
from app.api import settings as settings_api
from app.api import static as static_api
from app.api import system as system_api
from app.api import terminal as terminal_api
from app.api import tools as tools_api
from app.api import vk as vk_api
from app.core.config import get_settings
from app.core.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await seed_defaults_if_empty()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="claw", version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST
    app.include_router(system_api.router)
    app.include_router(vk_api.router)
    app.include_router(agents_api.router)
    app.include_router(connectors_api.router)
    app.include_router(tools_api.router)
    app.include_router(settings_api.router)
    app.include_router(models_api.router)

    # WebSocket
    app.include_router(system_api.ws_router)
    app.include_router(terminal_api.ws_router)
    app.include_router(agents_api.ws_router)
    app.include_router(models_api.ws_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    # Must be mounted LAST so it doesn't swallow /api and /ws routes.
    static_api.mount_frontend(app)

    return app


app = create_app()
