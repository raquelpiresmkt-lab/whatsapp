import pytest
import asyncio
import time
from state import init_db, advance_stage, Stage
from reporter import generate_report_text


@pytest.mark.asyncio
async def test_reporter_with_sample_data():
    """Smoke test: reporter with sample data shows metrics and alerts."""
    db = await init_db(':memory:')
    
    # Add sample data
    now = int(time.time())
    
    # Ana: 3 leads, 1 qualified, 1 purchase R$100
    await advance_stage(db, "5511999999999", "5511900000001", Stage.LEAD, now, 0)
    await advance_stage(db, "5511999999998", "5511900000001", Stage.LEAD, now, 0)
    await advance_stage(db, "5511999999997", "5511900000001", Stage.LEAD, now, 0)
    await advance_stage(db, "5511999999999", "5511900000001", Stage.QUALIFY, now+10, 0)
    await advance_stage(db, "5511999999999", "5511900000001", Stage.PURCHASE, now+20, 100.0)
    
    # Carol: 6 leads, 0 qualified (low conversion alert)
    for i in range(6):
        await advance_stage(db, f"551199999999{i}", "5511900000002", Stage.LEAD, now+i, 0)
    
    text = await generate_report_text(db)
    
    # Verify summary section
    assert "📊 *Relatório Semanal — Raquel Pires Bijoux*" in text
    assert "9 leads" in text  # 3 + 6
    assert "1 qualificados" in text
    assert "1 vendas" in text
    assert "R$ 100,00" in text
    
    # Verify per-saleswoman section
    assert "Ana" in text
    assert "Carol" in text
    assert "3 leads" in text
    assert "6 leads" in text
    
    # Verify alert for low conversion
    assert "⚠️ *Atenção:*" in text
    assert "Carol" in text  # Carol should be in alert
    
    await db.close()
