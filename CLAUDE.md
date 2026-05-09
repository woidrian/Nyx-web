# nyx-web — Nyx Agency

## Project Overview
Web corporativa de **Nyx**, agencia de automatización con IA de Adrian Davila.
Proyecto independiente. No relacionado con ARES Fighters ni Paperclip.

Desde 2026-05 el proyecto es **híbrido**: estática (HTML/CSS/JS) + backend FastAPI
en la misma raíz. El backend sirve la web y además expone los endpoints del
voice agent (AdrIAn) para Gemini Live.

## Estructura de archivos
```
nyx-web/
├── index.html            # Página principal (con voice FAB + modal embebido)
├── nosotros.html         # Página Quiénes Somos
├── server.py             # FastAPI: sirve la web + APIs del voice agent
├── Dockerfile            # Build para Easypanel
├── requirements.txt      # Deps Python
├── .env.example          # GEMINI_API_KEY, SUPABASE_*, RESEND_*, ALLOWED_ORIGINS
├── .dockerignore
├── CLAUDE.md
├── images/               # Assets de imagen + Video1.mp4
└── voice/
    └── frontend/
        ├── agent.js      # VoiceAgent (state machine, mic + WS Gemini)
        ├── audio.js      # MicStream (PCM 16k) + PCMPlayer (24k)
        ├── geminilive.js # Cliente WebSocket Gemini Live
        └── greeting.wav  # Saludo inicial pregrabado (voz Orus)
```

## Tech Stack
- **Frontend**: HTML puro + CSS + JS vanilla. Three.js r128 (CDN), GSAP 3.12.2 (CDN). Sin build.
- **Backend voice**: FastAPI + uvicorn. Cliente `google-genai` (Gemini Live, modelo `gemini-3.1-flash-live-preview`, voz Orus).
- **Lead capture**: tool call `guardar_lead` → `POST /api/lead` → persiste en **Supabase** (`nyx.leads`) + envía email con **Resend** a `growth@nyx-agency.es`. n8n retirado el 2026-05-09.
- **Cal.com webhook**: `POST /api/cal-webhook` recibe bookings de Cal.com y los persiste con la misma plumbing (Supabase + Resend), con `fuente="cal_com"`.

## Páginas

### index.html
Página principal con secciones:
1. Hero — badge, h1, métricas x4, CTA Cal.com
2. Servicios (s2) — 3 cards stack v2 (Auditoría de IA / Desarrollo de Sistemas / Capacitación)
3. Proceso (s3) — 4 pasos
4. Casos (s4) — galería
5. Casos de uso (s5) — 3 cards
6. Precios (s6) — Starter 499€ / Growth 1.299€ / Scale 1.998€ + toggle mensual/anual (-15%)
7. FAQ (s7) — 5 preguntas acordeón
8. CTA final (s8) — Cal.com
9. Footer — copyright + Política de Privacidad (modal)

**Servicios v2 (sección 002)** — Editorial Brutalism integrado con paleta navy:
- Stack vertical de 3 filas. Cada fila = 1 card sobre `#070d1c`, separadas por hairlines de 1px
- Tags: borde + texto `var(--muted)` con `var(--bmd)` (mismo estilo que `hero-badge`)
- Número grande: `#1a2030` en reposo → `var(--text)` (blanco) en hover (con flecha→)
- CTA pill (SCAN/BUILD/ADOPT): bg `var(--text)` blanco, texto `var(--bg)` navy. Hover: `opacity: .88` (igual que `.btn-fill`).
- CSS scopeado bajo `.svc-v2`. Tokens locales: `--nyx-deep:#070d1c`, `--nyx-accent:#f1f5f9`, `--nyx-line:rgba(241,245,249,.09)`

Funcionalidades añadidas:
- **Voice FAB "Habla con AdrIAn"** — píldora flotante abajo-derecha (`#voice-fab`) con punto pulsante lime. Abre el modal `#voice-overlay` que carga `voice/agent.js` la primera vez (lazy import dinámico). Cierra con X, click fuera o Escape. El mic + WebSocket se cortan al cerrar (`agent.stop()`) pero la instancia se reutiliza si vuelves a abrir.
- **Selector de idioma** — 12 idiomas (es/en/pt/fr/de/it/nl/ru/zh/ja/ko/ar), RTL para árabe, persiste en localStorage
- **Scroll-to-top** — botón circular abajo-derecha (offset right: 2rem; el voice FAB queda a 5rem)
- **Modal Política de Privacidad** — cierra con X, clic fuera, o Escape
- **Toggle precios mensual/anual** — muestra precios con -15% descuento

### nosotros.html
Página Quiénes Somos. Mismo i18n + scroll-to-top + modal privacidad. **Sin** voice FAB (de momento).

## Voice Agent (AdrIAn)

### Endpoints
- `GET  /api/token`       → token efímero Gemini Live (system prompt + tool **lock dentro del token** por seguridad)
- `POST /api/lead`        → persiste lead en Supabase (`nyx.leads`) + envía email con Resend
- `POST /api/cal-webhook` → recibe booking de Cal.com → mismo pipeline (Supabase + Resend) con `fuente="cal_com"`
- `POST /twiml/asistente` → TwiML para integración telefónica Twilio (opcional)
- `WS   /media-stream`    → bridge Twilio Media Stream ↔ Gemini Live (opcional)
- `GET  /voice/*`         → assets estáticos del frontend de voz
- `GET  /`                → resto del site (`index.html`, `nosotros.html`, `images/`)

### Frontend (modal embebido en index.html)
- `voice/frontend/agent.js` exporta `VoiceAgent`. Se importa con `import('/voice/agent.js?v=...')` la primera vez que el usuario abre el modal.
- Estados: `idle | connecting | listening | speaking | ended | error` aplicados al `data-state` del `.voice-modal` (CSS scopeado, no afecta resto del site).
- Saludo inicial: `voice/frontend/greeting.wav` (voz Orus, mismo modelo que Live → continuidad sonora). Mientras suena, el mic queda mute (`_micGateOpen=false`) hasta que el WS termine de conectar.
- Lead capture: cuando AdrIAn llama `guardar_lead`, el frontend hace `POST /api/lead` y marca `_leadSaved=true`. Cuando termina la despedida, cierra automáticamente.

## Despliegue (Easypanel)

### Opción A — Backend + web en un único servicio (default actual)
1. Push a Git, conectar Easypanel a la rama `main`.
2. Build con `Dockerfile` de la raíz. Easypanel detecta el `EXPOSE 8000`.
3. Variables de entorno en Easypanel:
   - `GEMINI_API_KEY` (obligatoria)
   - `SUPABASE_URL` + `SUPABASE_ANON_KEY` (opcionales, sin ellas no se persiste el lead)
   - `SUPABASE_SCHEMA` (opcional, default `nyx`) + `SUPABASE_TABLE` (opcional, default `leads`)
   - `RESEND_API_KEY` (opcional, sin ella no se envía email)
   - `LEAD_NOTIFY_EMAIL` (opcional, default `growth@nyx-agency.es`) + `LEAD_FROM_EMAIL` (opcional, default `growth@nyx-agency.es`)
   - `ALLOWED_ORIGINS=*` (opcional, default `*`)
4. Dominio: `nyx-agency.es` apuntando al servicio. La web carga directamente `/api/token` y `/voice/agent.js` desde el mismo origen — no hace falta CORS ni configuración extra.

### Opción B — Voice backend como servicio separado
Si en algún momento quieres servir la web estáticamente (Vercel/Netlify) y dejar solo el voice backend en Easypanel:
1. Subir solo `server.py`, `voice/`, `Dockerfile`, `requirements.txt` a un repo aparte (o usar este mismo).
2. Desplegar en Easypanel con dominio `voice.nyx-agency.es`. Set `ALLOWED_ORIGINS=https://nyx-agency.es,https://www.nyx-agency.es`.
3. En `index.html`, cambiar las URLs en el script del modal y en `agent.js`:
   - `import('/voice/agent.js')` → `import('https://voice.nyx-agency.es/voice/agent.js')`
   - `fetch('/api/token')` → `fetch('https://voice.nyx-agency.es/api/token')`
   - `fetch('/api/lead', ...)` → idem
   - `new Audio('/voice/greeting.wav?...')` → `new Audio('https://voice.nyx-agency.es/voice/greeting.wav?...')`
4. La web en Vercel/Netlify queda 100% estática.

## Commands
```bash
# Modo solo-estático (sin voice agent funcionando)
cmd.exe /c "start C:\Dev\nyx-web\index.html"

# Modo completo local (web + voice agent funcionando)
cd /c/Dev/nyx-web
cp .env.example .env   # añadir GEMINI_API_KEY real
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
# → http://localhost:8001
# (puerto 8001 en local para evitar conflictos con procesos legacy en 8000)

# Diagnóstico — confirma que el server respondiendo es el de nyx-web
curl http://localhost:8001/healthz
# → {"ok":true,"project":"nyx-web","root":"C:\\Dev\\nyx-web",...}

# Docker local
docker build -t nyx-web .
docker run -p 8000:8000 --env-file .env nyx-web
```

## Contacto
- Email: **growth@nyx-agency.es**
- Reservas: **https://cal.com/woidrian/nyx-agency** (todos los CTAs apuntan aquí)
- WhatsApp: retirado de la web (los iconos SVG `.btn-wa` siguen presentes pero los `href` ya van a Cal.com — pendiente cambiarlos por icono de calendario si se quiere coherencia visual)

## Key Conventions
- Español en UI, inglés en código
- i18n DOM-based: getElementById + querySelectorAll por índice
- Sin cookies, sin tracking, sin analytics
- Precios: siempre actualizar HTML + JS (objeto LANGS) en paralelo
- **Voice modal IDs reservados** (no reutilizar en el resto del DOM): `mic-btn`, `status`, `transcript`, `viz`, `end-btn`, `restart-btn`. Todos viven dentro de `.voice-modal` y son referenciados por `agent.js` mediante `root.querySelector(...)`.

