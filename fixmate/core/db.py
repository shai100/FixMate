import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from fixmate.core.settings import settings

# NullPool: asyncpg connections are bound to the event loop that created them;
# pooled reuse across loops (pytest creates one loop per test) breaks. Revisit
# with a real pool once the API runs in a single long-lived loop.
engine = create_async_engine(settings.database_app_url, poolclass=NullPool)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_for_org(org_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """The only way application code touches the DB (CLAUDE.md §6).

    Sets app.current_org_id transaction-locally on every transaction the
    session opens, so PostgreSQL RLS policies scope all queries to the tenant.
    """
    org = str(uuid.UUID(str(org_id)))
    session = session_factory()

    @event.listens_for(session.sync_session, "after_begin")
    def _set_tenant(_session, _transaction, connection) -> None:
        # set_config(..., is_local=true) == SET LOCAL: reverts at transaction
        # end, so a pooled connection can never leak another tenant's context.
        connection.execute(
            text("SELECT set_config('app.current_org_id', :org, true)"), {"org": org}
        )

    try:
        yield session
    finally:
        await session.close()
