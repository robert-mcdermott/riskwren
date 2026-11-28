"""The application factory."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from riskwren import PRODUCT_NAME, __version__, jobs
from riskwren.access.middleware import MAX_BODY, install_access
from riskwren.access.policy import authorize
from riskwren.api.problems import install_problem_handlers
from riskwren.api.routers import (
    agreements,
    analyses,
    assessments,
    branding,
    campaigns,
    controls,
    documents,
    evidence,
    exchange,
    frameworks,
    governance,
    incidents,
    indicators,
    integration,
    internal_audit,
    inventory,
    issues,
    operations,
    people,
    questionnaires,
    reporting,
    resilience,
    risks,
    scopes,
    session,
    sso,
    system,
    third_parties,
    tidy,
    treatment,
)
from riskwren.api.routers.branding import install_branding
from riskwren.api.security import install_security_headers
from riskwren.api.static import install_static
from riskwren.config import ENV_CONFIG, Config, load_config
from riskwren.core import log as logs
from riskwren.db.engine import Database
from riskwren.home import DataHome
from riskwren.program import branding as brand_rules

ROUTERS = (
    system, session, sso, people, branding, integration, inventory, risks, controls, treatment,
    frameworks, scopes, evidence, assessments, issues, exchange, reporting, operations,
    questionnaires, campaigns, indicators, tidy, analyses, documents, agreements, governance,
    third_parties, internal_audit, resilience, incidents,
)  # fmt: skip


def create_app(config: Config) -> FastAPI:
    brand_rules.pin(config.branding)
    home = DataHome(config.data.home)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        home.require()
        app.state.db = Database(config.database_url)
        # The scheduler runs beside the server for as long as it is up.
        stop_jobs = jobs.start_worker(app.state.db, config) if config.server.scheduler else None
        try:
            yield
        finally:
            if stop_jobs is not None:
                stop_jobs.set()
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
        # Counted as it arrives, so a body sent in chunks, with no length declared, is held to
        # the same limit as one that says how long it is.
        max_body_size=MAX_BODY,
    )
    app.state.config = config
    app.state.home = home

    logs.quiet_unnamed_reports()
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
