"""Nyx Web — FastAPI backend that also serves the static site.

Mounts:
- /api/token         → ephemeral Gemini Live token (system prompt + tool LOCKED inside)
- /api/lead          → forward lead payload to n8n webhook
- /voice/*           → static JS modules + greeting.wav consumed by index.html
- /                  → static nyx-web site (index.html, nosotros.html, images/)

Run locally:
    pip install -r requirements.txt
    uvicorn server:app --host 0.0.0.0 --port 8001 --reload

Deploy on Vercel: see vercel.json. Env vars:
    GEMINI_API_KEY      (required)
    N8N_WEBHOOK_URL     (optional, defaults to the Nyx n8n webhook)
    ALLOWED_ORIGINS     (optional, comma-separated for CORS — defaults to "*")
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from google import genai
from pydantic import BaseModel

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "https://ai-leedloop-n8n.t64mfz.easypanel.host/webhook/nyx-voice-lead",
)
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]
MODEL_ID = "gemini-3.1-flash-live-preview"

ROOT_DIR = Path(__file__).resolve().parent
VOICE_DIR = ROOT_DIR / "voice" / "frontend"
INDEX_FILE = ROOT_DIR / "index.html"


SYSTEM_PROMPT = """Eres AdrIAn, el asistente de voz de Nyx Agency — una agencia de automatización con IA para PYMEs españolas.

Tu objetivo es cualificar leads de forma natural y conversacional en español.

PERSONALIDAD:
- Cercano y profesional, hablas de tú
- Directo, no das rodeos
- Transmites confianza y expertise en IA

FLUJO DE CONVERSACIÓN:
- IMPORTANTE: Acabas de saludar al usuario y preguntarle por su negocio y su mayor reto operativo (esto ya ha ocurrido antes de esta sesión, NO LO REPITAS). Tu primera intervención aquí debe ser una RESPUESTA a lo que diga el usuario, nunca un saludo inicial.
1. (Saludo + presentación + pregunta inicial — YA HECHO, no repetir)
2. Cuando el usuario te conteste, profundiza en su reto y explica brevemente cómo Nyx puede ayudarles (automatización WhatsApp, agentes IA, n8n)
3. Recoge: nombre completo, email, teléfono, tipo de negocio, interés principal
4. Confirma los datos y despídete indicando que el equipo de Nyx contactará en 24h

CUANDO TENGAS nombre + email + teléfono confirmados:
- Llama a la función guardar_lead con los datos recogidos
- Confirma al usuario que sus datos han sido guardados

IMPORTANTE:
- Habla siempre en español
- Sé conciso en voz (frases cortas, naturales)
- No menciones que eres una IA a menos que te lo pregunten directamente
- Si te preguntan, confirma que eres un asistente IA de Nyx
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
                    "nombre":   {"type": "string", "description": "Nombre completo del lead"},
                    "email":    {"type": "string", "description": "Email del lead"},
                    "telefono": {"type": "string", "description": "Teléfono del lead"},
                    "negocio":  {"type": "string", "description": "Tipo de negocio (clínica, restaurante, academia, etc.)"},
                    "interes":  {"type": "string", "description": "Principal interés o problema que quiere resolver"},
                },
                "required": ["nombre", "email", "telefono"],
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
    """Forward lead data to the n8n webhook."""
    body = {
        **payload.model_dump(exclude_none=True),
        "fuente": "nyx-web-voice",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            r = await http.post(N8N_WEBHOOK_URL, json=body)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"n8n_error: {exc}") from exc
    return {"ok": True}


# Voice frontend assets (agent.js, audio.js, geminilive.js, greeting.wav).
# In Vercel, these are served as static files from /voice/ via vercel.json.
# Local dev with uvicorn keeps these mounts active.
if VOICE_DIR.is_dir():
    app.mount("/voice", StaticFiles(directory=str(VOICE_DIR)), name="voice-assets")

# Static media folders that ship with the site.
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
    """Diagnostic endpoint."""
    return {
        "ok": True,
        "project": "nyx-web",
        "gemini_key_set": bool(GEMINI_API_KEY),
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
