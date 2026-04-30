from __future__ import annotations

import time
import logging

import httpx
from state import get_weekly_stats
from config import get_settings

logger = logging.getLogger(__name__)


async def generate_report_text(db) -> str:
    settings = get_settings()
    since = int(time.time()) - 7 * 86400
    stats = await get_weekly_stats(db, since)

    if not stats:
        return "📊 *Relatório Semanal — Raquel Pires Bijoux*\n\nNenhuma conversa rastreada esta semana."

    total_leads = sum(r["leads"] for r in stats)
    total_qual = sum(r["qualified"] for r in stats)
    total_sales = sum(r["purchases"] for r in stats)
    total_rev = sum(r["revenue"] for r in stats)
    conv_rate = f"{(total_sales / total_leads * 100):.0f}%" if total_leads else "0%"

    def fmt_brl(v: float) -> str:
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    lines = [
        "📊 *Relatório Semanal — Raquel Pires Bijoux*",
        "",
        f"💬 *{total_leads} leads* recebidos",
        f"🔍 *{total_qual} qualificados* ({int(total_qual / total_leads * 100) if total_leads else 0}%)",
        f"✅ *{total_sales} vendas* ({conv_rate} conversão)",
        f"💰 *{fmt_brl(total_rev)}* em vendas rastreadas",
        "",
        "*Por vendedora:*",
    ]

    alerts = []
    for row in stats:
        name = settings.saleswomen.get(row["saleswoman_phone"], row["saleswoman_phone"])
        leads = row["leads"]
        sales = row["purchases"]
        rev = row["revenue"]
        lines.append(f"{name} → {leads} leads | {sales} vendas | {fmt_brl(rev)}")
        if leads >= 5 and (sales / leads if leads else 0) < 0.15:
            alerts.append(name)

    if alerts:
        lines.append("")
        lines.append(f"⚠️ *Atenção:* {', '.join(alerts)} com baixa conversão — vale uma conversa.")

    lines.append("")
    lines.append("_Enviado automaticamente pela Alice 🤖_")
    return "\n".join(lines)


async def send_whatsapp_message(text: str) -> None:
    settings = get_settings()
    url = f"{settings.evolution_api_url}/message/sendText/{settings.report_sender_instance}"
    headers = {"Authorization": f"Bearer {settings.evolution_api_key}"}
    payload = {"number": settings.raquel_phone, "text": text}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
    logger.info("Weekly report sent to %s", settings.raquel_phone)


async def send_weekly_report(db) -> None:
    text = await generate_report_text(db)
    await send_whatsapp_message(text)
