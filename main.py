from __future__ import annotations
import sys, io
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from dashboard import router as dashboard_router
from state import init_db, advance_stage, Stage, get_active_conversation, get_conversation
from detector import detect_stage, extract_value, extract_ref
from dispatcher import dispatch_event, EventPayload
from reporter import send_weekly_report
from config import get_settings

logger = logging.getLogger(__name__)


def _parse_phone(jid: str) -> str:
    return jid.split("@")[0]


def _get_message_text(data: dict) -> str:
    msg = data.get("message", {})
    return (
        msg.get("conversation")
        or msg.get("extendedTextMessage", {}).get("text")
        or ""
    )


def create_app(db_path: str = "database.db") -> FastAPI:
    settings = get_settings()
    db_conn = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal db_conn
        db_conn = await init_db(db_path)
        app.state.db = db_conn
        scheduler = AsyncIOScheduler(timezone=pytz.timezone("America/Sao_Paulo"))
        scheduler.add_job(
            send_weekly_report,
            CronTrigger(day_of_week="mon", hour=8, minute=0),
            args=[db_conn],
        )
        scheduler.start()
        yield
        scheduler.shutdown()
        if db_conn:
            await db_conn.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(dashboard_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/webhook")
    async def webhook(request: Request):
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {settings.webhook_secret}":
            raise HTTPException(status_code=401, detail="Unauthorized")

        body = await request.json()

        # Normalize event name — Evolution API may send MESSAGES_UPSERT or messages.upsert
        event_type = body.get("event", "").lower().replace("_", ".")
        if event_type != "messages.upsert":
            return {"status": "ignored"}

        data = body.get("data", {})
        key = data.get("key", {})
        contact_jid = key.get("remoteJid", "")

        if "@g.us" in contact_jid:
            return {"status": "ignored"}

        contact_phone = _parse_phone(contact_jid)
        instance_name = body.get("instance", "")

        saleswoman_phone = None
        saleswoman_name = instance_name
        for phone, name in settings.saleswomen.items():
            if name.lower() == instance_name.lower():
                saleswoman_phone = phone
                saleswoman_name = name
                break
        if not saleswoman_phone:
            saleswoman_phone = instance_name

        text = _get_message_text(data)
        event_ts = int(data.get("messageTimestamp", 0))

        stage = detect_stage(text)
        value = extract_value(text) if stage == Stage.PURCHASE else 0.0
        ref_fbc = extract_ref(text)

        # Prefer db set by lifespan; fall back to creating a new connection (test scenarios)
        try:
            conn = request.app.state.db
        except AttributeError:
            conn = await init_db(db_path)
            request.app.state.db = conn

        if stage is None:
            conv = await get_active_conversation(conn, contact_phone, saleswoman_phone)
            if conv is None and not key.get("fromMe"):
                stage = Stage.LEAD

        if stage is None:
            return {"status": "no_stage"}

        advanced = await advance_stage(conn, contact_phone, saleswoman_phone, stage, event_ts, value, fbc=ref_fbc)
        if not advanced:
            return {"status": "already_tracked"}

        # fbc é capturado só na mensagem de abertura (LEAD); pra QUALIFY e
        # PURCHASE (dias depois), recupera o que ficou guardado na conversa —
        # get_conversation (não get_active_conversation) pra funcionar mesmo
        # já fechada em 'purchase'.
        conv = await get_conversation(conn, contact_phone, saleswoman_phone)
        fbc = conv["fbc"] if conv else None

        await dispatch_event(EventPayload(
            contact_phone=contact_phone,
            saleswoman_name=saleswoman_name,
            stage=stage,
            event_ts=event_ts,
            value=value,
            fbc=fbc,
        ))

        return {"status": "ok", "stage": stage.value}

    return app


app = create_app()

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
