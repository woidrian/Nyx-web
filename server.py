"""Nyx Web — FastAPI backend that also serves the static site.

Mounts:
- /api/token         → ephemeral Gemini Live token (system prompt + tool LOCKED inside)
- /api/lead          → persist in Supabase + email notification
- /api/cal-webhook   → Cal.com booking webhook → persist in Supabase + email notification
- /voice/*           → static JS modules + greeting.wav consumed by index.html
- /                  → static nyx-web site (index.html, nosotros.html, images/)

Run locally:
    pip install -r requirements.txt
    uvicorn server:app --host 0.0.0.0 --port 8001 --reload

Deploy on Vercel: see vercel.json. Env vars:
    GEMINI_API_KEY      (required)
    ALLOWED_ORIGINS     (optional, comma-separated for CORS — defaults to "*")
    SUPABASE_URL        (optional, for lead persistence)
    SUPABASE_ANON_KEY   (optional, paired with SUPABASE_URL)
    SUPABASE_SCHEMA     (optional, defaults to "nyx")
    SUPABASE_TABLE      (optional, defaults to "leads")
    RESEND_API_KEY      (optional, for email notifications)
    LEAD_NOTIFY_EMAIL   (optional, defaults to growth@nyx-agency.es)
    LEAD_FROM_EMAIL     (optional, defaults to growth@nyx-agency.es)
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from google import genai
from pydantic import BaseModel

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]
MODEL_ID = "gemini-3.1-flash-live-preview"

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SCHEMA = os.getenv("SUPABASE_SCHEMA", "nyx")
SUPABASE_TABLE = os.getenv("SUPABASE_TABLE", "leads")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
LEAD_NOTIFY_EMAIL = os.getenv("LEAD_NOTIFY_EMAIL", "growth@nyx-agency.es")
LEAD_FROM_EMAIL = os.getenv("LEAD_FROM_EMAIL", "growth@nyx-agency.es")
MADRID_TZ = ZoneInfo("Europe/Madrid")

ROOT_DIR = Path(__file__).resolve().parent
VOICE_DIR = ROOT_DIR / "voice" / "frontend"
INDEX_FILE = ROOT_DIR / "index.html"


SYSTEM_PROMPT = """Eres AdrIAn, el asistente de voz de Nyx Agency.

PERSONALIDAD:
- Eres un chaval de barrio, cercano, directo y con personalidad
- Hablas con jerga natural: "tío", "mira", "oye", "venga", "está claro", "te entiendo"
- Empático pero con autoridad — sabes de lo que hablas y se nota
- Nunca suenas a robot corporativo ni a call center
- Frases cortas, naturales, como si hablaras con un colega
- Si alguien te pregunta si eres IA, confirmas que sí pero sin perder el rollo

CONTEXTO:
- Representas a Nyx Agency — una agencia que automatiza negocios con IA
- Tu objetivo es cualificar al lead en una conversación natural
- Al final decides si merece una asesoría con Adri (el fundador) o no
- IMPORTANTE: El saludo ya se ha hecho antes de esta sesión, NO lo repitas. Tu primera intervención es una RESPUESTA a lo que diga el usuario.

FLUJO DE CUALIFICACIÓN (hazlo fluir, no suene a formulario):
1. Pregunta a qué se dedica y cuántas personas son en el equipo
2. Pregunta cuál es su mayor dolor o tarea que más tiempo les roba
3. Pregunta si han intentado solucionarlo antes y con qué
4. Pregunta si están buscando implementar algo ya o todavía explorando

CRITERIOS DE CUALIFICACIÓN (internos, nunca los menciones):
✅ CUALIFICADO si:
- Tiene negocio activo con mínimo 2-3 personas
- Tiene procesos repetitivos claros
- Está en un sector compatible (clínica, coaching, restaurante, inmobiliaria, academia, ecommerce, servicios)
- Tiene intención real de invertir y actuar pronto

