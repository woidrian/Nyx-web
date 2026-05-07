// State machine + transcript orchestration for AdrIAn.
// States: idle | connecting | listening | speaking | error
//
// This module is loaded lazily by index.html when the user opens the
// "Habla con AdrIAn" modal. The constructor receives the modal element
// as `root`, and all DOM lookups + the data-state attribute are scoped
// to that subtree so we don't collide with the rest of the page.

import { MicStream, PCMPlayer } from './audio.js';
import { GeminiLiveClient } from './geminilive.js';

const STATES = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  LISTENING: 'listening',
  SPEAKING: 'speaking',
  ENDED: 'ended',
  ERROR: 'error',
};

export class VoiceAgent {
  constructor({ root }) {
    this.root = root;
    this.btn = root.querySelector('#mic-btn');
    this.statusEl = root.querySelector('#status');
    this.transcriptEl = root.querySelector('#transcript');
    this.canvas = root.querySelector('#viz');
    this.ctx2d = this.canvas.getContext('2d');
    this.endBtn = root.querySelector('#end-btn');
    this.restartBtn = root.querySelector('#restart-btn');

    this.state = STATES.IDLE;
    this.client = null;
    this.mic = null;
    this._leadSaved = false;
    this.player = new PCMPlayer({
      onLevel: (lvl) => { this._outLevel = lvl; },
      onSpeakingChange: (speaking) => {
        if (speaking) this._setState(STATES.SPEAKING);
        else if (this.state === STATES.SPEAKING) this._setState(STATES.LISTENING);
      },
    });
    this._inLevel = 0;
    this._outLevel = 0;
    this._currentUserLine = '';
    this._currentAgentLine = '';

    if (!this.btn) {
      console.error('[nyx] #mic-btn NOT FOUND in modal');
      return;
    }
    this.btn.addEventListener('click', () => this.toggle());
    if (this.endBtn) {
      this.endBtn.addEventListener('click', () => this._endConversation());
    }
    if (this.restartBtn) {
      this.restartBtn.addEventListener('click', () => this.start());
    }
    this._resizeCanvas();
    this._resizeHandler = () => this._resizeCanvas();
    window.addEventListener('resize', this._resizeHandler);
    this._renderViz();
    this._setState(STATES.IDLE);
  }

  _setState(s) {
    this.state = s;
    this.root.dataset.state = s;
    const labels = {
      idle: 'Pulsa para hablar',
      connecting: 'Conectando…',
      listening: 'Escuchando',
      speaking: 'AdrIAn habla',
      ended: 'Volver a hablar',
      error: 'Error de conexión',
    };
    if (this.statusEl) this.statusEl.textContent = labels[s] || s;
    if (this.btn) {
      this.btn.setAttribute(
        'aria-label',
        s === 'ended' ? 'Iniciar nueva conversación' : 'Activar micrófono'
      );
    }
  }

  _appendTranscript(role, text) {
    let bubble = this.transcriptEl.querySelector(`.bubble.${role}.live`);
    if (!bubble) {
      bubble = document.createElement('div');
      bubble.className = `bubble ${role} live`;
      this.transcriptEl.appendChild(bubble);
    }
    bubble.textContent = text;
    this.transcriptEl.scrollTop = this.transcriptEl.scrollHeight;
  }

  _finalizeTranscript(role) {
    const bubble = this.transcriptEl.querySelector(`.bubble.${role}.live`);
    if (bubble) bubble.classList.remove('live');
  }

  async toggle() {
    if (
      this.state === STATES.IDLE ||
      this.state === STATES.ERROR ||
      this.state === STATES.ENDED
    ) {
      await this.start();
    } else {
      this.stop();
    }
  }

  _endConversation() {
    if (this.mic) { this.mic.stop(); this.mic = null; }
    if (this.client) { this.client.close(); this.client = null; }
    this._setState(STATES.ENDED);
  }

