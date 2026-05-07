// Mic capture (PCM 16-bit LE mono 16kHz) + speaker playback (PCM 16-bit LE mono 24kHz).
// Uses AudioWorklet for capture, queued AudioBufferSourceNodes for playback.

const INPUT_RATE = 16000;
const OUTPUT_RATE = 24000;

const WORKLET_SOURCE = `
class PCM16Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._target = 960; // ~60ms at 16kHz — lower latency
  }
  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const channel = input[0];
    for (let i = 0; i < channel.length; i++) this._buffer.push(channel[i]);
    while (this._buffer.length >= this._target) {
      const chunk = this._buffer.splice(0, this._target);
      const pcm = new Int16Array(chunk.length);
      let sumSq = 0;
      for (let i = 0; i < chunk.length; i++) {
        let s = Math.max(-1, Math.min(1, chunk[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        sumSq += s * s;
      }
      const rms = Math.sqrt(sumSq / chunk.length);
      this.port.postMessage({ pcm: pcm.buffer, rms }, [pcm.buffer]);
    }
    return true;
  }
}
registerProcessor('pcm16-capture', PCM16Capture);
`;

function arrayBufferToBase64(buf) {
  const bytes = new Uint8Array(buf);
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(bin);
}

function base64ToArrayBuffer(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

export class MicStream {
  constructor({ onChunk, onLevel } = {}) {
    this.onChunk = onChunk || (() => {});
    this.onLevel = onLevel || (() => {});
    this.ctx = null;
    this.stream = null;
    this.workletNode = null;
    this.source = null;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    this.ctx = new AudioContext({ sampleRate: INPUT_RATE });
    if (this.ctx.state === 'suspended') await this.ctx.resume();

    const blob = new Blob([WORKLET_SOURCE], { type: 'application/javascript' });
    const url = URL.createObjectURL(blob);
    await this.ctx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);

    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.workletNode = new AudioWorkletNode(this.ctx, 'pcm16-capture');
    this.workletNode.port.onmessage = (e) => {
      const { pcm, rms } = e.data;
      this.onLevel(rms);
      this.onChunk(arrayBufferToBase64(pcm));
    };
    this.source.connect(this.workletNode);
    // Worklet doesn't need to reach destination (we don't want mic playback)
  }

  stop() {
    try { this.workletNode && this.workletNode.disconnect(); } catch {}
    try { this.source && this.source.disconnect(); } catch {}
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    if (this.ctx) this.ctx.close();
    this.ctx = null;
    this.stream = null;
    this.workletNode = null;
    this.source = null;
  }
}

export class PCMPlayer {
  constructor({ onLevel, onSpeakingChange } = {}) {
    this.onLevel = onLevel || (() => {});
    this.onSpeakingChange = onSpeakingChange || (() => {});
    this.ctx = null;
    this.gain = null;
    this.analyser = null;
    this.queueTime = 0;
    this.activeSources = 0;
    this._levelLoop = null;
    this._levelData = null;
  }

  ensure() {
    if (this.ctx) return;
    this.ctx = new AudioContext({ sampleRate: OUTPUT_RATE });
    this.gain = this.ctx.createGain();
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 256;
    this._levelData = new Uint8Array(this.analyser.frequencyBinCount);
    this.gain.connect(this.analyser);
    this.analyser.connect(this.ctx.destination);
    this.queueTime = this.ctx.currentTime;
    this._tickLevel();
  }

  async resume() {
    this.ensure();
    if (this.ctx.state === 'suspended') await this.ctx.resume();
  }

  enqueueBase64(b64) {
    this.ensure();
    const buf = base64ToArrayBuffer(b64);
    const view = new DataView(buf);
    const samples = buf.byteLength / 2;
    const audioBuf = this.ctx.createBuffer(1, samples, OUTPUT_RATE);
    const ch = audioBuf.getChannelData(0);
    for (let i = 0; i < samples; i++) {
      ch[i] = view.getInt16(i * 2, true) / 0x8000;
    }
    const src = this.ctx.createBufferSource();
    src.buffer = audioBuf;
    src.connect(this.gain);
    const startAt = Math.max(this.queueTime, this.ctx.currentTime);
    src.start(startAt);
    this.queueTime = startAt + audioBuf.duration;
    this.activeSources++;
    if (this.activeSources === 1) this.onSpeakingChange(true);
    src.onended = () => {
      this.activeSources--;
      if (this.activeSources <= 0) {
        this.activeSources = 0;
        this.onSpeakingChange(false);
      }
    };
  }

  interrupt() {
    if (!this.ctx) return;
    try {
      this.gain.disconnect();
    } catch {}
    this.gain = this.ctx.createGain();
    this.gain.connect(this.analyser);
    this.queueTime = this.ctx.currentTime;
    this.activeSources = 0;
    this.onSpeakingChange(false);
  }

  _tickLevel() {
    const loop = () => {
      if (!this.analyser) return;
      this.analyser.getByteTimeDomainData(this._levelData);
      let sumSq = 0;
      for (let i = 0; i < this._levelData.length; i++) {
        const v = (this._levelData[i] - 128) / 128;
        sumSq += v * v;
      }
      const rms = Math.sqrt(sumSq / this._levelData.length);
      this.onLevel(rms);
      this._levelLoop = requestAnimationFrame(loop);
    };
    loop();
  }

  close() {
    if (this._levelLoop) cancelAnimationFrame(this._levelLoop);
    if (this.ctx) this.ctx.close();
    this.ctx = null;
    this.gain = null;
    this.analyser = null;
  }
}

export { arrayBufferToBase64, base64ToArrayBuffer };
