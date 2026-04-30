from detector import detect_stage, extract_value, Stage


def test_first_message_is_lead():
    assert detect_stage("oi tudo bem") == Stage.LEAD


def test_price_question_is_lead():
    assert detect_stage("quanto custa esse colar?") == Stage.LEAD


def test_frete_is_qualify():
    assert detect_stage("qual o frete para São Paulo?") == Stage.QUALIFY


def test_pix_is_qualify():
    assert detect_stage("aceita pix?") == Stage.QUALIFY


def test_fechado_is_purchase():
    assert detect_stage("fechado! vou levar") == Stage.PURCHASE


def test_comprovante_is_purchase():
    assert detect_stage("mandei o comprovante agora") == Stage.PURCHASE


def test_qualify_beats_lead_if_both_present():
    assert detect_stage("oi, qual o frete?") == Stage.QUALIFY


def test_purchase_beats_qualify_if_both_present():
    assert detect_stage("qual o pix para pagar? já mandei") == Stage.PURCHASE


def test_random_message_returns_none():
    assert detect_stage("ok, vou pensar") is None


def test_extract_value_brl():
    assert extract_value("Negócio Fechado - R$ 3.000,00") == 3000.0


def test_extract_value_plain_number():
    assert extract_value("mandei R$450") == 450.0


def test_extract_value_not_found():
    assert extract_value("fechado") == 0.0


def test_accent_normalization():
    assert detect_stage("Orçamento por favor") == Stage.QUALIFY


def test_uppercase_normalized():
    assert detect_stage("FRETE GRÁTIS?") == Stage.QUALIFY