## Brand / Identidad
- Agencia: Nyx
- Foco: Automatización con IA
- Paleta site: `--bg:#030712` (dark navy), `--bg2:#070d1c`, `--text:#f1f5f9`, `--muted:#64748b`
- Paleta servicios v2 (sección 002): `--nyx-deep:#070d1c` + `--nyx-accent:#f1f5f9` (alineada con el site)
- **Paleta voice agent (modal + FAB)**: fondo `#0a0a0a`/`#111111`, accent `#c8ff00` (lime). Antes era exclusiva del voice agent — desde 2026-05-05 también se usa en el icono de calendario del nav (puntos pulsantes + glow). Ninguna otra sección la usa.
- Tipografía: Space Grotesk 600/700 (h2/títulos generales), Inter 300/400/500 (body), **Syne 400/500/600/700/800** (servicios v2 + voice modal), **JetBrains Mono 300/400** (status pills + footer del voice modal)
- Convenciones de color:
  - Lime `#c8ff00` SOLO en voice agent (FAB + modal) y en los iconos 3D del nav/CTAs (calendario, chevron-back). Ninguna otra sección lo usa.
  - Texto blanco puro `#ffffff` reservado a títulos hero-like; resto usa `--text` (#f1f5f9)
  - Descripciones siempre `var(--muted)` para coherencia inter-secciones

---

## Changelog 2026-05-05 — Sesión de UI cleanup + iconos 3D

### Nav: "Hablemos →" → icono calendario 3D animado
- `<a class="nav-cta" id="nav-cta">` ahora contiene un **SVG inline** del calendario "appointment-schedule" (estilo Lordicon `wired/outline 973`, recreado en SVG inline para no depender de hashes externos).
- **3D**: `perspective(160px) rotateX(10deg) rotateY(-10deg)`, hover endereza + scale 1.12.
- **Animaciones constantes**:
  - `calGlow` (2.8s) — pulsa el `drop-shadow` lime alrededor del icono.
  - `calDot` (2.4s, escalonada por `.d1`–`.d6`) — los 6 dots del grid pulsan en cascada.
  - `calPlus` (1.8s) + `calPing` (2s) — el badge "+" lime escala y emite un ping radar.
- Click → `https://cal.com/woidrian/nyx-agency` (target `_blank`).
- i18n: el `aria-label` se traduce con `t.nav.cta` en los 12 idiomas (en lugar de `textContent`, ya que ahora el `<a>` no tiene texto).
- Aplicado en **index.html** y **nosotros.html**.

### Nosotros · Hero "← Volver al inicio" → icono chevron-3D animado
- `<a class="hero-back-3d" id="hero-cta" href="index.html">` con **SVG inline** de 3 chevrons left con jerarquía visual (blanco puro stroke 2.6 → gris claro stroke 2.4 → gris medio stroke 2.2).
- **3D**: `perspective(220px) rotateX(14deg) rotateY(18deg)` + dual `drop-shadow` (sombra negra para profundidad + glow lime).
- Animación `chevPoint` (1.6s, delays escalonados 0/0.12/0.24s) — los 3 chevrons hacen slide-left de 5px en cascada (efecto "pointing" de Lordicon en bucle).
- Hover: endereza la perspectiva, scale 1.08, translateX -4px, animación a 1s, glow lime intensificado.
- Respeta `prefers-reduced-motion`.

### Nosotros · CTA "¿Trabajamos juntos?"
- **Eliminado** el botón `← Volver a la web` (anchor `#cta-back` borrado del HTML + del JS de i18n).
- Calendario dentro de `.btn-wa` actualizado al estilo **bolder Lordicon 28-calendar** (calendario con un "1" dibujado dentro, strokes 2.4-2.6).
- Icono con perspectiva 3D `rotateX(14deg) rotateY(-14deg)` + dual `drop-shadow`. Hover endereza y escala 1.08. Sin background propio (transparente sobre el botón blanco). El texto "Agenda tu cita" sigue activo y traducido (`#cta-wa-btn` → `t.cta.wa`).

### Hero index — borrado del badge "001 · Automatización con IA"
- Eliminado `<span class="hero-badge" id="hb">` del HTML + de la timeline GSAP (`#hh` ahora abre la entrada secuencial) + de `setLanguage`.

### Eyebrows/badges de sección — ocultos globalmente
- Añadido a ambas páginas: `.eyebrow, .hero-badge { display: none !important; }`.
- Cubre:
  - **index.html**: 002 Servicios, 003 Agentes, 004 Proceso, 005 Stack tecnológico, 006 Casos de éxito, 006A Beneficios, 006B Diferenciación, 007 Precios, 009 Contacto.
  - **nosotros.html**: hero badge "Quiénes somos · Nyx Agency", 01 Nuestra historia, 02 Valores, 03 El equipo.
- **Decisión deliberada**: `display: none` en CSS en lugar de borrar el HTML para que `getElementById('s2-eyebrow')` etc. en `setLanguage` sigan funcionando (no rompe i18n, solo oculta visualmente). El HTML se puede eliminar después si se quiere limpieza definitiva.

### Footer (ambas páginas, 12 idiomas)
- Borrado: span `#footer-copy2` "Hecho con IA. Operado por humanos." + su línea en `setLanguage`. Las claves `c2` siguen en el LANGS object como código muerto inofensivo.
- Cambiado `c1` (12 idiomas): "© 2026 Nyx. Automatización con IA." → "© 2026 Nyx. Todos los derechos reservados.":
  - es: Todos los derechos reservados / en: All rights reserved / pt: Todos os direitos reservados / fr: Tous droits réservés / de: Alle Rechte vorbehalten / it: Tutti i diritti riservati / nl: Alle rechten voorbehouden / ru: Все права защищены / zh: 版权所有 / ja: 全著作権所有 / ko: 모든 권리 보유 / ar: جميع الحقوق محفوظة.

### Modales legales — Privacy + T&C
- **Botones del footer mantenidos** (`#privacy-btn` y `#tc-btn`) — siguen abriendo los modales.
- **Vaciado el contenido** de `<div class="pm-body">` y `<div class="tcm-body">` en ambas páginas (sólo el cuerpo, header con título y X de cerrar permanecen).
- Pendiente: rellenar el contenido cuando se quiera.

### i18n — Auditoría pendiente para mañana
**Identificadas secciones con texto hardcodeado en español que NO se traduce al cambiar de idioma**:
- `.footer-nav` (5 links): Servicios/Proceso/Casos/Precios/Nosotros (index) y Servicios/Casos/Precios/Inicio (nosotros).
- **#servicios** — los `.svc-tag` (Discovery, ROI, Plan 90 días, Agentes IA, Automations, A medida, Knowledge transfer, Sin dependencia, Criterio propio).
- **#agentes** — todo el contenido: heading, 6 dep-cards × 5 items + 4 dep-stats (~40 strings).
- **#proceso** — los 4 `.step-h`/`.step-p` (los datos están en `LANGS.s3.steps` pero no están wired al DOM).
- **#casos** — 3 caso-cards (sector + heading + paragraph + 3 metrics).
- **#beneficios** — `.bnf-idle-text` + 5 etiquetas de nodo + datos del panel activo.
- **#diferenciacion** — 6 celdas comparativas (label "Otros"/"Nyx" + h + p).
- **#precios** — toggle "Mensual"/"Anual", 3 plan tiers, todas las features list, notas, CTAs.
- En **nosotros.html**: footer-nav + posibles textos no marcados con id.

**Plan propuesto** (por discutir mañana):
- Patrón `data-i18n="seccion.clave"` con un walker genérico añadido a `setLanguage`:
  ```js
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = key.split('.').reduce((o,k) => o?.[k], LANGS[code]?.t || {});
    if (val != null) el.innerHTML = val;
  });
  ```
- Añadir un objeto `t: { ... }` flat per-language en `LANGS` con todas las traducciones nuevas.
- Anotar el HTML con `data-i18n=...`.
- Estimación: ~80 strings nuevos × 12 idiomas ≈ 1000 traducciones. Hacer en fases (Agentes + Precios + Proceso + Footer-nav primero, resto después).

### Estado actual i18n (pre-fix)
Sí están traducidos: nav (services/process/cases/pricing/about/cta), hero h1/sub/metrics, s2 cards (h+p), s3 título+párrafo (no los pasos), s4 título+párrafo, s5 título+párrafo + cases array, s6 título+párrafo+toggle text+plans array, s8 (h+p+cta), footer-copy1, hero-cta aria-label en nosotros.

---

## Changelog 2026-05-06 — i18n masivo + nav compact pill + voice agent en nosotros + sección equipo robot 3D

### Server fix
- **Bug Unicode cp1252 (Windows)**: `server.py` reventaba al imprimir `→`. Reemplazado por `->` ASCII en los `print(...)` de arranque (líneas ~434, 440, 447). Ahora `uvicorn server:app --port 8001 --reload` arranca limpio.

### i18n masivo — walker genérico `data-i18n`
- Implementado en **ambas páginas** el walker que se discutió ayer:
  ```js
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = key.split('.').reduce((o,k) => o?.[k], LANGS[code]?.t || {});
    if (val != null) el.innerHTML = val;
  });
  ```
- Añadido objeto `t: { ... }` per-language en `LANGS` con las nuevas claves: `agentes`, `bnf`, `s2.tags`, `footerNav`, `footerLegal`, `equipo`, etc.
- HTML anotado con `data-i18n="..."` en ~60 elementos: `.svc-tag`, `#agentes` completo (heading + 6 dep-cards + 4 dep-stats), `.footer-nav`, `.bnf-*`, etc.
- **Total**: ~720 traducciones nuevas wired (~60 strings × 12 idiomas).
- **Pendiente todavía**: casos metrics labels (3×3), voice modal, diferenciación, pricing notes/features detail.

### Nav compact pill mode (scroll)
- En ambas páginas, al scrollear el nav pasa de `width:100%` a una **pill centrada** flotando en el medio:
  ```css
  #nav { position:fixed; top:0; left:0; right:0; margin:0 auto; max-width:100%;
         transition: top .5s, max-width .5s, padding .4s, background .35s, ...; }
  #nav.compact {
    top: 1rem;
    max-width: min(900px, calc(100% - 2rem));
    background: rgba(3,7,18,.78);
    backdrop-filter: blur(18px) saturate(140%);
    border-radius: 999px;
  }
  ```
- **Decisión clave**: animar `max-width` (no `left/right/transform`) porque los valores `auto` no se interpolan y producían un salto visual brusco.
- Toggle vía un segundo `ScrollTrigger` con `start:'top -70vh'` que hace `nav.classList.toggle('compact', self.isActive)`.

### nosotros.html · Nav: añadidos "Inicio" y "Proceso"
- Antes solo tenía Servicios/Casos/Precios. Ahora tiene **Inicio** (primer link, `href="index.html"`) + **Proceso** (apunta a `index.html#proceso`).
- Recuperado el icono chevron-3D animado en el hero para volver al inicio (que se había perdido en una iteración intermedia).
- Añadidas claves `nav.home` y `nav.process` a los 12 idiomas + wired vía `data-i18n`.

### nosotros.html · Voice agent (AdrIAn) portado
- Antes el voice FAB + modal solo existía en `index.html`. Ahora también está en `nosotros.html`.
- Copiados: CSS scopeado bajo `.voice-modal` y `#voice-fab`, HTML del modal (`#voice-overlay`), wiring del lazy import dinámico (`import('/voice/agent.js?v=...')`), gestión de cierre (X / Escape / click fuera) que invoca `agent.stop()`.
- Añadidas las fonts **Syne** y **JetBrains Mono** al `<link>` de Google Fonts (eran exclusivas de index hasta ahora).

### Sección "El equipo" — evolución larga hasta robot Three.js
Iteraciones (en orden):
1. **Video** original → reemplazado por imagen `YOPANIME.jpg` (con `mix-blend-mode: multiply` para quitar fondo blanco).
2. Imagen actualizada a `YOPANIME.png` (transparente). Quitado `mix-blend-mode`, añadido `drop-shadow` para profundidad 3D.
3. Añadida **lámpara dibujada en SVG** encima del personaje, con animación de luz cálida.
4. Reemplazado todo el bloque por **Spline 3D** (robot importado desde `spline-viewer`).
5. Quitado Spline (incluyendo el watermark "Built with Spline"). Sustituido por **vanilla Three.js** que recrea el mismo robot manualmente.

**Estado final actual** — Three.js robot custom:
- Importmap: `"three": "https://unpkg.com/three@0.160.0/build/three.module.js"`.
- Cuerpo: `ExtrudeGeometry` con shape redondeada (bw 1.85, bh 1.18, br 0.22) + bevels suaves.
- Pantalla con `CanvasTexture` (gradiente radial púrpura→magenta).
- Ojos: `SphereGeometry` con `MeshPhysicalMaterial` (clearcoat 1.0).
- Cuello: cilindro con forma de embudo + cilindro fino.
- **Plataforma** debajo del cuerpo: `BoxGeometry(1.55, 0.72, 1.0)` en `position.y = -1.45`. Con plano de glow púrpura por debajo (`additive blending`).
- **Sub-grupo `head`**: el cuerpo + pantalla + ojos viven en un `THREE.Group()` separado de la plataforma. La plataforma queda fija; solo la cabeza rota con el ratón.
- **Mouse tracking** (corregido tras varias iteraciones):
  ```js
  // Usar bounds del wrap, NO window.innerWidth/Height
  const r = wrap.getBoundingClientRect();
  const dx = (clientX - centerX) / (r.width / 2);
  targetRY = clampedDx * 0.7;   // ±40° yaw
  targetRX = -clampedDy * 0.4;  // ±23° pitch
  // Aplicado solo a head, no al robot completo:
  head.rotation.y += (targetRY - head.rotation.y) * 0.09;
  head.rotation.x += (targetRX - head.rotation.x) * 0.09;
  ```
- Cámara alejada para que el robot se vea pequeño: `position.set(0, 0.4, 11.5)`, FOV 26°, `robot.scale.setScalar(0.78)`.

### Sección "El equipo" — capa de texto morphing
- Componente vanilla portado de **21st.dev liquid-text** sobre la pantalla del robot.
- Textos en rotación: `['Construyo','Automatizo','Diseño','Optimizo','Resuelvo','Entrego']`.
- Dos `<span>` apilados (`.morph-1` y `.morph-2`) con `filter: url(#morph-threshold) blur(.6px)` — efecto de fundido líquido.
- SVG `<feColorMatrix>` con threshold como filtro de morph, `morphTime=1.5s`, `cooldownTime=0.5s`. Cada span recibe blur+opacity dinámicos.
- El texto va **detrás** del robot (z-index) pero visible.

### Sección "El equipo" — fade visual a sección siguiente
- `.equipo-robot-wrap` con CSS mask:
  ```css
  mask-image: linear-gradient(to bottom, black 0%, black 78%, transparent 100%);
  ```
- La plataforma del robot se difumina hacia la sección de abajo en lugar de cortar bruscamente.

### Sección "El equipo" — limpieza visual
- **Borrado** el `<h2>` "La persona detrás de Nyx." del HTML (último cambio del día). La eyebrow "03 · El equipo" se mantiene (oculta globalmente vía `display:none` del cambio del 2026-05-05, pero el span sigue en el DOM para no romper i18n).
- Resultado: la sección equipo es ahora **solo** el robot 3D + el morph text. Limpio y minimalista.

### Bugs fix durante la sesión
- **`founder-role` getElementById null**: `setLanguage` abortaba completo al hacer `.textContent` sobre un elemento que ya no existía (era class, no id, después de un redesign). Añadidos `if (el)` defensivos en todos los accesos por id de la sección equipo (`founder-role`, `bio-h`, `bio-p1/2/3`).
- **Cache aggressive**: varias veces el usuario tuvo que hacer Ctrl+F5 / hard refresh porque los cambios CSS no aparecían — recordatorio para el futuro.

### Estado i18n actualizado (post-2026-05-06)
**Wired** (todo se traduce):
- nav completo (incluido `nav.home` y `nav.process` en nosotros), hero h1/sub/metrics, s2 cards (h+p) + tags, s3 (título + párrafo + 4 pasos), s4 (título+párrafo), s5 (título+párrafo + cases), s6 (título+párrafo+toggle+plans), s8 (h+p+cta), footer (copy1 + footer-nav + footerLegal), hero-cta aria-label, agentes completo (~40 strings), beneficios (`.bnf-*`), equipo (eyebrow).

**Pendiente** (todavía hardcodeado en español):
- Casos metrics labels (3 cards × 3 metrics = 9 labels)
- Voice modal (estados + textos del UI)
- Diferenciación (6 celdas: label "Otros"/"Nyx" + h + p)
- Pricing notes y features detail (más allá de los 3 plan names)

---

## Changelog 2026-05-07 — Sesión maratón: SEO, deletes, casos v2, mobile responsive overhaul

### 1. SEO & assets — preparar la web para producción
**Archivos nuevos en raíz**:
- `favicon.svg` (304B vectorial) — N estilizada con punto lime accent sobre cuadrado navy. Escala perfecto a cualquier DPI.
- `og-image.png` (39KB, 1200×630) — generado con PIL: navy + glow sutil + "Nyx" titular grande + accent lime line + "Automatización con IA · para PYMEs" + URL footer. Para preview de WhatsApp/LinkedIn/Twitter.
- `robots.txt` — `Allow: /`, `Disallow: /api/, /twiml/, /twilio/, /media-stream`, `Sitemap: https://nyx-agency.es/sitemap.xml`
- `sitemap.xml` — `/` (priority 1.0, weekly) + `/nosotros.html` (0.8, monthly)

**HTML — meta tags añadidos en ambas páginas**:
- `<link rel="canonical">` apuntando a la URL absoluta
- `<link rel="icon" type="image/svg+xml" href="/favicon.svg">` + apple-touch-icon
- 8 meta `og:*` (title, description, type, url, image, image:width/height, locale, site_name)
- 4 meta `twitter:*` (card=summary_large_image, title, description, image)
- En `index.html`: bloque `<script type="application/ld+json">` con schema `ProfessionalService` (founder Adrian Davila, areaServed España, email growth@nyx-agency.es, serviceType array, sameAs Cal.com)

**`server.py` — 5 rutas nuevas** para servir los assets en raíz: `/favicon.svg`, `/favicon.ico` (alias→svg), `/og-image.png`, `/robots.txt`, `/sitemap.xml`. Todas con FileResponse + media_type correcto.

### 2. Decisión de despliegue: Easypanel sí, Vercel NO (por ahora)
**Bloqueador técnico**: el voice telefónico Twilio usa WebSocket (`/media-stream`) y Vercel Serverless **no soporta WebSockets**. El voice del FAB en la web sí podría funcionar en Vercel (usa token efímero + Gemini Live directo desde browser), pero el split entre web estática + voice backend complica la arquitectura.

**Recomendación documentada**: Easypanel + dominio `nyx-agency.es`. La web ya está dockerizada y probada. Compra dominio + apuntar A record + Let's Encrypt automático. Tiempo total ~30 min.

### 3. Secciones eliminadas (focus + simplificación)

#### Sección de Precios (007 PRECIOS) — borrada completa
- Sección HTML completa (toggle mensual/anual + 3 cards Starter/Growth/Scale)
- CSS bloque "006 PRECIOS" + 3 reglas responsive + bloque media query 600px específico (~250 líneas CSS total)
- Link Precios en nav principal + footer-nav (en index + nosotros)
- IIFE completo del Electric Border canvas animation (114 líneas — solo se usaba aquí, ahora código muerto)
- IIFE del toggle pricing
- Bloque `// Section 6` del JS i18n (8 referencias DOM a `s6.*` + plans loop)
- Línea `getElementById("nav-pricing")` en `setLanguage` (en ambas páginas)

**Quedó como código muerto inocuo**: claves `s6` y `nav.pricing`/`footerNav.pricing` en `LANGS` de los 12 idiomas. El walker `data-i18n` ignora claves cuyos elementos no existen.

#### Sección Agentes "27 especialistas. Una sola factura." — borrada
- Bloque CSS completo "003 AGENTES / DEPARTAMENTOS" (`.dep-grid`, `.dep-card`, `.dep-head`, `.dep-name`, `.dep-badge`, `.dep-list`, `.dep-stat` + 3 media queries)
- Sección HTML completa: heading "27 especialistas" + 6 dep-cards (Ventas, Marketing, Atención, Admin, RRHH, Dirección) con 27 items + 4 dep-stats finales
- `<hr class="sec-divider">` que la precedía

**Quedaron como código muerto inocuo**: claves `agentes.*` en `LANGS` (12 idiomas).

### 4. Sección "Casos" rediseñada — Empresas que ya operan diferente

**Antes**: 3 caso-cards con métricas individuales tipo (Fitness +240% / Salud −80% / Comercio −60%).

**Ahora — replica adaptada del modelo 21st.dev "Resultados reales"**:
- **Header centrado**: eyebrow `RESULTADOS REALES` púrpura `#a78bfa` (letter-spacing .24em) + h2 "Empresas que ya **operan diferente.**" (segunda línea en accent púrpura)
- **3 stats agregados** (`.casos-v2-stats` grid 3 cols): `+40%` eficiencia operativa / `−60%` tareas repetitivas / `3×` capacidad atención. Caja con borde púrpura sutil + glow radial. Cada stat con dot pulsante púrpura arriba a la izquierda.
- **Stack de 3 testimonials en abanico** (`.casos-v2-stack`): card frente sin rotar + back1 rotada `+5°` con blur leve + back2 rotada `−7°` con blur mayor. Avatares circulares blancos con halo púrpura.

**Marcas inventadas (logos SVG inline)** — testimonios ficticios con copy genérico:
- **PULSEFIT** (front): pulso cardíaco horizontal estilizado. Testimonio: Carlos Méndez — Director Comercial en Pulsefit
- **LUMEA Clinic** (back1): luna creciente. Testimonio: Laura Bermejo — Coordinadora en Lumea Clinic
- **NORDIKA** (back2): silueta de montañas + sol. Testimonio: Daniel Ortega — Founder de Nordika

⚠️ **Disclaimer pendiente**: las 3 marcas son completamente ficticias. Antes de producción **validar** que no chocan con marcas reales registradas en España.

**Cards más estrechas**: `max-width: 580px` → `420px` (formato tarjeta vertical), padding interno `3rem 2rem`, quote font `1rem` con max-width 320px.

**i18n cleanup**: borrado el bloque `// Section 5` del JS porque el nuevo h2 con `<br>` y `<span class="accent">` no encajaba con `t.s5.h2`. La sección queda hardcoded en español por ahora.

### 5. Cards arrastrables (swipe-deck manual con Pointer Events)

**Implementación**:
- Drag con `pointerdown` + `setPointerCapture` para no perder el evento si el cursor sale de la card
- `pointermove` actualiza `transform: translate(dx, dy*0.4) rotate(dx*0.06deg)` + opacity fade según distancia
- `pointerup`/`pointercancel`: si `|dx| > 110px` → fly-out (450ms hacia el lado del swipe + 28° rotación) y reorder al fondo del stack. Si no, snap-back (320ms).
- Bloqueo `animating` durante anim para no encadenar drags rotos
- `touch-action: none` en `.csv2-card-front` impide scroll vertical accidental
- `pointer-events: none` en hijos (avatar/quote/author) → click siempre captura la card padre

**Bug "drag pegado" — root cause + fix iterativo**:
- **V1 bug**: en snap-back, el `setTimeout` chequeaba `if (dragCard)` pero `dragCard` ya había sido seteado a `null` justo después → la clase `csv2-flying` (con transition activa) NO se quitaba nunca → siguiente drag se animaba en vez de seguir el cursor.
- **V2 fix**: capturar `const card = dragCard` en variable local antes del setTimeout. Bloqueo `animating = true` también en snap-back. Limpieza de transform/opacity inline al final.
- **V3 (final) — rewrite robusto**:
  - Tracking de `pointerId` en módulo: `onMove`/`onUp` filtran por id (multi-touch safe)
  - `clearGlobalListeners()` quita los 3 listeners (`pointermove`, `pointerup`, `pointercancel`) **siempre**, sin depender del `{ once: true }` que dejaba zombies
  - `onDown` llama a `clearGlobalListeners()` antes de registrar nuevos → mata zombies de drags abortados
  - `releasePointerCapture` explícito en up
  - Guard `animating || dragging` en onDown
  - Reset completo en early-return de onUp

**Hint UX visible y persistente**:
- Pill con borde púrpura sólido (`rgba(167,139,250,.45)`), fondo `rgba(11,8,24,.92)`, texto en accent
- 2 flechas blancas a los lados (← Arrastra para ver más →) con animación slide-out de 1.6s en bucle
- Halo pulsante box-shadow púrpura (2.6s)
- Posicionado a `bottom: -3.25rem` del stack
- **Persiste siempre** — no se oculta tras swipe (UX explícita por petición del user)

### 6. Tecnologías mobile — Slider de logos con progressive blur

**Solo en mobile** (`@media max-width: 720px`): los 2 carruseles desktop de chips se ocultan. En su lugar aparece un slider compacto:
- Container 90px alto, **sin background ni border** (totalmente integrado en la sección)
- 10 logos en bucle infinito (Claude AI, n8n, Supabase, OpenAI, WhatsApp, Stripe, Make, Notion, HubSpot, Twilio) — animación 18s linear infinite
- Cada logo: dot gris muted + nombre en `.92rem` Inter Medium
- **Progressive blur en bordes laterales** (4 layers apilados estilo `motion-primitives/progressive-blur`):
  - Layer 1: blur `0.5px`, mask 0→50%
  - Layer 2: blur `1.5px`, mask 0→35%
  - Layer 3: blur `3px`, mask 0→22%
  - Layer 4: blur `5px`, mask 0→12%

  Cero JS extra, solo CSS `backdrop-filter` + `mask-image`.

**Iteración descartada**: primera versión tenía sparkles canvas + horizonte púrpura curvo + glow radial púrpura (estilo modelo 21st.dev "clients"). El usuario pidió simplificar → quitar background, dejar solo logos + blur edges.

### 7. Responsive overhaul masivo — layouts horizontales mantenidos en mobile

**Filosofía aplicada por petición del usuario**: las secciones que en desktop están "lado a lado" deben mantener ese layout en mobile (no colapsar a 1 columna). Solo compactar tamaños/padding.

**Forzados a multi-columna SIEMPRE en mobile** (antes colapsaban a 1 col):

| Sección | Antes mobile | Ahora mobile |
|---|---|---|
| Hero metrics (4 stats) | 4→2→1 col | **4 cols siempre** + clamp font-size + padding compactado |
| Casos · 3 stats agregados | 1 col | **3 cols siempre** (font 1.75→1.4rem, dot 4-5px) |
| Proceso (4 pasos) | 1 col | **2×2 grid encuadrado** (con bordes hairline + radius) |
| Diferenciación (Otros vs Nyx) | 1 col | **2 cols siempre** (padding compactado) |
| Historia (nosotros) | 2→1 col en 800px | desktop 2 cols, **mobile apila correctamente** (texto arriba, stats 2×2 abajo) |
| Valores 3 cards (nosotros) | 2+1 layout (2 arriba, 1 sola abajo) | **3 cols SIEMPRE** (en línea) |
| Servicios sticky scroll | 1 col en 880px | **rail+panel 2 cols siempre** con sticky activo (rail 84-64px en mobile, IntersectionObserver sincroniza el item activo) |

**Anti-cortes globales**: aplicado en `body` de ambas páginas: `hyphens: none`, `-webkit-hyphens: none`, `overflow-wrap: break-word`, `word-break: normal`. Palabras siempre enteras, sin guiones automáticos extraños. Re-aplicado a nivel de elemento en `.cmp-cell`, `.step`, `.valor-card`, `.stat-item`, `.historia-text`.

**Breakpoints añadidos donde faltaban**:
- Casos v2: 720px refinado, **480px nuevo**, **360px nuevo**
- Stack testimonials: 720px (height 360, max-width 88%) → 480px (height 340, padding compactado, hint reposicionado) → 360px (rotaciones traseras mínimas ±3°)
- Beneficios orbital: 880px (orbital 340px / r=110), 480px (290px / r=92), 360px (260px / r=82)

### 8. Nav mejoras
- **Mobile nav fix**: la regla `@media (max-width: 700px) { .nav-links li:not(:last-child):not(.lang-li) { display: none; } }` ocultaba TODOS los links del nav en mobile excepto CTA + lang. Ahora se muestran todos compactos:
  - ≤700px: font `.76rem`, gap `1rem`
  - ≤540px: font `.7rem`, gap `.75rem` (nav.compact baja a `.68rem`)
  - ≤420px: font `.65rem`, gap `.55rem`, lang-button `.65rem`
  - `white-space: nowrap` en cada link → nunca desbordan
- **Nav compact pill (al hacer scroll) — separación logo↔links**:
  - `max-width` 900 → **960px**
  - `padding` `.55rem 1.5rem` → `.55rem 1.75rem .55rem 1.5rem`
  - `gap: 2rem` flex en nav.compact (separa los 3 grupos: logo / links / CTA+lang)
  - **Separador visual**: el logo `NYX` en compact tiene `border-right: 1px var(--border)` + padding/margin → divisor sutil que separa visualmente del primer link "Servicios"

### 9. Beneficios "Lo que ganas al automatizar con Nyx" — orbital reducido en mobile

**Antes**: `.bnf-stage` con `width: min(520px, 100%)` y `--r: 200px` (radio órbita) → en mobile pequeño ocupaba prácticamente todo el viewport, dejando poco espacio para el panel de texto del nodo activo.

**Ahora — escala progresiva**:

| Breakpoint | Width | Radio | Core | Nodos |
|---|---|---|---|---|
| Desktop | min(520px, 100%) | 200px | 64px | 60px |
| ≤880px | **min(340px, 78%)** | **110px** | 46px | 48px |
| ≤480px | **min(290px, 72%)** | **92px** | 36px | 40px |
| ≤360px | **min(260px, 78%)** | **82px** | 30px | 36px |

El orbital ocupa ~1/3 del viewport mobile, el panel de texto (número grande + título + párrafo) queda como elemento principal y bien legible al hacer click en cualquier nodo.

### 10. Server LAN access para testing móvil/tablet
- Server uvicorn ya escucha en `0.0.0.0:8001` (ningún cambio necesario)
- IP local detectada: **192.168.1.132** (Wi-Fi) — URL para móvil/tablet en misma red: `http://192.168.1.132:8001`
- Si Windows Firewall bloquea, regla manual con admin:
  ```powershell
  New-NetFirewallRule -DisplayName "Nyx Web Dev (8001)" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
  ```

### Estado del proyecto post 2026-05-07
- **Líneas index.html**: 3865 (inicio sesión) → ~3500 (fin sesión) tras eliminar Precios + Agentes y reorganizar
- **Líneas nosotros.html**: ~2300 (sin cambios estructurales grandes, solo CSS responsive overrides)
- **Server**: estable, hot-reload funcionando, healthcheck `/healthz` OK, LAN OK
- **SEO ready**: favicon + og-image + canonical + robots + sitemap + JSON-LD desplegados
- **Bloqueadores legales pendientes**: modal Privacidad y modal T&C siguen vacíos (críticos para RGPD antes de producción con voice agent capturando emails/teléfonos)
- **Pendiente decisión**: dominio (nyx-agency.es) + producción (Easypanel)
- **Marcas testimonios**: validar Pulsefit / Lumea / Nordika contra registros reales antes de deploy

---

## Changelog 2026-05-08 — Sesión maratón: hero v2, fluid menu, logo, valores, scroll behaviors

### 1. Fix nav mobile — calendario que desaparecía
- En mobile el icono del calendario (`#nav-cta`, 44×44) seguía reservando su box completo aunque visualmente estuviera escalado con `transform: scale(.78)` → en la pill compact terminaba empujado fuera del área visible.
- Solución provisional (después reemplazada por el fluid menu): añadidos `flex-shrink: 0` y reducido el box real (no solo el visual) por breakpoint: 36px → 32px → 30px.

### 2. Fluid menu mobile — sustituye el ul.nav-links en ≤700px
- Inspirado en `21st.dev/community/components/s/dock` (fluid menu de Kokonut UI), portado a vanilla CSS+JS (sin React/framer-motion).
- En ≤700px se oculta `ul.nav-links` completo y aparece un **botón circular único** (44px) arriba a la derecha que al click se expande hacia abajo en cascada con `data-i="1..6"` y `transition-delay` escalonado de 30ms cada uno.
- Items: Servicios, Proceso, Casos, Nosotros, **Calendario lime** (con `calGlow` heredado), **Globe** (idiomas).
- El item Globe abre un sub-overlay centrado en pantalla (`position: fixed; top:50%; left:50%`) con las 12 banderas en grid 2 columnas → al click llama a `setLanguage(code)` existente y cierra todo.
- Cierre: click fuera, Escape, click en cualquier item de navegación (con `setTimeout(closeAll, 80)` para que el href tenga tiempo de procesar).
- z-index: nav (300) < fluid-menu (305) < lang-drop (320), todos por encima del voice FAB.

### 3. Hero v2 — TrueFocus + nuevo layout
- Reemplazo completo del hero antiguo (4-line h1 + 4 contadores animados) por v2:
  - **Badge** con dot pulsante lime + glow + texto "AUTOMATIZACIÓN PARA PYMES ESPAÑOLAS" en DM Sans 500 mayúscula con tracking ancho.
  - **H1 con TrueFocus** vanilla: la frase se split por espacios, las palabras inactivas tienen `blur(5px)`, y un frame con 4 corners lima va saltando de palabra en palabra (0.3s transition + 0.8s pausa). Port del componente React de **ReactBits TrueFocus** sin `motion/react` — usé puras CSS transitions + setInterval.
  - **Subtítulo** DM Sans 300 al 45% blanco, max-width 580px, centrado.
  - **Stats strip**: 4 columnas con hairlines verticales: `+200%`, `7`, `−60%`, `24/7` — los símbolos `%` y `/7` en lima dentro de `<em>`. Mobile (≤720px) baja a 2x2.
  - **Animación entrada**: cada bloque entra con `fadeUp` escalonado vía CSS keyframes (no GSAP) — badge .10s, h1 .25s, sub .40s, CTAs .55s, stats .70s. Respeta `prefers-reduced-motion`.
- **Fonts**: añadido **DM Sans** 300/400/500 al import de Google Fonts.
- **i18n**: nuevas traducciones en 12 idiomas en un objeto separado `HERO2` (con claves badge, h1, sub, cta1, cta2, s1-s4) — separado de `LANGS` para no reescribir las 12 entradas gigantes. `setLanguage` aplica `HERO2[code]` y reinicializa TrueFocus con el texto traducido.
- **JSON-LD y SEO**: el hero v2 mantiene compatibilidad — los IDs antiguos (`hh`, `hs`, `hm`) siguen usándose como contenedores.

### 4. Hero — fondo navy del site (revertido) + textos centralizados
- Inicialmente puse el hero con fondo `#0a0a0a` (negro). El usuario lo revertió: `background: transparent` para que herede el `var(--bg)` (navy `#030712`) del site igual que el resto de secciones.
- Todos los `rgba(255,255,255,...)` hardcoded sustituidos por tokens del proyecto (`var(--text)`, `var(--muted)`, `var(--border)`, `var(--bmd)`).
- **Todo centrado**: `.hero-body` con `align-items: center; text-align: center`, `.true-focus` con `justify-content: center`, sub/CTA-group/stats todos horizontalmente centrados, stats hairlines visibles en todas las separaciones.
- max-width del hero-body: 980px.

### 5. CTA primario — hand-drawn circle (Kokonut UI)
- Eliminado el botón secundario "Ver demo" (ghost + scroll-to-#casos).
- Reemplazado el botón pill primary lime por un **anchor transparente con SVG circle dibujado a mano** alrededor del label, port del `hand-writing-text` de Kokonut UI:
  - Path original (`M 950 90 C 1250 300, 1050 480, 600 520 ...`) con stroke-linecap round.
  - Reproducción del `pathLength` de framer-motion en CSS puro: atributo SVG `pathLength="1"` + `stroke-dasharray: 1; stroke-dashoffset: 1 → 0` durante 2.5s con curva original `cubic-bezier(.43,.13,.23,.96)`, delay .55s.
  - Label "Agendar diagnóstico" en Syne 800 centrado dentro del óvalo, fade-up con delay 1.4s.
  - **Hover**: stroke + label se tintan a lima `#c8ff00` con drop-shadow lima sutil.
  - Click → `https://cal.com/woidrian/nyx-agency?overlayCalendar=true`.
  - Respeta `prefers-reduced-motion`.

#### Fix mobile: label se salía del círculo
- El aspect-ratio 2:1 del óvalo dejaba muy poca altura interior en mobile → "Agendar diagnóstico" wrapping en 2 líneas que se salían.
- **Solución**: cambié `preserveAspectRatio="xMidYMid meet"` → `preserveAspectRatio="none"` para que el óvalo se estire al container, y añadí `vector-effect="non-scaling-stroke"` para que el grosor del trazo quede uniforme aunque se aplaste verticalmente. Stroke pasó de 12 (escalado por viewBox) a 4 (absoluto).
- Aspect-ratio progresivo: 2:1 desktop → 1.7:1 (≤720) → 1.55:1 (≤480) → 1.45:1 (≤360). Cuanto más estrecho, más cuadrado y más espacio interior.
- Label `max-width: 66% → 60% → 58% → 56%` para forzar el wrap dentro de la zona segura del óvalo, `line-height: 1.05/1.1`.

### 6. Nav: links centrales + eliminación de Servicios/Casos
- Eliminados del nav: "Servicios", "Casos". Mantenidos: "Proceso", "Quiénes somos" (renombrado de "Nosotros"). En `nosotros.html`: "Inicio", "Proceso".
- **Layout reorganizado**: el `<ul class="nav-links">` ahora flota **absolute centered** en el medio del nav (`left: 50%; top: 50%; transform: translate(-50%, -50%)`), y el selector de idioma + calendario se movieron a un nuevo `<ul class="nav-aux">` que queda a la derecha gracias al `justify-content: space-between` del `#nav` flex.
- Quitado el `border-right` divisor del logo en compact mode (que ahora flotaría suelto al no tener el ul al lado).
- Fluid menu mobile reducido en consecuencia: 4 items (Proceso, Quiénes somos, Calendario, Idioma) en index / (Inicio, Proceso, Calendario, Idioma) en nosotros.
- **Mobile nav**: marcado el li de "Quiénes somos" / "Inicio" con clase `.nav-mobile-show` → en ≤700px se hide todos los `<li>` del nav-links excepto ese, así queda visible y centrado entre el logo y el fluid menu. Estilo prominente (`color: var(--text)`, no muted).
- **i18n**: `setLanguage` cambiado a `_setNav` defensivo con `if (el)` — ya no rompe al intentar actualizar IDs eliminados (`nav-services`, `nav-cases`). Cambiado el valor de `nav.about` en `LANGS.es` ("Quiénes somos") y `LANGS.en` ("About us"); el resto de idiomas ya tenían su variante natural correcta.

### 7. nosotros.html — Bug robot 3D + reemplazo de valores
- **Bug fix robot 3D**: el eje Y del mouse tracking estaba invertido. En el rig actual `rotation.x` positiva inclina la cabeza hacia ABAJO (no atrás), así que la línea original `targetRX = -cdy * 0.4` hacía que al mover el cursor arriba el robot mirase abajo. Quité el menos: `targetRX = cdy * 0.4`. Ahora la cabeza sigue al cursor correctamente.
- **Sección "Lo que nos define" rediseñada**: reemplazadas las 3 valor-cards planas (01 Resultados / 02 Sistemas / 03 Transparencia) por **skew gradient cards**, port vanilla del componente React `gradient-card-showcase` de 21st.dev:
  - Cada card usa CSS custom props `--gf` y `--gt` para gradientes únicos: orange→pink (#ffbc00→#ff0058), blue→pink (#03a9f4→#ff0058), lime→cyan (#4dff03→#00d0ff).
  - **Dos paneles absolutos** (sólido + 30px blur) skewed 15deg detrás de un cuerpo glassmorphism (`backdrop-filter: blur(10px)`).
  - **Hover**: paneles se enderezan, cuerpo se desplaza a la izquierda y crece en padding, aparecen 2 blobs flotantes en las esquinas (top-left + bottom-right) con animación `skewBlob` (translateY ±10px, 2s loop, escalonada -1s).
  - Mantenidos IDs `v1-h`, `v2-h`, `v3-h`, `v1-p`, `v2-p`, `v3-p` para no romper el i18n existente.
- **Mobile responsive evolution** (3 iteraciones):
  - **V1**: scroll horizontal snap con `flex-wrap: nowrap; overflow-x: auto; scroll-snap-type: x mandatory` — las 3 cards "paralelas" al hacer swipe. Encuadre con border + bg + radius.
  - **V2** (a petición del usuario): cards más pequeñas para que cupieran encuadradas. 280×360 → 220×290 → 195×270 → 175×260 progresivo. Pull del panel oblicuo (`left: 22px → 18px → 16px → 14px`). Trim del glow blur a 18px. Tipografía proporcionada (h: 1rem → .85rem, p: .76rem → .68rem). `-webkit-line-clamp` (7→6→5) para evitar desbordes.
  - **V3 final** (a petición del usuario "dos arriba y la otra abajo en medio"): switch de scroll horizontal a **CSS Grid 2 columnas**:
    ```css
    .skew-grid { display: grid; grid-template-columns: 1fr 1fr; }
    .skew-card:nth-child(3) { grid-column: 1 / -1; justify-self: center; }
    ```
    Las cards 1 y 2 quedan en la fila superior lado a lado, la card 3 ocupa las 2 columnas y se centra en medio (max-width propio mantiene su tamaño igual a las de arriba). Tamaños: 220×280 (≤880) → 175×260 (≤480) → 150×240 (≤360).

### 8. Logo nuevo — NYX AGENCY (marca + wordmark + tag)
- Reemplazado el logo `NY<span class="nav-logo-x">X</span>` por un lockup completo:
  - **Marca cuadrada** 36×36px con borde sutil (`var(--bmd)`), `border-radius: 7px` y bg ligero. Dentro: SVG inline de una "N" estilizada (3 trazos lima `#c8ff00` con stroke 2.6 + drop-shadow lima sutil).
  - **Wordmark** "NYX" en Space Grotesk 700.
  - **Tag** "AGENCY" en JetBrains Mono debajo, lima, con `letter-spacing: .32em`.
  - **Hover**: cuadrado se tinta lima (border + bg), opacity de todo el lockup baja a .85.
- **Responsive**:
  - Default: 36px mark + 1.1rem word + 0.54rem tag.
  - Compact (al scrollear): 30px / 0.95rem / 0.48rem.
  - Mobile ≤700px: 32px / 1rem / 0.5rem.
  - Mobile ≤420px: el tag "AGENCY" se hide completo, mark a 30px y word a 0.95rem para que el lockup ocupe menos en la pill al lado del fluid menu.
- Aplicado en `index.html` y `nosotros.html`.

### 9. Animated shiny shimmer en H1 hero
- Aplicado al `.tf-word` (palabras del TrueFocus) un efecto shiny shimmer infinito, port vanilla del `AnimatedText` de 21st.dev:
  - **Gradiente lineal** sobre el texto: `linear-gradient(90deg, rgba(241,245,249,.35), #ffffff, rgba(241,245,249,.35))` con `background-size: 200% 100%`.
  - `background-clip: text` + `color: transparent` → el gradiente se recorta a las letras.
  - Animación `tfShimmer 3s ease-in-out infinite alternate` mueve `background-position` de 0% a 100% y regresa, generando el sweep de luz infinito.
  - **Coexiste con TrueFocus**: el frame lima sigue saltando palabra a palabra, las inactivas siguen con `blur(5px)`, el shimmer corre por debajo. Respeta `prefers-reduced-motion`.

### 10. Nav compact al primer scroll
- Antes: dos `ScrollTrigger.create` separados — `nav.solid` con `start: 'top -60'` y `nav.compact` con `start: 'top -' + (window.innerHeight * 0.7)` (≈ pasar la primera sección).
- Ahora: un único `ScrollTrigger` con `start: 'top -40'` que activa ambas clases (`solid` + `compact`) a la vez. En cuanto el usuario hace cualquier scroll, el nav colapsa a la pill compacta.
- Aplicado a `index.html` y `nosotros.html` — mismo comportamiento en desktop, tablet y mobile.

### Estado del proyecto post 2026-05-08
- **Animaciones del hero combinadas**: fadeUp escalonado (entrada) + TrueFocus (frame lima rotando) + shiny shimmer (gradiente moviéndose) + handwriting circle (path drawing). Todas en CSS puro o GSAP existente, sin nuevas librerías.
- **Stack visual unificado**: el lima `#c8ff00` se usa coherentemente en logo, voice FAB, cal-icon nav, frame TrueFocus, blobs hero, badge dot, hand-drawn circle hover, valores hover, fluid-menu cal item, dot pulsante badge.
- **Nav mobile claro**: logo NYX|N a la izquierda, "Quiénes somos" / "Inicio" centrado, fluid menu a la derecha — todo entre los 360-700px de viewport.
- **Sección valores mobile** (nosotros): pirámide invertida 2+1 dentro de un encuadre con border + radius.
- **Nav compact** ahora más responsivo: pill aparece al primer scroll real (~40px), no después de la primera sección.
- **Pendientes** (sin cambios desde 2026-05-07): modales Privacidad/T&C vacíos para RGPD; validar marcas Pulsefit/Lumea/Nordika; deploy a producción ya activo en Vercel + dominio nyx-agency.es funcionando.

---

## Changelog 2026-05-08 (cont.) — i18n masivo final, mobile rail, fluid menu fix, stagger-text en nosotros

### 1. Auto deploy en main — workflow permanente
- Confirmado por el usuario como regla: **después de cualquier edición sustantiva, hacer `git add` + `git commit` + `git push origin main` automáticamente** (sin pedir confirmación). Vercel está conectado a `github.com/woidrian/Nyx-web` y deploya solo a `https://nyx-agency.es` al detectar push a `main`.
- El usuario testea siempre en la versión deployed, no en local. Si los cambios solo están en disco, los ve "como si no se hubieran aplicado".
- Guardado como memoria persistente (`feedback_auto_deploy.md`).

### 2. i18n completion — Casos, Diferenciación, Equipo morph
**Antes**: 3 secciones quedaban hardcoded en español aunque cambiaras de idioma.

**Ahora todo wired vía `data-i18n` walker** (que ya existía desde 2026-05-06):

#### Sección Casos v2 (`index.html`)
- 3 stats agregados: `+40% / Eficiencia operativa`, `−60% / Tareas repetitivas`, `3× / Capacidad de atención`.
- 3 testimonios (Pulsefit / Lumea / Nordika): quote + author name + author role.
- Hint pill: "Arrastra para ver más".
- Eyebrow: "RESULTADOS REALES".
- H2 con `<br>` y `<span class="accent">` ahora wired vía `data-i18n="casos.h2"` (innerHTML).
- Total: ~15 strings × 12 idiomas = ~180 traducciones nuevas.

#### Sección Diferenciación (`index.html`)
- 6 celdas comparativas (Otros vs Nyx): label + heading + parágrafo cada una.
- H2 + parágrafo intro.
- Total: ~20 strings × 12 idiomas = ~240 traducciones nuevas.

#### Equipo morph (`nosotros.html`)
- Las 6 palabras rotativas en la pantalla del robot (`Construyo / Automatizo / Diseño / Optimizo / Resuelvo / Entrego`) ahora dependen del idioma.
- Cada idioma tiene su array `equipo.morph: [...]` con sus propios verbos.
- El módulo morph del IIFE expone `window.setMorphWords(words)`. `setLanguage` lo llama después de aplicar la traducción.
- Total: 6 verbos × 12 idiomas = 72 traducciones nuevas.

### 3. `setLanguage` defensivo — robustez ante elementos eliminados
**Bug histórico**: `setLanguage` tenía accesos directos como `getElementById('XYZ').textContent = ...` sobre elementos que ya no existían (eliminados en limpiezas previas: nav-services, nav-cases, founder-role, etc.). El primer null reference abortaba TODA la función → secciones siguientes no se traducían (incluido el walker `data-i18n` al final).

**Fix aplicado en ambas páginas**:
- Helpers internos:
  ```js
  const setText = (id, val) => { const el = document.getElementById(id); if (el && val != null) el.textContent = val; };
  const setHTML = (id, val) => { const el = document.getElementById(id); if (el && val != null) el.innerHTML = val; };
  const safe = (fn) => { try { fn(); } catch (e) { /* silent */ } };
  ```
- **El walker `data-i18n` se ejecuta PRIMERO** (después de actualizar el `<html lang>` y dir). Así, aunque algo más abajo falle, las traducciones ya están aplicadas vía data-attr.
- Cada sección hardcoded antigua envuelta en `safe(() => { ... })` para que un error en una no rompa las demás.

### 4. Mobile rail "Cómo trabajariamos contigo" — fix Capacitación overlap
**Problema**: en `index.html` el rail de servicios sticky-scroll tenía `grid-template-columns: 84px 1fr` en mobile. La palabra "Capacitación" del item activo se solapaba con el contenido del panel.

**Iteraciones**:
1. **V1** (`word-break: break-word`): partió la palabra dejando "n" suelta en línea aparte. Usuario: "queda fatal!".
2. **V2 final**: aumentar la columna del rail progresivamente y reducir la fuente:
   - ≤720px: rail-cols `108px 1fr`, font `.7rem`
   - ≤480px: rail-cols `124px 1fr`, font `.66rem`
   - ≤360px: rail-cols `124px 1fr`, font `.58rem`
   - **Removido** todo `word-break` para mantener palabras enteras.
   - `white-space: normal` (permite wrap natural si hace falta) + `line-height: 1.15` compacta.

### 5. Fluid menu mobile — sub-overlay de idiomas se cortaba
**Problema**: al hacer scroll, `#nav.compact` aplica `backdrop-filter: blur(18px)`. CSS spec: `backdrop-filter` crea un nuevo **containing block** para descendientes con `position: fixed`. El `.fm-lang-drop` (overlay con las 12 banderas) estaba dentro de `#nav` → se posicionaba relativo al nav, no al viewport, y se recortaba mostrando solo 8 de 12 idiomas.

**Fix**: mover el `<div class="fm-lang-drop">` **fuera de `#nav`**, al body level (justo después del `<nav>` o al final del body). Así su `position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%)` se calcula relativo al viewport. Aplicado en index + nosotros.

### 6. Stagger-text en H1 de nosotros — port vanilla 21st.dev

**H1 nuevo** (12 idiomas, formato 2 líneas): `'Somos Nyx.<br>Automatizamos el trabajo repetitivo.'`

**Diseño de la animación**:
- Cada **palabra** entra como bloque sólido (no char-by-char). Usuario explícito: "que aparezca como en bloque".
- **Direcciones asimétricas** por línea:
  - Línea 1 ("Somos Nyx.") → entra desde la **izquierda**, empezando por "Somos" (`fromLeft`, orden natural 0,1,2).
  - Línea 2 ("Automatizamos el trabajo repetitivo.") → entra desde la **derecha**, empezando por "repetitivo." (`fromRight`, orden inverso N-1,N-2,...0).

**Implementación CSS**:
```css
.hero-h1 { overflow-wrap: normal; word-break: normal; hyphens: none; }
.hero-h1 * { overflow-wrap: normal; word-break: normal; }
.hero-h1 .st-line { display: block; }
.hero-h1 .st-word {
  display: inline-block;
  overflow: hidden;          /* clip box que reserva el espacio del char */
  vertical-align: top;
  white-space: nowrap;       /* nunca partir la palabra (incluido el "." final) */
  padding: .04em 0 .25em 0;  /* margen para descenders sin recortar */
  margin: -.04em 0 -.25em 0;
}
.hero-h1 .st-char {
  display: inline-block;
  white-space: nowrap;
  opacity: 1;
  transform: translateX(0);
  transition:
    transform 480ms cubic-bezier(.22,.61,.36,1),
    opacity 320ms cubic-bezier(.25,.1,.25,1);
}
.hero-h1 .st-line.is-prep[data-from="left"]  .st-char { opacity: 0; transform: translateX(-110%); }
.hero-h1 .st-line.is-prep[data-from="right"] .st-char { opacity: 0; transform: translateX( 110%); }
```

**Implementación JS**:
- `wrapChars(rootEl, { stagger: 55, baseDelay: 60 })`:
  - Splitea el contenido del H1 por `<br>` → array de líneas.
  - Cada línea se tokeniza con regex `/(\s+)/` (preserva espacios).
  - Para cada palabra: `<span class="st-word"><span class="st-char">word</span></span>`.
  - **Reverse stagger en líneas impares** (idx=1, idx=3...): `orderIdx = fromRight ? (wordCount - 1 - wIdx) : wIdx`.
  - `transition-delay = baseDelay + orderIdx * stagger` por palabra.
- `play(rootEl)`:
  - Añade `.is-prep` a todas las `.st-line` (estado pre-anim: chars fuera de pantalla).
  - Force reflow `void rootEl.offsetWidth`.
  - Quita `.is-prep` después de 30ms → arranca la transición.
  - Fallback de seguridad: si algo falla, el H1 está visible por defecto (sin `.is-prep` no se aplica el desplazamiento).
- `window.runHeroStagger()` exposto globalmente y llamado desde `setLanguage` después de `setHTML('hero-h1', t.hero.h1)`.

**Bug fixes durante el port**:
- **"repetitivo" partido a mitad**: el `overflow-wrap: break-word` global del body (anti-cortes del 2026-05-07) overrideaba mi CSS. Fix: `white-space: nowrap` en `.st-char` + `.st-word` + `overflow-wrap: normal` explícito en `.hero-h1` y `.hero-h1 *`.
- **Letras solapándose**: cada `.st-char` con `translateX(±110%)` se desplazaba sobre su propio width pero el flow del DOM no reservaba el espacio. Fix: envolver cada char en `.st-word { overflow: hidden }` que actúa de clip box y SÍ reserva el espacio en línea.
- **Título completamente invisible**: la primera versión asumía estado por defecto invisible y aplicaba `.is-vis` para mostrar. Si el JS fallaba, el título no aparecía nunca. Fix: invertir la lógica → estado por defecto **visible**; `.is-prep` aplica el estado pre-anim de forma efímera. JS quita `.is-prep` a los 30ms con un fallback de 2.2s.
- **"." separado de "repetitivo"**: el punto final estaba siendo tratado como token aparte por el split del walker o quedaba en línea aparte por word-break global. Fix: el regex `/(\s+)/` solo splitea por whitespace → "repetitivo." queda como un único token. Sumado a `white-space: nowrap` en `.st-word` → nunca se rompe.
- **Velocidad final**: `stagger: 90 → 55ms`, `baseDelay: 100 → 60ms`, `transform 720 → 480ms`, `opacity 500 → 320ms` (a petición del usuario).

### 7. Estado del proyecto post 2026-05-08 (cont.)
- **i18n: 100% wired** en index.html y nosotros.html. Las únicas strings que quedan hardcoded son del voice modal (UI states + textos del modal AdrIAn) — pendiente para una sesión dedicada.
- **`setLanguage` robusto**: aunque añadan/quiten secciones, una falla local no rompe las demás. Las traducciones data-i18n se aplican siempre primero.
- **Workflow auto-deploy confirmado**: cualquier edit → commit + push → Vercel deploya en ~30s. El usuario verifica en `https://nyx-agency.es`, no en local.
- **Animación H1 nosotros**: stagger asimétrico funcional, palabras enteras (incluido punto final), velocidad ajustada.
- **Pendientes (sin cambios)**: modales Privacy + T&C vacíos para RGPD, validar marcas Pulsefit/Lumea/Nordika, voice modal i18n.

---

## Changelog 2026-05-08 (tarde) — Clean URLs, carrusel infinito, animación skew cards, subrayado nav

### 1. Clean URLs — eliminado `.html` de la barra de direcciones
**Problema reportado**: clicar "Inicio" o "Quiénes somos" mostraba `nyx-agency.es/index.html` y `nyx-agency.es/nosotros.html` en la URL. Usuario quería URLs limpias (sin extensión).

**Aclaración importante sobre el deploy**: aunque la memoria dice "Vercel", el dominio `nyx-agency.es` lo sirve **`server.py` (FastAPI)** — la respuesta `{"detail":"Not Found"}` cuando piden `/nosotros` es la 404 default de FastAPI/Starlette, no de Vercel. Vercel sí está conectado al repo, pero las rutas no estáticas las maneja la app Python. Por eso `cleanUrls` del `vercel.json` solo aplica si la web fuese 100% estática.

**Doble fix aplicado por seguridad**:

#### `vercel.json` (por si en el futuro la web se sirve estática)
- Añadido `"cleanUrls": true` y `"trailingSlash": false`. Si Vercel toma el control, sirve `nosotros.html` en `/nosotros` y emite 308 desde `/nosotros.html` automáticamente.

#### `server.py` (lo que realmente está activo en producción)
```python
from fastapi.responses import RedirectResponse  # nuevo import

@app.get("/nosotros")
async def nosotros() -> FileResponse:
    return FileResponse(ROOT_DIR / "nosotros.html", media_type="text/html", headers=_HTML_HEADERS)

@app.get("/nosotros.html")
async def nosotros_html() -> RedirectResponse:
    return RedirectResponse(url="/nosotros", status_code=308)

@app.get("/index.html")
async def index_html() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=308)
```

#### Enlaces internos en HTML
- `index.html`: 3 hrefs `nosotros.html` → `/nosotros`.
- `nosotros.html`: 9 hrefs `index.html(...)` → `/(...)` (logo, nav, hero back chevron, footer + anchors `#proceso`, `#servicios`, `#casos`).

#### SEO
- `nosotros.html`: `<link rel="canonical">` y `<meta property="og:url">` actualizados a `https://nyx-agency.es/nosotros` (sin `.html`).
- `sitemap.xml`: `/nosotros.html` → `/nosotros`, `lastmod` 2026-05-08.

**Resultado**: cualquier URL legacy con `.html` redirige permanentemente (308) a la versión limpia. Los enlaces nuevos siempre apuntan a `/` y `/nosotros`.

### 2. Carrusel de tecnologías — scroll infinito sin pausa al hover
**Antes**: `.carousel-wrap:hover .carousel-track { animation-play-state: paused; }` → al pasar el ratón sobre los logos, el carrusel se detenía.

**Ahora**: regla eliminada. El carrusel mantiene la animación `scrollLeft`/`scrollRight` continua aunque el usuario hover sobre las marcas. Es solo una decoración visual, no un componente interactivo.

### 3. Sección Valores (nosotros) — entrada en cascada de las skew cards al scroll

**Antes**: las 3 skew gradient cards (Resultados / Sistemas / Transparencia) aparecían al cargar la página, sin animación de entrada.

**Ahora**:
- **CSS**: las cards arrancan con `opacity: 0`. Cuando reciben `.is-in`, ejecutan el keyframe `skewIn`:
  ```css
  @keyframes skewIn {
    from { opacity: 0; transform: translateY(48px) scale(.92); filter: blur(10px); }
    60%  { opacity: 1; filter: blur(0); }
    to   { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
  }
  ```
  - Duración: 950ms con cubic-bezier(.22,.61,.36,1).
  - El `60%` del keyframe quita el blur y normaliza opacity antes del final → da sensación de "lift suave" sin re-blurear al final.
- **Stagger left-to-right** vía `nth-child` en el grid:
  - Card 1 (Resultados, naranja→rosa) → delay 0ms.
  - Card 2 (Sistemas, azul→rosa) → delay 180ms.
  - Card 3 (Transparencia, lima→cian) → delay 360ms.
- **JS — IntersectionObserver**:
  - `threshold: 0.18` y `rootMargin: '0px 0px -8% 0px'` → la animación arranca cuando la card está ~18% visible, un pelín antes de llegar al centro del viewport.
  - Cada card se observa individualmente y se desuscribe al disparar (`io.unobserve(e.target)`) para que no se vuelva a animar en re-scroll.
  - Fallback sin IntersectionObserver: aplica `.is-in` a todas las cards inmediatamente.
- **Mobile**: el layout 2+1 (cards 1-2 arriba, card 3 centrada abajo) mantiene el mismo stagger ya que las 3 cards entran al viewport prácticamente a la vez al hacer scroll.
- **Accesibilidad**: `prefers-reduced-motion: reduce` desactiva la animación con `opacity: 1 !important` (las cards se muestran directamente sin movimiento).

### 4. Nav — links más legibles + subrayado lima animado izq→der

**Problema**: las palabras "Proceso" y "Quiénes somos" (index) / "Inicio" y "Proceso" (nosotros) eran poco distinguibles en reposo (color `--muted` que es un slate medio bastante apagado).

**Cambios aplicados en ambas páginas, mismo selector `.nav-links a`**:

#### Texto en reposo más diferenciado
- Color: `#cbd5e1` (slate-300, casi blanco con tono frío) — antes `var(--muted)` (#64748b).
- `font-weight: 500` (antes default 400).
- `letter-spacing: .005em` (toque editorial sutil sin afear).
- Hover: blanco completo `var(--text)` (#f1f5f9).

#### Subrayado animado izq→der con pseudo-elemento
```css
.nav-links a {
  position: relative;
  padding-bottom: 4px;  /* hace sitio para la línea sin afectar layout */
}
.nav-links a::after {
  content: "";
  position: absolute;
  left: 0; bottom: 0;
  width: 100%;
  height: 1.5px;
  background: #c8ff00;
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform .5s cubic-bezier(.22,.61,.36,1);
  box-shadow: 0 0 6px rgba(200,255,0,.5);
  border-radius: 1px;
  pointer-events: none;
}
.nav-links a:hover::after,
.nav-links a:focus-visible::after,
.nav-links a:active::after { transform: scaleX(1); }
```

**Decisiones de diseño**:
- **`scaleX` + `transform-origin: left center`** en lugar de animar `width`: usa GPU compositor (más fluido), arranca desde la izquierda y crece hacia la derecha de forma natural.
- **Color lima `#c8ff00`**: mismo accent que el voice FAB, el frame TrueFocus del hero, el badge dot, el calendario nav y los blobs lima — coherencia visual.
- **`box-shadow` lima sutil**: la línea no es solo un trazo plano, tiene un glow suave que la integra en el sistema de luces lima del site.
- **`border-radius: 1px`** en una línea de 1.5px: puntas redondeadas casi imperceptibles que dan acabado profesional.
- **Triple trigger** (`:hover`, `:focus-visible`, `:active`): cubre desktop (hover), navegación por teclado (focus accesible) y mobile (tap activa `:active`).
- **Easing cubic-bezier(.22,.61,.36,1)**: arranca rápido, desacelera al final — sensación elegante.

**Mobile (≤700px)**: el item `.nav-mobile-show a` (única palabra del nav visible en mobile, "Quiénes somos" en index / "Inicio" en nosotros) hereda el mismo `::after` automáticamente. Al tocar la palabra en mobile, la línea lima aparece como feedback de presión.

### Estado del proyecto post 2026-05-08 (tarde)
- **URLs limpias 100%**: ningún enlace interno usa `.html`. Cualquier acceso legacy con extensión hace 308 a la URL limpia.
- **Carrusel tecnologías**: no se interrumpe nunca, pure decoración fluida.
- **Sección valores**: entrada animada coherente con el resto del site (ya teníamos animaciones en hero stats, hero h1, true focus, etc).
- **Nav**: visualmente más fuerte y con feedback claro en hover/click. La línea lima refuerza la identidad de marca.
- **Aclaración sobre arquitectura de deploy**: el usuario tiene contradicción en su memoria — el CLAUDE.md original dice Easypanel + FastAPI, la memoria de auto-deploy dice Vercel. La realidad es que **el dominio lo sirve `server.py`** (lo evidencia el `{"detail":"Not Found"}` de FastAPI). Vercel puede estar como pipeline CI, pero las rutas las decide Python. Para futuras sesiones: si una ruta no existe en producción, **buscar primero en `server.py`** antes que en `vercel.json`.

### 5. Footer rediseñado — logo NYX|N + subrayados lima + wordmark gigante visible
**Cambios aplicados en index.html y nosotros.html:**

#### Logo del footer = logo del nav
- Antes: `<span class="footer-logo">NYX</span>` (texto plano blanco, sin marca, no clicable).
- Ahora: misma estructura completa que el `nav-logo` — `<a class="nav-logo footer-brand" href="/">` con la marca cuadrada lima (3 trazos N en SVG), wordmark "NYX" en Space Grotesk 700 y tag "AGENCY" en JetBrains Mono lima debajo.
- Reutilizamos las clases `.nav-logo*` ya estiladas (mark + text + word + tag). El selector `#nav.compact .nav-logo*` no afecta porque el logo del footer no está dentro de `#nav`.
- Clase extra `footer-brand` solo añade `text-decoration: none` por si el reset cambia, sin sobrescribir nada del nav-logo.
- **Hover heredado del nav-logo**: marca se tinta lima, opacidad baja a .85.
- Borrada la regla CSS `.footer-logo { font-family ... }` (ya no se usa).

#### Subrayado lima animado izq→der en footer-nav + footer-legal
- Mismo patrón exacto que `.nav-links a` (cambio del bloque anterior):
  - Color reposo: `#cbd5e1` (slate-300), font-weight 500, letter-spacing .005em, padding-bottom 4px.
  - `::after` con `transform: scaleX(0)`, `transform-origin: left center`, lima `#c8ff00` 1.5px de alto, `box-shadow: 0 0 6px rgba(200,255,0,.5)`, border-radius 1px.
  - Trigger triple: `:hover / :focus-visible / :active` → `transform: scaleX(1)` con `transition: transform .5s cubic-bezier(.22,.61,.36,1)` + color → `var(--text)`.
- Aplicado a:
  - **`.footer-nav a`** (links: Servicios / Proceso / Casos / Nosotros en index; Servicios / Casos / Inicio en nosotros).
  - **`.footer-legal button`** (Política de Privacidad y Términos y Condiciones). Detalle extra: `font-family: inherit` para que los botones tengan la misma tipografía que el resto del footer.

#### Wordmark gigante "NYX" del fondo — gris claro visible
- Antes: `-webkit-text-stroke: 1px rgba(241,245,249,0.1)` → outline blanco al 10% de opacidad sobre el navy oscuro → casi invisible (el problema reportado: "no se diferencia, está en negro completo").
- Ahora: `-webkit-text-stroke: 1.5px rgba(203,213,225,0.32)` → trazo más grueso (1px → 1.5px) en slate-300 al 32% de opacidad. Se ve claramente como un wordmark decorativo gris medio sobre el navy, pero sigue sin dominar la composición.
- **Decisión de color**: usar slate-300 (`#cbd5e1`) en lugar de lima por petición explícita del usuario ("ponlo gris pero que se diferencia"). El lima ya está reservado para elementos interactivos/accent (FAB, frame hero, calendar nav, subrayados nav/footer, marca del logo).

### Estado del proyecto post 2026-05-08 (tarde + footer)
- **Coherencia visual del footer ↔ nav**: misma marca, misma tipografía, mismo subrayado lima, misma paleta. El usuario llega al final de la página y ve la misma identidad que en el header — refuerzo de marca.
- **Wordmark gigante**: ahora cumple su función decorativa (era invisible antes).
- **Sistema lima consistente**: marca cuadrada del logo, subrayado en hover de cualquier link/button, FAB, frame hero, calendar nav, dot del badge, blobs hero. Único accent funcional. El gris claro del wordmark gigante es un elemento decorativo neutro que NO compite con el lima.

---

## Changelog 2026-05-09 — Backend lead pipeline rework + AdrIAn 2.0 + voice modal UX

### 1. Lead pipeline: n8n fuera, Supabase + Resend dentro
**Antes**: `POST /api/lead` reenviaba el payload al webhook n8n (`ai-leedloop-n8n.t64mfz.easypanel.host/webhook/nyx-voice-lead`), que era el responsable de persistir y notificar. Si n8n caía o el webhook se rompía, los leads se perdían.

**Ahora**: el server.py persiste y notifica directamente, sin intermediarios:

#### `_save_to_supabase(lead)` — fail-soft
- POST a `${SUPABASE_URL}/rest/v1/${SUPABASE_TABLE}` con headers `Content-Profile`/`Accept-Profile` apuntando a `SUPABASE_SCHEMA` (default `nyx`).
- Auth: `apikey` + `Authorization: Bearer ${SUPABASE_ANON_KEY}`.
- `Prefer: return=minimal` para no devolver el row completo (más rápido).
- Si SUPABASE_URL o SUPABASE_ANON_KEY no están configuradas, log y devuelve `False` sin lanzar excepción.
- Si HTTP error: log + return `False`. Nunca rompe el endpoint público.

#### `_send_resend_email(lead)` — fail-soft
- POST a `https://api.resend.com/emails` con bearer token.
- Plantilla HTML con tabla por filas (Nombre / Email / Teléfono / Negocio / Interés / Fuente / Cualificado / Notas) + timestamp en zona Europe/Madrid (`zoneinfo.ZoneInfo`).
- Booleans renderizados como `Sí ✅` / `No ❌`. None/"" → `—`.
- Notas con `white-space: pre-wrap` para conservar saltos de línea.
- Subject dinámico: `🚀 Nuevo lead Nyx — {nombre} ({fuente})`.
- Si RESEND_API_KEY no está configurada → log + skip.

#### `_persist_lead(lead)` — orquestador
- Llama a Supabase y Resend secuencialmente. Cada uno es independiente: si Supabase falla, el email igualmente se intenta. Devuelve `{"supabase": bool, "email": bool}`.

#### Endpoint `POST /api/lead`
- Sigue recibiendo `LeadPayload` validado por Pydantic.
- Default `fuente="voice_agent"` si el cliente no la manda.
- Llama a `_persist_lead` y devuelve `{"ok": True, "supabase": ..., "email": ...}`.

#### Endpoint nuevo `POST /api/cal-webhook`
- Recibe el JSON crudo del webhook de Cal.com, extrae `payload.attendees[0]` (name/email/phone) y `payload.title` como negocio.
- Mapea a la misma forma de lead con `fuente="cal_com"` + `interes="Reserva de cita"`.
- Reusa `_persist_lead` → mismo flujo de Supabase + email que `/api/lead`. Una sola plumbing para ambas fuentes.

#### Cambios en config / env
- **Eliminada**: `N8N_WEBHOOK_URL` (y su default hardcoded).
- **Nuevas (todas opcionales con defaults sensatos)**: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SCHEMA` (`nyx`), `SUPABASE_TABLE` (`leads`), `RESEND_API_KEY`, `LEAD_NOTIFY_EMAIL` (`growth@nyx-agency.es`), `LEAD_FROM_EMAIL` (`growth@nyx-agency.es`).
- `/healthz` ahora reporta `supabase_configured` y `resend_configured` para diagnóstico rápido.

### 2. Tool `guardar_lead` extendido — cualificación dentro del payload

**Antes**: el tool solo recogía datos de contacto + sector + interés. AdrIAn no transmitía juicio sobre si el lead merecía asesoría.

**Ahora — dos campos nuevos**:
- `cualificado` (boolean, **required**): true si el lead encaja con los criterios de Nyx (presupuesto, encaje, motivación), false si no.
- `notas` (string, opcional): resumen breve de la conversación (contexto del negocio, dolor principal, urgencia, motivo de la decisión).

**Propagación end-to-end** (porque añadir el campo solo al tool no sirve si el resto del pipeline lo descarta):
1. `GUARDAR_LEAD_TOOL` declara los dos parámetros nuevos en `function_declarations[0].parameters.properties` y `cualificado` se añade a `required`.
2. `LeadPayload` (Pydantic) acepta ambos: `cualificado: bool | None = None`, `notas: str | None = None`. Sin esto, FastAPI los descartaba silenciosamente (Pydantic ignora extras por default).
3. `_format_lead_email_html` añade dos filas a la tabla del email — "Cualificado" (con render boolean → `Sí ✅` / `No ❌`) y "Notas" (con `white-space: pre-wrap`).
4. La tabla `nyx.leads` ya tenía las columnas `cualificado bool` y `notas text` (confirmado por el usuario, no hizo falta migración).

### 3. SYSTEM_PROMPT 2.0 — AdrIAn de barrio madrileño

**Antes**: prompt corto y genérico ("Cercano y profesional, hablas de tú. Directo, no das rodeos."). Salida sonaba a call center.

**Ahora — prompt con 5 secciones explícitas**:
1. **PERSONALIDAD**: chaval de barrio, jerga natural, empático con autoridad. Lista de muletillas concretas que debe usar.
2. **CONTEXTO**: representa Nyx, objetivo cualificar lead, decide si merece asesoría con Adri.
3. **FLUJO DE CUALIFICACIÓN** (4 pasos): a qué se dedica + tamaño equipo → mayor dolor → qué han intentado antes → urgencia (implementar ya o explorar).
4. **CRITERIOS** (internos, nunca mencionados al usuario):
   - ✅ negocio activo con 2-3+ personas, procesos repetitivos claros, sector compatible (clínica/coaching/restaurante/inmobiliaria/academia/ecommerce/servicios), intención real de invertir.
   - ❌ autónomo solo, sin presupuesto, sin procesos repetitivos, busca software a medida, estudiante/curioso.
5. **CIERRE SEGÚN RESULTADO**:
   - Si cualifica: dile que encaja, recoge nombre/email/teléfono, anuncia que Adri contacta en <24h, llama `guardar_lead` con `cualificado=true`.
   - Si no: amable pero honesto, recoge igualmente datos para el futuro, llama `guardar_lead` con `cualificado=false`.

**Reglas globales**: español siempre, máx 2-3 frases por turno (es voz, no email), nunca menciona criterios ni procesos internos, mantiene la coherencia del personaje incluso si le preguntan si es IA.

#### Iteración de jerga
La primera versión usaba expresiones genéricas ("tío", "mira", "oye", "venga", "está claro", "te entiendo"). Sonaba a sevillano. El usuario pidió **estilo Madrid específicamente**. Lista final:
> tío, macho, ostia, venga va, qué fuerte, mola, en plan, o sea, de puta madre, no te flipes

(Sí, el lenguaje fuerte es deliberado — es la voz que el usuario quiere para AdrIAn.)

### 4. Voice modal — transcript legible (desktop, tablet, móvil)

**Problema reportado**: usuario mandó screenshot del modal abierto. La conversación visible (burbujas user + agent) era ilegible — fuente pequeña y altura cortada. En tablet y móvil aún peor.

**Causas**:
- `#transcript max-width: 520px` (modal es 720px → bubbles encogidas).
- `#transcript max-height: 24dvh` (en pantalla 900px = 216px, en breakpoint <700px alto = 18dvh = 126px → solo 1-2 burbujas visibles).
- `.bubble font-size: .9rem` (~14.4px), padding `.55rem .8rem`, line-height 1.45 → texto apretado.
- Sin breakpoints específicos para tablet/móvil del modal (los responsive del site no aplicaban dentro del modal porque el CSS está scopeado).

**Cambios aplicados en `index.html` y `nosotros.html` (mismas reglas en ambos)**:

| | Antes | Después |
|---|---|---|
| `#transcript max-width` | 520px | **640px** |
| `#transcript max-height` | 24dvh | **min(38dvh, 340px)** |
| `#transcript min-height` | — | **200px** (suelo garantizado) |
| `#transcript gap` | .5rem | **.65rem** |
| `.bubble font-size` | .9rem | **1rem** |
| `.bubble line-height` | 1.45 | **1.55** |
| `.bubble padding` | .55rem .8rem | **.75rem 1rem** |
| `.bubble border-radius` | 12px | **14px** |
| `.bubble max-width` | 85% | **88%** |
| @media `max-height: 700px` | max-height 18dvh | **min(30dvh, 220px) + min 160px** |
| @media `max-width: 720px` (NUEVO) | — | max-h **min(36dvh, 300px)** + min 180px, font .95rem, max-w 92% |
| @media `max-width: 480px` (NUEVO) | — | max-h **min(34dvh, 260px)** + min 160px, font .92rem, line-h 1.5, max-w 94% |

El `min(Xdvh, Ypx)` evita que en pantallas gigantes el transcript ocupe demasiado, y el `min-height` garantiza un suelo legible siempre.

### 5. Footer-nav alineado a la derecha (todos los breakpoints)

**Problema reportado**: el bloque `.footer-nav` (links Servicios / Proceso / Casos / Quiénes somos) flotaba a la izquierda del footer y se solapaba visualmente con el wordmark gigante "NYX" que está detrás (gris claro al 32%, blur 2.5px). Ilegible y feo.

**Causa**: `.footer-top` con `display: flex; justify-content: space-between` pero solo tenía un único hijo (`.footer-nav`) → flex lo empujaba a la izquierda por defecto.

**Fix aplicado en `index.html` y `nosotros.html`**:
- Default: `.footer-top { justify-content: flex-end; }` (era `space-between`).
- Mobile @media ≤700px: `.footer-top { flex-direction: column; align-items: flex-end; }` (era `align-items: flex-start`). Sin esto, en mobile el column-stack volvería a alinear los items a la izquierda.

Resultado: el bloque de links queda siempre a la derecha (desktop, tablet, móvil), encima de la mitad limpia del wordmark, sin solaparse con la "N" inicial. Coherente con el patrón visual del nav (logo izquierda / links + CTA derecha).

### 6. Hero subtitle — copy más punzante (12 idiomas)

**Antes**: *"Diseñamos e implementamos sistemas de IA para empresas que quieren crecer sin crecer en plantilla."* — claro pero genérico, suena a deck de consultora.

**Ahora (ES)**: *"Tu competencia ya está usando IA. Tú sigues respondiendo el mismo WhatsApp 40 veces al día. Vamos a arreglarlo."*

**Por qué funciona mejor**:
- Estructura **3-beats**: amenaza competitiva → pintura del dolor concreto → promesa de solución (en 1ª persona del plural, "vamos").
- "Respondiendo el mismo WhatsApp 40 veces al día" es **específico, visual, dolorosamente real** para el target (PYME española / autónomo). No es un dato medio — es la imagen mental que el lead ve cuando lee la web.
- "Tu competencia ya está usando IA" introduce **FOMO comercial** sin sonar agresivo.
- "Vamos a arreglarlo" cierra con **acción colaborativa** — alinea con la voz de AdrIAn (chaval de barrio que resuelve, no agencia que vende).

**Aplicado en 12 idiomas** (objeto `HERO2` en index.html, líneas ~3895–3906) más el HTML estático (`<p class="hero-sub" id="hs">`). Cada traducción mantiene la **estructura 3-beats** sin traducir literalmente:
- EN: *"Your competition is already using AI. You're still answering the same WhatsApp 40 times a day. Let's fix that."*
- PT-BR: *"Sua concorrência já está usando IA. Você ainda responde ao mesmo WhatsApp 40 vezes por dia. Vamos resolver isso."*
- FR: *"Vos concurrents utilisent déjà l'IA. Vous répondez encore au même WhatsApp 40 fois par jour. On va régler ça."*
- DE / IT / NL / RU / ZH / JA / KO / AR siguen el mismo patrón.

**Decisión de copy**: el usuario eligió esta opción de un set de 8 propuestas agrupadas por tono (dolor-claro, concreto, aspiracional, crudo). Esta es del bucket "crudo / de barrio" — alineada deliberadamente con el SYSTEM_PROMPT de AdrIAn. Coherencia entre la voz del agente y la voz de la web.

### Estado del proyecto post 2026-05-09
- **Lead pipeline 100% en server.py**: ya no depende de n8n. Cualquier fallo de Supabase o Resend se loggea pero no rompe el endpoint público (fail-soft). El cliente recibe `{"ok": true}` siempre que la request sea válida.
- **AdrIAn cualifica activamente**: cada lead llega con `cualificado: true/false` y `notas` con el resumen de la conversación → Adri lee el email y sabe inmediatamente si vale la pena llamar.
- **Cal.com webhook listo** para conectar desde el dashboard de Cal.com (URL: `https://nyx-agency.es/api/cal-webhook`). Pendiente de configurar el subscription en la cuenta de Cal.com.
- **Voice modal usable**: transcript legible en cualquier dispositivo. El usuario puede leer la conversación mientras AdrIAn habla, no solo escucharla.
- **Footer limpio**: links a la derecha, wordmark gigante decorativo a la izquierda sin solaparse.
- **Hero copy alineado con la voz**: subtítulo del hero ahora habla el mismo idioma que AdrIAn — directo, concreto, sin floritura corporativa.
- **Pendientes (sin cambios desde sesiones previas)**: modales Privacy + T&C vacíos para RGPD, validar marcas Pulsefit/Lumea/Nordika, voice modal i18n.

