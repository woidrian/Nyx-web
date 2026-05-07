// Gemini Live API WebSocket client (constrained endpoint, ephemeral token).
// The system prompt + tool config is LOCKED inside the token, so the setup
// payload only needs to acknowledge the model.

const WS_BASE =
  'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained';

export class GeminiLiveClient {
  constructor({
    onOpen,
    onSetupComplete,
    onAudio,
    onTextDelta,
    onInputTranscript,
    onOutputTranscript,
    onToolCall,
    onTurnComplete,
    onInterrupted,
    onError,
    onClose,
  } = {}) {
    this.onOpen = onOpen || (() => {});
    this.onSetupComplete = onSetupComplete || (() => {});
    this.onAudio = onAudio || (() => {});
    this.onTextDelta = onTextDelta || (() => {});
    this.onInputTranscript = onInputTranscript || (() => {});
    this.onOutputTranscript = onOutputTranscript || (() => {});
    this.onToolCall = onToolCall || (() => {});
    this.onTurnComplete = onTurnComplete || (() => {});
    this.onInterrupted = onInterrupted || (() => {});
    this.onError = onError || (() => {});
    this.onClose = onClose || (() => {});
    this.ws = null;
    this.ready = false;
  }

  async connect(token, model = 'gemini-3.1-flash-live-preview') {
    return new Promise((resolve, reject) => {
      const url = `${WS_BASE}?access_token=${encodeURIComponent(token)}`;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.onOpen();
        // Setup is locked in token, but we still send a setup frame.
        this.ws.send(
          JSON.stringify({
            setup: {
              model: `models/${model}`,
              inputAudioTranscription: {},
              outputAudioTranscription: {},
            },
          })
        );
      };

      this.ws.onmessage = async (ev) => {
        let raw = ev.data;
        if (raw instanceof Blob) raw = await raw.text();
        let msg;
        try {
          msg = JSON.parse(raw);
        } catch (e) {
          this.onError(new Error('non-JSON message: ' + raw));
          return;
        }
        this._handleMessage(msg, resolve);
      };

      this.ws.onerror = (e) => {
        if (this._intentionalClose) return;
        this.onError(e);
        if (!this.ready) reject(new Error('ws connection error'));
      };

      this.ws.onclose = (e) => {
        const wasReady = this.ready;
        this.ready = false;
        this.onClose(e);
        if (!wasReady && !this._intentionalClose) {
          reject(new Error('ws closed before setup: ' + (e && e.code)));
        }
      };
    });
  }

  _handleMessage(msg, resolveSetup) {
    const keys = Object.keys(msg);
    console.log('[nyx] ws msg keys:', keys);

    if (msg.setupComplete) {
      this.ready = true;
      this.onSetupComplete();
      resolveSetup && resolveSetup();
      return;
    }

    if (msg.serverContent) {
      const sc = msg.serverContent;
      console.log('[nyx] serverContent:', JSON.stringify(sc).slice(0, 400));
      if (sc.interrupted) this.onInterrupted();
      if (sc.inputTranscription && sc.inputTranscription.text) {
        this.onInputTranscript(sc.inputTranscription.text, !!sc.inputTranscription.finished);
      }
      if (sc.outputTranscription && sc.outputTranscription.text) {
        this.onOutputTranscript(sc.outputTranscription.text, !!sc.outputTranscription.finished);
      }
      if (sc.modelTurn && sc.modelTurn.parts) {
        for (const part of sc.modelTurn.parts) {
          if (part.inlineData && part.inlineData.data) {
            this.onAudio(part.inlineData.data, part.inlineData.mimeType || '');
          }
          // Ignoramos part.text aquí — el texto del agente viene por
          // outputTranscription. Si llega text extra, sería duplicado.
        }
      }
      if (sc.turnComplete) this.onTurnComplete();
      return;
    }

    if (msg.toolCall) {
      const calls = msg.toolCall.functionCalls || [];
      for (const fc of calls) this.onToolCall(fc);
      return;
    }

    if (msg.toolCallCancellation) {
      // No-op for this demo.
      return;
    }

    if (msg.goAway) {
      this.onError(new Error('server goAway'));
      return;
    }
  }

  sendAudioChunk(b64Pcm16k) {
    if (!this.ready) return;
    this._sentChunks = (this._sentChunks || 0) + 1;
    if (this._sentChunks % 20 === 1) console.log('[nyx] audio chunks sent:', this._sentChunks);
    this.ws.send(
      JSON.stringify({
        realtimeInput: {
          audio: { mimeType: 'audio/pcm;rate=16000', data: b64Pcm16k },
        },
      })
    );
  }

  sendUserText(text) {
    if (!this.ready) return;
    console.log('[nyx] sending user text:', text);
    this.ws.send(
      JSON.stringify({
        clientContent: {
          turns: [{ role: 'user', parts: [{ text }] }],
          turnComplete: true,
        },
      })
    );
  }

  // Manual activity detection — usado cuando automatic_activity_detection
  // está desactivado en el server config. El cliente delimita cada turno.
  sendActivityStart() {
    if (!this.ready) return;
    console.log('[nyx] sending activityStart');
    this.ws.send(JSON.stringify({ realtimeInput: { activityStart: {} } }));
  }

  sendActivityEnd() {
    if (!this.ready) return;
    console.log('[nyx] sending activityEnd');
    this.ws.send(JSON.stringify({ realtimeInput: { activityEnd: {} } }));
  }

  sendToolResponse(id, name, response) {
    if (!this.ready) return;
    this.ws.send(
      JSON.stringify({
        toolResponse: {
          functionResponses: [{ id, name, response }],
        },
      })
    );
  }

  close() {
    this._intentionalClose = true;
    this.ready = false;
    if (this.ws) {
      try { this.ws.close(); } catch {}
    }
    this.ws = null;
  }
}