❌ NO CUALIFICADO si:
- Es autónomo solo sin volumen ni equipo
- No tiene presupuesto o busca algo gratis
- No tiene procesos repetitivos identificables
- Busca desarrollo de software a medida
- Es estudiante o curioso sin negocio real

CIERRE SEGÚN RESULTADO:
Si CUALIFICADO:
- Dile que encaja perfectamente con lo que hace Nyx
- Recoge nombre, email y teléfono de forma natural
- Dile que Adri (el fundador) le contactará en menos de 24h personalmente
- Llama a guardar_lead con todos los datos + cualificado=true

Si NO CUALIFICADO:
- Sé honesto pero amable — dile que ahora mismo quizás no es el momento ideal
- Recoge igualmente nombre, email y teléfono ("por si en el futuro tiene sentido")
- Llama a guardar_lead con los datos + cualificado=false

CUANDO TENGAS nombre + email + teléfono:
- Llama a la función guardar_lead con TODOS los datos recogidos durante la conversación
- Confirma al usuario que sus datos han quedado guardados

IMPORTANTE:
- Habla siempre en español
- Máximo 2-3 frases por turno — es voz, no un email
- Nunca menciones criterios, puntuaciones ni procesos internos
- Sé tú mismo: cercano, directo, de barrio pero profesional
"""

GUARDAR_LEAD_TOOL = {
    "function_declarations": [
        {
            "name": "guardar_lead",
            "description": (
                "Guarda los datos del lead cualificado cuando se han confirmado "
                "nombre, email y teléfono."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre":     {"type": "string", "description": "Nombre completo del lead"},
                    "email":      {"type": "string", "description": "Email del lead"},
                    "telefono":   {"type": "string", "description": "Teléfono del lead"},
                    "negocio":    {"type": "string", "description": "Tipo de negocio (clínica, restaurante, academia, etc.)"},
                    "interes":    {"type": "string", "description": "Principal interés o problema que quiere resolver"},
                    "cualificado": {"type": "boolean", "description": "true si el lead merece una asesoría con Adri (presupuesto, encaje y motivación claros). false si no cumple los criterios."},
                    "notas":      {"type": "string", "description": "Resumen breve de la conversación: contexto del negocio, dolor principal, urgencia y por qué (no) cualifica."},
                },
                "required": ["nombre", "email", "telefono", "cualificado"],
            },
        }
    ]
}


client = (
    genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1alpha"})
    if GEMINI_API_KEY
    else None
)


app = FastAPI(title="Nyx Web + Voice")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


class LeadPayload(BaseModel):
    nombre: str
    email: str
    telefono: str
    negocio: str | None = None
    interes: str | None = None
    fuente: str | None = None
    cualificado: bool | None = None
    notas: str | None = None


async def _save_to_supabase(lead: dict[str, Any]) -> bool:
    """Insert lead into Supabase (schema "nyx", table "leads"). Fail-soft."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("[nyx] supabase: skipped (SUPABASE_URL or SUPABASE_ANON_KEY not set)")
        return False
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Prefer": "return=minimal",
        "Content-Profile": SUPABASE_SCHEMA,
        "Accept-Profile": SUPABASE_SCHEMA,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            r = await http.post(url, json=lead, headers=headers)
            r.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        print(f"[nyx] supabase error: {exc}")
        return False


