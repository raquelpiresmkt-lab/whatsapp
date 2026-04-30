import pytest
import pytest_asyncio
from datetime import datetime, timezone
from state import init_db, get_active_conversation, advance_stage, Stage

@pytest_asyncio.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = await init_db(db_path)
    yield conn
    await conn.close()

@pytest.mark.asyncio
async def test_new_contact_has_no_conversation(db):
    conv = await get_active_conversation(db, "5511999990001", "5511900000001")
    assert conv is None

@pytest.mark.asyncio
async def test_advance_to_lead_creates_conversation(db):
    await advance_stage(db, "5511999990001", "5511900000001", Stage.LEAD, 1234567890, 0.0)
    conv = await get_active_conversation(db, "5511999990001", "5511900000001")
    assert conv is not None
    assert conv["current_stage"] == "lead"

@pytest.mark.asyncio
async def test_cannot_advance_lead_twice(db):
    await advance_stage(db, "5511999990001", "5511900000001", Stage.LEAD, 1234567890, 0.0)
    result = await advance_stage(db, "5511999990001", "5511900000001", Stage.LEAD, 1234567890, 0.0)
    assert result is False

@pytest.mark.asyncio
async def test_advance_lead_to_qualify(db):
    await advance_stage(db, "5511999990001", "5511900000001", Stage.LEAD, 1234567890, 0.0)
    result = await advance_stage(db, "5511999990001", "5511900000001", Stage.QUALIFY, 1234567891, 0.0)
    assert result is True
    conv = await get_active_conversation(db, "5511999990001", "5511900000001")
    assert conv["current_stage"] == "qualified"

@pytest.mark.asyncio
async def test_advance_to_purchase_closes_conversation(db):
    await advance_stage(db, "5511999990001", "5511900000001", Stage.LEAD, 100, 0.0)
    await advance_stage(db, "5511999990001", "5511900000001", Stage.QUALIFY, 101, 0.0)
    await advance_stage(db, "5511999990001", "5511900000001", Stage.PURCHASE, 102, 3000.0)
    conv = await get_active_conversation(db, "5511999990001", "5511900000001")
    assert conv is None

@pytest.mark.asyncio
async def test_new_conversation_after_purchase(db):
    await advance_stage(db, "5511999990001", "5511900000001", Stage.LEAD, 100, 0.0)
    await advance_stage(db, "5511999990001", "5511900000001", Stage.PURCHASE, 101, 0.0)
    result = await advance_stage(db, "5511999990001", "5511900000001", Stage.LEAD, 200, 0.0)
    assert result is True
