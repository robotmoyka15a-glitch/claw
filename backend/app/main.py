"""Entry point for the claw backend."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agents.manager import seed_defaults_if_empty
from app.api import agents as agents_api
from app.api import auth as auth_api
from app.api import autonomy as autonomy_api
from app.api import connectors as connectors_api
from app.api import settings as settings_api
from app.api import static as static_api
from app.api import system as system_api
from app.api import terminal as terminal_api
from app.api import tools as tools_api
from app.api import vk as vk_api
from app.api import webhook as webhook_api
from app.api import models as models_api
from app.core.config import get_settings
from app.core.db import init_db
from app.core.security import install_sanitised_logging

# Install sanitised logging early so startup messages are masked.
logging.basicConfig(level=logging.INFO)
install_sanitised_logging()

logger = logging.getLogger("claw.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await seed_defaults_if_empty()
    # Start autonomous agent scheduler
    from app.agents import autonomy  # noqa: PLC0415
    await autonomy.start_scheduler()
    # Start Telegram long-poll if token configured
    from app.connectors import telegram_poller  # noqa: PLC0415
    await telegram_poller.start()
    yield
    await autonomy.stop_scheduler()
    await telegram_poller.stop()


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
    app.include_router(auth_api.router)
    app.include_router(system_api.router)
    app.include_router(vk_api.router)
    app.include_router(agents_api.router)
    app.include_router(connectors_api.router)
    app.include_router(tools_api.router)
    app.include_router(settings_api.router)
    app.include_router(autonomy_api.router)
    app.include_router(webhook_api.router)

    # WebSocket
    app.include_router(system_api.ws_router)
    app.include_router(terminal_api.ws_router)
    app.include_router(agents_api.ws_router)
    app.include_router(autonomy_api.ws_router)
    app.include_router(models_api.ws_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    # Must be mounted LAST so it doesn't swallow /api and /ws routes.
    static_api.mount_frontend(app)

    return app


app = create_app()