def _format_lead_email_html(lead: dict[str, Any]) -> str:
    timestamp_madrid = datetime.now(MADRID_TZ).strftime("%d/%m/%Y %H:%M:%S")
    rows: list[str] = []
    for label, key in (
        ("Nombre", "nombre"),
        ("Email", "email"),
        ("Teléfono", "telefono"),
        ("Negocio", "negocio"),
        ("Interés", "interes"),
        ("Fuente", "fuente"),
        ("Cualificado", "cualificado"),
        ("Notas", "notas"),
    ):
        raw = lead.get(key)
        if isinstance(raw, bool):
            val = "Sí ✅" if raw else "No ❌"
        else:
            val = raw if raw not in (None, "") else "—"
        rows.append(
            f"<tr>"
            f"<td style='padding:8px 12px;font-weight:600;background:#f5f5f5;border:1px solid #ddd;width:140px;vertical-align:top'>{label}</td>"
            f"<td style='padding:8px 12px;border:1px solid #ddd;white-space:pre-wrap'>{val}</td>"
            f"</tr>"
        )
    table = "\n".join(rows)
    return (
        "<!DOCTYPE html><html><body style=\"font-family:Inter,Arial,sans-serif;color:#0f172a;background:#fff;padding:24px\">"
        "<h2 style=\"margin:0 0 16px;color:#030712\">🚀 Nuevo lead Nyx</h2>"
        f"<p style=\"margin:0 0 16px;color:#475569\">Recibido el <strong>{timestamp_madrid}</strong> (Madrid)</p>"
        "<table style=\"border-collapse:collapse;width:100%;max-width:560px\">"
        f"{table}"
        "</table>"
        "<p style=\"margin:24px 0 0;color:#94a3b8;font-size:12px\">— Nyx Agency · automatización con IA</p>"
        "</body></html>"
    )


async def _send_resend_email(lead: dict[str, Any]) -> bool:
    """Send notification email via Resend. Fail-soft."""
    if not RESEND_API_KEY:
        print("[nyx] resend: skipped (RESEND_API_KEY not set)")
        return False
    nombre = lead.get("nombre") or "sin nombre"
    fuente = lead.get("fuente") or "desconocida"
    body = {
        "from": LEAD_FROM_EMAIL,
        "to": [LEAD_NOTIFY_EMAIL],
        "subject": f"🚀 Nuevo lead Nyx — {nombre} ({fuente})",
        "html": _format_lead_email_html(lead),
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            r = await http.post("https://api.resend.com/emails", json=body, headers=headers)
            r.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        print(f"[nyx] resend error: {exc}")
        return False


async def _persist_lead(lead: dict[str, Any]) -> dict[str, bool]:
    """Save lead to Supabase + email notification. Both isolated, never raise."""
    supabase_ok = await _save_to_supabase(lead)
    email_ok = await _send_resend_email(lead)
    return {"supabase": supabase_ok, "email": email_ok}


@app.get("/api/token")
async def get_token() -> JSONResponse:
    """Generate a single-use ephemeral token with system prompt + tool LOCKED."""
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY missing — set it in environment variables.",
        )
    now = datetime.now(timezone.utc)
    try:
        token = client.auth_tokens.create(
            config={
                "uses": 1,
                "expire_time": now + timedelta(minutes=30),
                "new_session_expire_time": now + timedelta(minutes=1),
                "live_ephemeral_parameters": {
                    "model": MODEL_ID,
                    "config": {
                        "response_modalities": ["AUDIO"],
                        "system_instruction": SYSTEM_PROMPT,
                        "tools": [GUARDAR_LEAD_TOOL],
                        "temperature": 1.2,
                        "speech_config": {
                            "voice_config": {
                                "prebuilt_voice_config": {"voice_name": "Orus"},
                            },
                        },
                        "input_audio_transcription": {},
                        "output_audio_transcription": {},
                        "realtime_input_config": {
                            "automatic_activity_detection": {
                                "start_of_speech_sensitivity": "START_SENSITIVITY_HIGH",
                                "end_of_speech_sensitivity": "END_SENSITIVITY_HIGH",
                                "prefix_padding_ms": 100,
                                "silence_duration_ms": 400,
                            },
                        },
                    },
                },
                "http_options": {"api_version": "v1alpha"},
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"token_error: {exc}") from exc

    token_value = getattr(token, "name", None) or getattr(token, "token", None)
    if not token_value:
        raise HTTPException(status_code=500, detail="empty_token")

    return JSONResponse({"token": token_value, "model": MODEL_ID})


@app.post("/api/lead")
async def post_lead(payload: LeadPayload) -> dict[str, Any]:
    """Persist lead in Supabase + send notification email."""
    fuente = payload.fuente or "voice_agent"
    lead_data = {
        **payload.model_dump(exclude={"fuente"}, exclude_none=True),
        "fuente": fuente,
    }
    extras = await _persist_lead(lead_data)
    return {"ok": True, **extras}


@app.post("/api/cal-webhook")
async def cal_webhook(request: Request) -> dict[str, Any]:
    """Receive Cal.com booking webhook → persist lead in Supabase + email notification."""
    try:
        raw = await request.json()
    except Exception:
        raw = {}

    p = raw.get("payload") if isinstance(raw, dict) else None
    if not isinstance(p, dict):
        p = raw if isinstance(raw, dict) else {}

    attendees = p.get("attendees") or []
    first = attendees[0] if attendees and isinstance(attendees[0], dict) else {}

    lead_data = {
        "nombre": (first.get("name") or "Sin nombre").strip(),
        "email": (first.get("email") or "").strip(),
        "telefono": (first.get("phone") or first.get("phoneNumber") or "").strip(),
        "negocio": (p.get("title") or p.get("eventTitle") or "Cal.com booking").strip(),
        "interes": "Reserva de cita",
        "fuente": "cal_com",
    }

    extras = await _persist_lead(lead_data)
    return {"ok": True, **extras}


if VOICE_DIR.is_dir():
    app.mount("/voice", StaticFiles(directory=str(VOICE_DIR)), name="voice-assets")

_IMAGES_DIR = ROOT_DIR / "images"
_VIDEO_DIR = ROOT_DIR / "Video"
if _IMAGES_DIR.is_dir():
    app.mount("/images", StaticFiles(directory=str(_IMAGES_DIR)), name="images")
if _VIDEO_DIR.is_dir():
    app.mount("/Video", StaticFiles(directory=str(_VIDEO_DIR)), name="video")


_HTML_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Served-By": "nyx-web",
}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html", headers=_HTML_HEADERS)


