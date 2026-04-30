from __future__ import annotations
import pytest
import os

os.environ.setdefault("EVOLUTION_API_URL", "http://evo.test")
os.environ.setdefault("EVOLUTION_API_KEY", "test_key")
os.environ.setdefault("WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("META_ACCESS_TOKEN", "test_token")
os.environ.setdefault("META_PIXEL_ID", "1234567890")
os.environ.setdefault("META_AD_ACCOUNT_ID", "act_123")
os.environ.setdefault("GA4_MEASUREMENT_ID", "G-TEST")
os.environ.setdefault("GA4_API_SECRET", "ga4_secret")
os.environ.setdefault("GOOGLE_ADS_YAML_PATH", "/tmp/fake.yaml")
os.environ.setdefault("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
os.environ.setdefault("GADS_CONVERSION_LEAD", "customers/1/conversionActions/1")
os.environ.setdefault("GADS_CONVERSION_QUALIFY", "customers/1/conversionActions/2")
os.environ.setdefault("GADS_CONVERSION_PURCHASE", "customers/1/conversionActions/3")
os.environ.setdefault("DASHBOARD_USER", "raquel")
os.environ.setdefault("DASHBOARD_PASSWORD", "testpass")
os.environ.setdefault("DASHBOARD_SECRET_KEY", "a" * 32)
os.environ.setdefault("RAQUEL_PHONE", "5511900000000")
os.environ.setdefault("REPORT_SENDER_INSTANCE", "inst1")
os.environ.setdefault("SALESWOMAN_1", "Ana:5511900000001")

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import create_app

@pytest_asyncio.fixture
async def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

async def test_dashboard_redirects_unauthenticated(client):
    resp = await client.get("/dashboard", follow_redirects=False)
    assert resp.status_code in (302, 307)

async def test_login_with_wrong_password(client):
    resp = await client.post("/login", data={"username": "raquel", "password": "wrong"})
    assert resp.status_code == 401

async def test_login_sets_cookie(client):
    resp = await client.post(
        "/login",
        data={"username": "raquel", "password": "testpass"},
        follow_redirects=False
    )
    assert resp.status_code in (302, 307)
    assert "session" in resp.cookies

async def test_dashboard_accessible_after_login(client):
    await client.post("/login", data={"username": "raquel", "password": "testpass"})
    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    assert "Raquel Pires" in resp.text
