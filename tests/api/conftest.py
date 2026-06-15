import uuid

import httpx
import pytest
from httpx import ASGITransport

from fixmate.api.main import app
from fixmate.core.db import session_for_org
from fixmate.core.models import User


def auth_headers(org_id, user_id, role: str = "tech") -> dict[str, str]:
    return {"X-Org-Id": str(org_id), "X-User-Id": str(user_id), "X-Role": role}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def org_user(two_orgs):
    """Org A with one tech user, plus org B's id for tenancy tests.

    Returns (org_a_id, user_id, org_b_id).
    """
    org_a, org_b = two_orgs
    async with session_for_org(org_a) as s:
        user = User(organization_id=org_a, name="Tech One", role="tech", email="tech@example.com")
        s.add(user)
        await s.commit()
        user_id = user.id
    return org_a, user_id, org_b


@pytest.fixture
def random_id():
    return uuid.uuid4()
