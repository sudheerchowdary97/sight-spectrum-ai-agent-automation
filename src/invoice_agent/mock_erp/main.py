"""Mock ERP FastAPI app. Run with ``uvicorn invoice_agent.mock_erp.main:app``.

Stand-in ERP exposing PO / Goods-Receipt / AR reads and Payment-Journal /
cash-application writes, seeded from the Task 1 master data. Behind a small
store interface so a real SAP/Oracle/NetSuite connector can replace it later.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from invoice_agent import __version__
from invoice_agent.config import get_settings
from invoice_agent.logging_config import configure_logging, get_logger
from invoice_agent.mock_erp.routers import router
from invoice_agent.mock_erp.store import ERPStore


def create_app(store: ERPStore | None = None) -> FastAPI:
    """Build the Mock ERP app.

    If ``store`` is provided it is used as-is (handy for tests); otherwise the
    store is seeded from ``settings.erp_data_dir`` on start-up.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        log = get_logger("mock-erp")
        settings = get_settings()
        if getattr(app.state, "store", None) is None:
            app.state.store = ERPStore.from_dir(settings.erp_data_dir)
        log.info("mock-erp.startup", version=__version__)
        yield
        log.info("mock-erp.shutdown")

    app = FastAPI(
        title="Mock ERP API",
        version=__version__,
        description="Stand-in ERP exposing PO/GR/AR reads and journal posting for the agent.",
        lifespan=lifespan,
    )
    # Injected store (tests) is available immediately, without waiting for lifespan.
    app.state.store = store
    app.include_router(router)
    return app


app = create_app()
