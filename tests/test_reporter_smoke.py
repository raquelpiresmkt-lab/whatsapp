import pytest
import asyncio
from state import init_db
from reporter import generate_report_text


@pytest.mark.asyncio
async def test_reporter_empty_db():
    """Smoke test: reporter with empty database returns default message."""
    db = await init_db(':memory:')
    text = await generate_report_text(db)
    assert "Nenhuma conversa rastreada esta semana" in text
    assert "📊" in text
    assert "Raquel Pires Bijoux" in text
    await db.close()
