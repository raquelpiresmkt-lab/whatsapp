from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch
from dispatcher import dispatch_event, EventPayload
from state import Stage

@pytest.fixture
def payload():
    return EventPayload(
        contact_phone="5511999990001",
        saleswoman_name="Ana",
        stage=Stage.LEAD,
        event_ts=1714000000,
        value=0.0,
    )

async def test_dispatch_lead_calls_meta_capi(payload):
    with patch("dispatcher.send_meta_capi", new_callable=AsyncMock) as mock_meta, \
         patch("dispatcher.send_ga4", new_callable=AsyncMock), \
         patch("dispatcher.send_google_ads"):
        await dispatch_event(payload)
        mock_meta.assert_called_once()
        call_args = mock_meta.call_args[1]
        assert call_args["event_name"] == "Lead"

async def test_dispatch_purchase_sends_value(payload):
    payload.stage = Stage.PURCHASE
    payload.value = 3000.0
    with patch("dispatcher.send_meta_capi", new_callable=AsyncMock) as mock_meta, \
         patch("dispatcher.send_ga4", new_callable=AsyncMock), \
         patch("dispatcher.send_google_ads"):
        await dispatch_event(payload)
        call_args = mock_meta.call_args[1]
        assert call_args["value"] == 3000.0

async def test_dispatcher_does_not_raise_on_meta_error(payload):
    with patch("dispatcher.send_meta_capi", new_callable=AsyncMock, side_effect=Exception("network error")), \
         patch("dispatcher.send_ga4", new_callable=AsyncMock), \
         patch("dispatcher.send_google_ads"):
        await dispatch_event(payload)  # must not raise


async def test_dispatch_forwards_fbc_when_present(payload):
    payload.fbc = "fb.1.1699999999.IwAR0abc123"
    with patch("dispatcher.send_meta_capi", new_callable=AsyncMock) as mock_meta, \
         patch("dispatcher.send_ga4", new_callable=AsyncMock), \
         patch("dispatcher.send_google_ads"):
        await dispatch_event(payload)
        call_args = mock_meta.call_args[1]
        assert call_args["fbc"] == "fb.1.1699999999.IwAR0abc123"


async def test_dispatch_fbc_none_when_absent(payload):
    with patch("dispatcher.send_meta_capi", new_callable=AsyncMock) as mock_meta, \
         patch("dispatcher.send_ga4", new_callable=AsyncMock), \
         patch("dispatcher.send_google_ads"):
        await dispatch_event(payload)
        call_args = mock_meta.call_args[1]
        assert call_args["fbc"] is None


@pytest.mark.parametrize("fbc,expect_key", [("fb.1.111.abc", True), (None, False)])
async def test_send_meta_capi_payload_shape(fbc, expect_key):
    """Verifica o payload real montado pro Graph API — action_source deve
    ser 'website' (não 'other', que o Meta aceita mas nunca processa nesse
    Pixel), com event_source_url, e fbc só entra em user_data quando presente."""
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

    class FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    from dispatcher import send_meta_capi
    with patch("dispatcher.httpx.AsyncClient", FakeAsyncClient):
        await send_meta_capi(
            event_name="Purchase", phone_hash="deadbeef", event_ts=123,
            value=100.0, event_id="evt1", fbc=fbc,
        )

    event = captured["json"]["data"][0]
    assert event["action_source"] == "website"
    assert event["event_source_url"] == "https://www.raquelpires.com.br"
    assert ("fbc" in event["user_data"]) == expect_key
    if expect_key:
        assert event["user_data"]["fbc"] == fbc
