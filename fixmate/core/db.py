"""Database access with built-in tenant isolation.

FixMate is multi-tenant: many customer organizations share one Postgres
database, and a bug that let one tenant read another's data would be
catastrophic. The defense is PostgreSQL **Row-Level Security (RLS)** — policies
on every table that filter rows to ``app.current_org_id``. For those policies to
fire, two things must be true:

  1. The app must connect as a *non-owner* role (``database_app_url``). Table
     owners and superusers bypass RLS, so the app deliberately uses a weaker
     role.
  2. Every transaction must declare which org it is acting for by setting the
     ``app.current_org_id`` session variable.

``session_for_org()`` below is the single entry point that guarantees (2). All
application code opens DB sessions through it, never by constructing a session
directly — this is the contract described in CLAUDE.md §6.
"""

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
    """Yield a DB session locked to one tenant — the only way app code touches the DB (CLAUDE.md §6).

    How it works: we open a normal SQLAlchemy ``AsyncSession``, then register an
    ``after_begin`` event listener. SQLAlchemy fires that listener the moment a
    transaction starts, and we use it to run ``SET LOCAL app.current_org_id =
    <org>``. Because it is ``SET LOCAL`` (the ``is_local=true`` argument to
    ``set_config``), the setting automatically reverts when the transaction
    ends, so a reused connection can never carry one tenant's id into another
    tenant's request. Every subsequent query in that transaction is then
    transparently filtered by the RLS policies.

    Args:
        org_id: The organization (tenant) whose data this session may see/touch.
            Round-tripped through ``uuid.UUID`` to reject malformed input before
            it reaches SQL.

    Yields:
        An ``AsyncSession`` scoped to ``org_id``. Use it inside ``async with``;
        the session is always closed on exit.
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
