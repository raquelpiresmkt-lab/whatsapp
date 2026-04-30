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
