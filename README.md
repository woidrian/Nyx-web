# Nyx Web

Web corporativa de **Nyx Agency** — agencia de automatización con IA para PYMEs.

🌐 **Producción**: [nyx-agency.es](https://nyx-agency.es)

---

## Stack

- **Frontend**: HTML + CSS + JS vanilla. Three.js (CDN), GSAP (CDN). Sin build step.
- **Backend**: FastAPI (Python) — sirve token efímero Gemini Live + forward de leads a n8n.
- **Voice agent (AdrIAn)**: Gemini 3.1 Flash Live (modelo `gemini-3.1-flash-live-preview`, voz Orus). El browser se conecta directo a Gemini con un token efímero generado por el backend.
- **Hosting**: Vercel (Serverless Functions + CDN edge).

## Estructura

```
nyx-web/
├── api/
│   └── index.py           # Vercel entrypoint (re-exporta server.app)
├── server.py              # FastAPI app (también dev local con uvicorn)
├── vercel.json            # Rewrites + headers
├── requirements.txt       # Deps Python
├── index.html             # Página principal (con voice FAB)
├── nosotros.html          # Quiénes somos (robot 3D)
├── favicon.svg
├── og-image.png
├── robots.txt
├── sitemap.xml
├── images/                # Assets visuales
└── voice/
    └── frontend/          # agent.js, audio.js, geminilive.js, greeting.wav
```

## Endpoints

| Ruta | Método | Descripción |
|---|---|---|
| `/api/token` | GET | Token efímero Gemini Live (system prompt + tool LOCKED) |
| `/api/lead` | POST | Forward de datos del lead al webhook n8n |
| `/healthz` | GET | Diagnóstico |

Todo lo demás (HTML, imágenes, voice/, favicon, etc.) lo sirve Vercel directamente desde la raíz.

## Variables de entorno (Vercel)

| Variable | Requerida | Default |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | — |
| `N8N_WEBHOOK_URL` | ❌ | webhook nyx-voice-lead en n8n |
| `ALLOWED_ORIGINS` | ❌ | `*` |

## Dev local

```bash
cp .env.example .env   # añadir GEMINI_API_KEY real
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
# http://localhost:8001
```

## Contacto

- Email: **growth@nyx-agency.es**
- Reservas: [cal.com/woidrian/nyx-agency](https://cal.com/woidrian/nyx-agency)