  async start() {
    try {
      this._setState(STATES.CONNECTING);
      this.transcriptEl.innerHTML = '';
      this._leadSaved = false;
      this._micGateOpen = false;

      this.mic = new MicStream({
        onChunk: (b64) => {
          if (!this._micGateOpen) return;
          if (this.client) this.client.sendAudioChunk(b64);
        },
        onLevel: (lvl) => { this._inLevel = lvl; },
      });
      await this.mic.start();

      await this.player.resume();

      const tokenRes = await fetch('/api/token');
      if (!tokenRes.ok) {
        const txt = await tokenRes.text();
        throw new Error('token fetch failed ' + tokenRes.status + ': ' + txt);
      }
      const { token, model } = await tokenRes.json();

      this.client = new GeminiLiveClient({
        onAudio: (b64) => this.player.enqueueBase64(b64),
        onInputTranscript: (text, finished) => {
          this._currentUserLine = this._currentUserLine + text;
          this._appendTranscript('user', this._currentUserLine);
          if (finished) {
            this._currentUserLine = '';
            this._finalizeTranscript('user');
          }
        },
        onOutputTranscript: (text, finished) => {
          this._currentAgentLine = this._currentAgentLine + text;
          this._appendTranscript('agent', this._currentAgentLine);
          if (finished) {
            this._currentAgentLine = '';
            this._finalizeTranscript('agent');
          }
        },
        onToolCall: (fc) => this._handleToolCall(fc),
        onInterrupted: () => {
          this.player.interrupt();
          this._currentAgentLine = '';
        },
        onTurnComplete: () => {
          this._currentAgentLine = '';
          this._currentUserLine = '';
          this._finalizeTranscript('agent');
          this._finalizeTranscript('user');
          if (this._leadSaved) {
            setTimeout(() => this._endConversation(), 800);
          }
        },
        onError: (e) => {
          console.error('[nyx] gemini error', e);
          if (this.state !== STATES.ENDED && this.state !== STATES.IDLE) {
            this._setState(STATES.ERROR);
          }
        },
        onClose: (e) => {
          if (this.state === STATES.ENDED || this.state === STATES.ERROR) return;
          this._setState(STATES.IDLE);
        },
      });

      const wsConnectPromise = this.client.connect(token, model);

      this._setState(STATES.SPEAKING);
      const greetingPromise = this._playGreeting();

      await Promise.all([wsConnectPromise, greetingPromise]);

      this._micGateOpen = true;
      this._setState(STATES.LISTENING);
    } catch (e) {
      console.error('[nyx] start() failed', e);
      this._setState(STATES.ERROR);
      this.stop();
    }
  }

  stop() {
    if (this.mic) { this.mic.stop(); this.mic = null; }
    if (this.client) { this.client.close(); this.client = null; }
    if (this._greetingAudio) {
      try { this._greetingAudio.pause(); this._greetingAudio.currentTime = 0; } catch {}
      this._greetingAudio = null;
    }
    this._setState(STATES.IDLE);
  }

  destroy() {
    this.stop();
    if (this._resizeHandler) window.removeEventListener('resize', this._resizeHandler);
    if (this._vizRaf) cancelAnimationFrame(this._vizRaf);
  }

  _playGreeting() {
    return new Promise((resolve) => {
      const text = 'Hola, soy AdrIAn de Nyx Agency. ¿En qué tipo de negocio trabajas y cuál es vuestro mayor reto operativo?';
      const bubble = document.createElement('div');
      bubble.className = 'bubble agent';
      bubble.textContent = text;
      this.transcriptEl.appendChild(bubble);
      this.transcriptEl.scrollTop = this.transcriptEl.scrollHeight;

      const audio = new Audio(`/voice/greeting.wav?v=${Date.now()}`);
      audio.preload = 'auto';
      audio.onended = () => resolve();
      audio.onerror = (e) => {
        console.warn('[nyx] greeting audio error', e);
        resolve();
      };
      this._greetingAudio = audio;
      audio.play().catch((err) => {
        console.warn('[nyx] greeting play() failed', err);
        resolve();
      });
    });
  }

  async _handleToolCall(fc) {
    if (fc.name !== 'guardar_lead') return;
    const args = fc.args || {};
    let response;
    try {
      const r = await fetch('/api/lead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args),
      });
      response = r.ok
        ? { success: true, message: 'Lead guardado correctamente' }
        : { success: false, error: 'webhook_failed', status: r.status };
    } catch (e) {
      response = { success: false, error: String(e) };
    }
    this._leadSaved = true;
    if (this.client) this.client.sendToolResponse(fc.id, fc.name, response);
  }

  _resizeCanvas() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const r = this.canvas.getBoundingClientRect();
    this.canvas.width = Math.round(r.width * dpr);
    this.canvas.height = Math.round(r.height * dpr);
  }

  _renderViz() {
    const draw = () => {
      const c = this.canvas;
      const g = this.ctx2d;
      const w = c.width;
      const h = c.height;
      g.clearRect(0, 0, w, h);

      const isSpeak = this.state === STATES.SPEAKING;
      const isListen = this.state === STATES.LISTENING;
      const level = isSpeak ? this._outLevel : this._inLevel;

      const t = performance.now() / 1000;
      const bars = 48;
      const bw = w / bars;
      const accent = '#c8ff00';
      const dim = 'rgba(200,255,0,0.18)';

      for (let i = 0; i < bars; i++) {
        const x = i * bw + bw * 0.2;
        const phase = i / bars;
        const wave = (Math.sin(t * 2.4 + phase * 6.28) + 1) / 2;
        const baseAmp = isListen || isSpeak ? 0.06 : 0.02;
        const reactive = (level || 0) * 2.4;
        const amp = Math.min(1, baseAmp + reactive * (0.4 + 0.6 * wave));
        const barH = amp * h * 0.9;
        const y = (h - barH) / 2;
        g.fillStyle = isSpeak || isListen ? accent : dim;
        g.fillRect(x, y, bw * 0.6, barH);
      }

      this._vizRaf = requestAnimationFrame(draw);
    };
    draw();
  }
}
