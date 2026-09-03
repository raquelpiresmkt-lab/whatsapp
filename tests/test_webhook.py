from __future__ import annotations
import pytest
import os
from unittest.mock import AsyncMock, patch

# Set all required env vars BEFORE importing main/config
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
os.environ.setdefault("DASHBOARD_USER", "admin")
os.environ.setdefault("DASHBOARD_PASSWORD", "pass")
os.environ.setdefault("DASHBOARD_SECRET_KEY", "x" * 32)
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

VALID_MESSAGE = {
    "event": "messages.upsert",
    "instance": "Ana",
    "data": {
        "key": {"remoteJid": "5511999990001@s.whatsapp.net", "fromMe": False},
        "message": {"conversation": "oi, quero saber sobre os brincos"},
        "messageTimestamp": 1714000000,
    },
}

async def test_webhook_rejects_missing_auth(client):
    resp = await client.post("/webhook", json=VALID_MESSAGE)
    assert resp.status_code == 401

async def test_webhook_rejects_wrong_secret(client):
    resp = await client.post("/webhook", json=VALID_MESSAGE, headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401

async def test_webhook_accepts_valid_secret(client):
    with patch("main.dispatch_event", new_callable=AsyncMock):
        resp = await client.post(
            "/webhook", json=VALID_MESSAGE,
            headers={"Authorization": "Bearer test_secret"}
        )
    assert resp.status_code == 200

async def test_webhook_ignores_non_message_events(client):
    payload = {**VALID_MESSAGE, "event": "connection.update"}
    with patch("main.dispatch_event", new_callable=AsyncMock) as mock_dispatch:
        resp = await client.post("/webhook", json=payload, headers={"Authorization": "Bearer test_secret"})
    assert resp.status_code == 200
    mock_dispatch.assert_not_called()

async def test_webhook_fires_lead_on_first_message(client):
    with patch("main.dispatch_event", new_callable=AsyncMock) as mock_dispatch:
        await client.post("/webhook", json=VALID_MESSAGE, headers={"Authorization": "Bearer test_secret"})
    mock_dispatch.assert_called_once()
    event_payload = mock_dispatch.call_args[0][0]
    assert event_payload.stage.value == "lead"


async def test_webhook_captures_ref_token_on_lead(client):
    message = {
        **VALID_MESSAGE,
        "data": {
            **VALID_MESSAGE["data"],
            "message": {"conversation": "Posso te ajudar? [ref:fb.1.1699999999.IwAR0abc]"},
        },
    }
    with patch("main.dispatch_event", new_callable=AsyncMock) as mock_dispatch:
        await client.post("/webhook", json=message, headers={"Authorization": "Bearer test_secret"})
    event_payload = mock_dispatch.call_args[0][0]
    assert event_payload.fbc == "fb.1.1699999999.IwAR0abc"


async def test_webhook_carries_fbc_from_lead_into_later_purchase(client):
    lead_msg = {
        **VALID_MESSAGE,
        "data": {**VALID_MESSAGE["data"], "message": {"conversation": "oi [ref:fb.1.111.abc]"}},
    }
    purchase_msg = {
        **VALID_MESSAGE,
        "data": {
            **VALID_MESSAGE["data"],
            "message": {"conversation": "fechado! R$ 199,00"},
            "messageTimestamp": 1714000100,
        },
    }
    with patch("main.dispatch_event", new_callable=AsyncMock) as mock_dispatch:
        await client.post("/webhook", json=lead_msg, headers={"Authorization": "Bearer test_secret"})
        await client.post("/webhook", json=purchase_msg, headers={"Authorization": "Bearer test_secret"})

    purchase_payload = mock_dispatch.call_args_list[-1][0][0]
    assert purchase_payload.stage.value == "purchase"
    assert purchase_payload.fbc == "fb.1.111.abc"
