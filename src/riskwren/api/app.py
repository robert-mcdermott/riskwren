"""The application factory."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from riskwren import PRODUCT_NAME, __version__
from riskwren.access.middleware import install_access
from riskwren.access.policy import authorize
from riskwren.api.problems import install_problem_handlers
from riskwren.api.routers import (
    branding,
    controls,
    inventory,
    people,
    risks,
    session,
    system,
    treatment,
)
from riskwren.api.routers.branding import install_branding
from riskwren.api.security import install_security_headers
from riskwren.api.static import install_static
from riskwren.config import ENV_CONFIG, Config, load_config
from riskwren.db.engine import Database
from riskwren.home import DataHome

ROUTERS = (system, session, people, branding, inventory, risks, controls, treatment)


def create_app(config: Config) -> FastAPI:
    home = DataHome(config.data.home)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        home.require()
        app.state.db = Database(config.database_url)
        try:
            yield
        finally:
            app.state.db.dispose()

    app = FastAPI(
        title=PRODUCT_NAME,
        version=__version__,
        summary="An open system of record for governance, risk, and compliance.",
        lifespan=lifespan,
        docs_url=None,  # the bundled documentation pages load third-party scripts
        redoc_url=None,
        openapi_url="/api/openapi.json",
        dependencies=[Depends(authorize)],  # every API route is checked against the policy table
    )
    app.state.config = config
    app.state.home = home

    install_access(app)  # runs inside the header middleware, so refusals carry the headers
    install_security_headers(app)
    install_problem_handlers(app)
    for module in ROUTERS:
        app.include_router(module.router)
    install_branding(app)
    install_static(app)  # last: its catch-all would shadow anything registered after it
    return app


def create_app_from_env() -> FastAPI:
    """The factory uvicorn's workers call. ``riskwren serve`` names the configuration."""
    return create_app(load_config(os.environ.get(ENV_CONFIG)))
