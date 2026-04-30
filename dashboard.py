from __future__ import annotations
import time
from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
from state import get_weekly_stats, init_db
from config import get_settings

router = APIRouter()


def _make_signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().dashboard_secret_key)


def _get_session(request: Request) -> str | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        return _make_signer().loads(token, max_age=28800)  # 8h
    except BadSignature:
        return None


@router.get("/login", response_class=HTMLResponse)
async def login_page() -> HTMLResponse:
    return HTMLResponse("""
    <html><head><title>Login — Raquel Pires</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f9f9f9}
    form{background:#fff;padding:2rem;border-radius:12px;box-shadow:0 2px 16px #0001;display:flex;flex-direction:column;gap:1rem;min-width:280px}
    input{padding:.75rem;border:1px solid #ddd;border-radius:8px;font-size:1rem}
    button{background:#c62a88;color:#fff;border:none;padding:.75rem;border-radius:8px;font-size:1rem;cursor:pointer}
    </style></head><body>
    <form method="post" action="/login">
      <h2 style="margin:0;color:#c62a88">Raquel Pires Bijoux</h2>
      <input name="username" placeholder="Usuário" required>
      <input name="password" type="password" placeholder="Senha" required>
      <button type="submit">Entrar</button>
    </form></body></html>
    """)


@router.post("/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)) -> Response:
    settings = get_settings()
    if username != settings.dashboard_user or password != settings.dashboard_password:
        return HTMLResponse("Usuário ou senha incorretos", status_code=401)
    token = _make_signer().dumps(username)
    redirect = RedirectResponse("/dashboard", status_code=302)
    redirect.set_cookie("session", token, httponly=True, samesite="strict", max_age=28800)
    return redirect


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> Response:
    if not _get_session(request):
        return RedirectResponse("/login")

    db = getattr(request.app.state, "db", None)
    if db is None:
        db = await init_db()
        request.app.state.db = db

    settings = get_settings()
    since = int(time.time()) - 7 * 86400
    stats = await get_weekly_stats(db, since)

    rows = ""
    for row in stats:
        phone = row["saleswoman_phone"]
        name = settings.saleswomen.get(phone, phone)
        leads = row["leads"]
        qual = row["qualified"]
        sales = row["purchases"]
        rev = row["revenue"]
        conv_rate = f"{(sales / leads * 100):.0f}%" if leads else "0%"
        alert = "&#9888;" if leads >= 10 and (sales / leads if leads else 0) < 0.15 else ""
        rows += (
            f"<tr><td>{alert} {name}</td>"
            f"<td>{leads}</td><td>{qual}</td><td>{sales}</td>"
            f"<td>R$ {rev:,.2f}</td><td>{conv_rate}</td></tr>"
        )

    empty_row = '<tr><td colspan="6" style="text-align:center;color:#aaa">Nenhum dado ainda</td></tr>'
    html = f"""
    <html><head><title>Dashboard — Raquel Pires</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    body{{font-family:sans-serif;max-width:640px;margin:0 auto;padding:1rem;background:#f9f9f9}}
    h1{{color:#c62a88;font-size:1.4rem}}
    table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 8px #0001}}
    th{{background:#c62a88;color:#fff;padding:.6rem;text-align:left;font-size:.85rem}}
    td{{padding:.6rem;border-bottom:1px solid #eee;font-size:.9rem}}
    </style></head><body>
    <h1>&#128202; Raquel Pires Bijoux</h1>
    <p style="color:#888;font-size:.85rem">Últimos 7 dias</p>
    <table>
      <tr><th>Vendedora</th><th>Leads</th><th>Qualif.</th><th>Vendas</th><th>Receita</th><th>Conv.</th></tr>
      {rows if rows else empty_row}
    </table>
    </body></html>
    """
    return HTMLResponse(html)