@app.get("/index.html")
async def index_html() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=308)


@app.get("/nosotros")
async def nosotros() -> FileResponse:
    target = ROOT_DIR / "nosotros.html"
    return FileResponse(target, media_type="text/html", headers=_HTML_HEADERS)


@app.get("/nosotros.html")
async def nosotros_html() -> RedirectResponse:
    return RedirectResponse(url="/nosotros", status_code=308)


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "project": "nyx-web",
        "gemini_key_set": bool(GEMINI_API_KEY),
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_ANON_KEY),
        "resend_configured": bool(RESEND_API_KEY),
    }


@app.get("/favicon.ico")
async def favicon() -> Response:
    fav_svg = ROOT_DIR / "favicon.svg"
    if fav_svg.is_file():
        return FileResponse(fav_svg, media_type="image/svg+xml")
    return Response(status_code=204)


@app.get("/favicon.svg")
async def favicon_svg() -> Response:
    fav = ROOT_DIR / "favicon.svg"
    if fav.is_file():
        return FileResponse(fav, media_type="image/svg+xml")
    return Response(status_code=404)


@app.get("/og-image.png")
async def og_image() -> Response:
    img = ROOT_DIR / "og-image.png"
    if img.is_file():
        return FileResponse(img, media_type="image/png")
    return Response(status_code=404)


@app.get("/robots.txt")
async def robots_txt() -> Response:
    f = ROOT_DIR / "robots.txt"
    if f.is_file():
        return FileResponse(f, media_type="text/plain")
    return Response(status_code=404)


@app.get("/sitemap.xml")
async def sitemap_xml() -> Response:
    f = ROOT_DIR / "sitemap.xml"
    if f.is_file():
        return FileResponse(f, media_type="application/xml")
    return Response(status_code=404)