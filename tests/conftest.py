# Shared fixtures land here as phases add them (two_orgs in Phase 1, etc.).
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from fixmate.core.settings import settings

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def migrated_db():
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=REPO_ROOT,
    )


@pytest.fixture
async def two_orgs(migrated_db):
    # Owner connection (not fixmate_app): creating organizations is a bootstrap
    # operation that happens outside any tenant context.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    org_ids = []
    async with engine.begin() as conn:
        for name in ("Org A", "Org B"):
            org_id = await conn.scalar(
                text("INSERT INTO organizations (name) VALUES (:name) RETURNING id"),
                {"name": name},
            )
            org_ids.append(org_id)
    yield tuple(org_ids)
    async with engine.begin() as conn:
        for org_id in org_ids:
            await conn.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
    await engine.dispose()
