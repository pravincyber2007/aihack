import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.deps import DbSession
from app.api.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.assignment import process_due_work

logger = logging.getLogger(__name__)
WORKER_INTERVAL_SECONDS = 10


def _run_assignment_cycle() -> None:
    with SessionLocal() as db:
        process_due_work(db)


async def _assignment_worker() -> None:
    while True:
        try:
            await run_in_threadpool(_run_assignment_cycle)
        except Exception:
            logger.exception("Assignment worker cycle failed")
        await asyncio.sleep(WORKER_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    worker = asyncio.create_task(_assignment_worker()) if settings.assignment_worker_enabled else None
    yield
    if worker:
        worker.cancel()


app = FastAPI(title="Staff Portal API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness_check(db: DbSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}


app.include_router(api_router, prefix="/api/v1")
