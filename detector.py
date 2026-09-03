from __future__ import annotations
import re
import unicodedata
from state import Stage


KEYWORDS = {
    Stage.PURCHASE: [
        "vou levar", "fechado", "comprovante", "mandei", "transferi",
        "confirmei", "pedido", "pago", "confirmo",
    ],
    Stage.QUALIFY: [
        "orçamento", "orcamento", "frete", "entrega", "pagamento",
        "pix", "parcelado", "prazo", "envio", "forma de pagamento",
        "parcel", "cartão", "cartao", "boleto",
    ],
    Stage.LEAD: [
        "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite",
        "quero", "tem ", "quanto", "preço", "preco", "informação",
        "informacao", "catálogo", "catalogo", "coleção", "colecao",
        "gostaria", "interesse",
    ],
}

VALUE_PATTERN = re.compile(r"R\$\s*([\d.,]+)")

# Token que o botão de WhatsApp do site anexa ao texto pré-preenchido da
# mensagem (ver tag GTM "WhatsApp — Captura fbc"), carregando o cookie _fbc
# do visitante pra dar atribuição de clique real à venda fechada no chat.
REF_PATTERN = re.compile(r"\[ref:([^\]\s]+)\]")


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def detect_stage(text: str) -> Stage | None:
    normalized = _normalize(text)
    for stage in [Stage.PURCHASE, Stage.QUALIFY, Stage.LEAD]:
        for kw in KEYWORDS[stage]:
            if kw in normalized:
                return stage
    return None


def extract_value(text: str) -> float:
    match = VALUE_PATTERN.search(text)
    if not match:
        return 0.0
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def extract_ref(text: str) -> str | None:
    match = REF_PATTERN.search(text)
    return match.group(1) if match else None
