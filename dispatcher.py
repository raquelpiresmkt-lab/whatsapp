from __future__ import annotations
import hashlib
import uuid
import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from state import Stage
from config import get_settings

logger = logging.getLogger(__name__)

STAGE_TO_META_EVENT = {
    Stage.LEAD: "Lead",
    Stage.QUALIFY: "QualifyLead",
    Stage.PURCHASE: "Purchase",
}

STAGE_TO_GADS = {
    Stage.LEAD: "gads_conversion_lead",
    Stage.QUALIFY: "gads_conversion_qualify",
    Stage.PURCHASE: "gads_conversion_purchase",
}

STAGE_TO_GA4 = {
    Stage.LEAD: "generate_lead",
    Stage.QUALIFY: "qualify_lead",
    Stage.PURCHASE: "purchase",
}


@dataclass
class EventPayload:
    contact_phone: str
    saleswoman_name: str
    stage: Stage
    event_ts: int
    value: float


def _hash_phone(phone: str) -> str:
    normalized = phone.strip().lstrip("+")
    return hashlib.sha256(normalized.encode()).hexdigest()


async def send_meta_capi(*, event_name: str, phone_hash: str, event_ts: int, value: float, event_id: str) -> None:
    settings = get_settings()
    # CAPI endpoint uses Pixel ID, not Ad Account ID
    url = f"https://graph.facebook.com/v19.0/{settings.meta_pixel_id}/events"
    payload = {
        "data": [{
            "event_name": event_name,
            "event_time": event_ts,
            "event_id": event_id,
            "action_source": "other",
            "user_data": {"ph": [phone_hash]},
            "custom_data": {"value": value, "currency": "BRL"},
        }],
        "access_token": settings.meta_access_token,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()


async def send_ga4(*, event_name: str, phone_hash: str, event_ts: int, value: float, saleswoman: str) -> None:
    settings = get_settings()
    url = (
        f"https://www.google-analytics.com/mp/collect"
        f"?measurement_id={settings.ga4_measurement_id}&api_secret={settings.ga4_api_secret}"
    )
    payload = {
        "client_id": phone_hash[:32],
        "timestamp_micros": event_ts * 1_000_000,
        "events": [{
            "name": event_name,
            "params": {
                "currency": "BRL",
                "value": value,
                "saleswoman": saleswoman,
            },
        }],
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json=payload)  # GA4 MP always returns 204


def send_google_ads(*, stage: Stage, phone_hash: str, event_ts: int, value: float) -> None:
    try:
        from google.ads.googleads.client import GoogleAdsClient
        settings = get_settings()
        client = GoogleAdsClient.load_from_storage(settings.google_ads_yaml_path)
        service = client.get_service("ConversionUploadService")

        conversion_action = getattr(settings, STAGE_TO_GADS[stage])
        conversion = client.get_type("ClickConversion")
        conversion.conversion_action = conversion_action
        dt = datetime.fromtimestamp(event_ts, tz=timezone.utc)
        conversion.conversion_date_time = dt.strftime("%Y-%m-%d %H:%M:%S+00:00")
        conversion.conversion_value = value
        conversion.currency_code = "BRL"

        identifier = client.get_type("UserIdentifier")
        identifier.hashed_phone_number = phone_hash
        conversion.user_identifiers.append(identifier)

        request = client.get_type("UploadClickConversionsRequest")
        request.customer_id = settings.google_ads_customer_id
        request.conversions.append(conversion)
        request.partial_failure = True
        service.upload_click_conversions(request=request)
    except Exception as e:
        logger.warning("Google Ads upload failed: %s", e)


async def dispatch_event(payload: EventPayload) -> None:
    event_name_meta = STAGE_TO_META_EVENT[payload.stage]
    event_name_ga4 = STAGE_TO_GA4[payload.stage]
    phone_hash = _hash_phone(payload.contact_phone)
    event_id = str(uuid.uuid4())

    results = await asyncio.gather(
        send_meta_capi(
            event_name=event_name_meta,
            phone_hash=phone_hash,
            event_ts=payload.event_ts,
            value=payload.value,
            event_id=event_id,
        ),
        send_ga4(
            event_name=event_name_ga4,
            phone_hash=phone_hash,
            event_ts=payload.event_ts,
            value=payload.value,
            saleswoman=payload.saleswoman_name,
        ),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            logger.error("Dispatch error: %s", r)

    # Google Ads is sync — run in executor to avoid blocking event loop
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: send_google_ads(
            stage=payload.stage,
            phone_hash=phone_hash,
            event_ts=payload.event_ts,
            value=payload.value,
        ),
    )
