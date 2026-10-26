/**
 * Browser Web Audio API Recorder that outputs canonical 16 kHz Mono 16-bit PCM WAV
 * compatible with Demo 2's speech.decode_audio() contract (0.3s - 30s, RMS >= 0.002).
 */

export interface AudioMeterReading {
  rms: number;
  elapsedSeconds: number;
  bars: number[];
}

export interface RecordedWavResult {
  blob: Blob;
  durationSeconds: number;
  peakRms: number;
  averageRms: number;
  sampleRate: number;
}

const TARGET_SAMPLE_RATE = 16000;

function downsampleFloat32(
  buffer: Float32Array,
  inputRate: number,
  outputRate: number
): Float32Array {
  if (inputRate === outputRate) return buffer;
  const ratio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (
      let i = offsetBuffer;
      i < nextOffsetBuffer && i < buffer.length;
      i++
    ) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

export function encodeMonoWav(
  samples: Float32Array,
  sampleRate: number = TARGET_SAMPLE_RATE
): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM format = 1
  view.setUint16(22, 1, true); // Mono = 1 channel
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // Byte rate
  view.setUint16(32, 2, true); // Block align
  view.setUint16(34, 16, true); // 16 bits per sample
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return new Blob([buffer], { type: "audio/wav" });
}

export class WavVoiceRecorder {
  private stream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private analyserNode: AnalyserNode | null = null;
  private processorNode: ScriptProcessorNode | null = null;
  private chunks: Float32Array[] = [];
  private startTime = 0;
  private meterTimer: number | null = null;
  private peakRms = 0;
  private rmsSum = 0;
  private rmsCount = 0;
  private inputSampleRate = 48000;

  async start(onMeter?: (reading: AudioMeterReading) => void): Promise<void> {
    if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      throw new Error(
        "Microphone capture requires a modern browser on localhost or HTTPS."
      );
    }

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    this.audioCtx = new AudioContextClass();
    // Modern browsers keep AudioContext suspended until resumed after a user gesture.
    // Without this, onaudioprocess fires with all-zero buffers → RMS stays 0.
    if (this.audioCtx.state === "suspended") {
      await this.audioCtx.resume();
    }
    this.inputSampleRate = this.audioCtx.sampleRate;
    this.chunks = [];
    this.peakRms = 0;
    this.rmsSum = 0;
    this.rmsCount = 0;
    this.startTime = performance.now();

    this.sourceNode = this.audioCtx.createMediaStreamSource(this.stream);
    this.analyserNode = this.audioCtx.createAnalyser();
    this.analyserNode.fftSize = 64;
    this.analyserNode.smoothingTimeConstant = 0.7;

    this.processorNode = this.audioCtx.createScriptProcessor(4096, 1, 1);
    this.processorNode.onaudioprocess = (event: AudioProcessingEvent) => {
      const input = event.inputBuffer.getChannelData(0);
      const copy = new Float32Array(input.length);
      copy.set(input);
      this.chunks.push(copy);

      let sumSq = 0;
      for (let i = 0; i < copy.length; i++) {
        sumSq += copy[i] * copy[i];
      }
      const rms = Math.sqrt(sumSq / copy.length);
      if (rms > this.peakRms) this.peakRms = rms;
      this.rmsSum += rms;
      this.rmsCount += 1;
    };

    this.sourceNode.connect(this.analyserNode);
    this.analyserNode.connect(this.processorNode);
    this.processorNode.connect(this.audioCtx.destination);

    if (onMeter && this.analyserNode) {
      const freqData = new Uint8Array(this.analyserNode.frequencyBinCount);
      const timeData = new Float32Array(this.analyserNode.fftSize);
      this.meterTimer = window.setInterval(() => {
        if (!this.analyserNode) return;
        this.analyserNode.getByteFrequencyData(freqData);
        this.analyserNode.getFloatTimeDomainData(timeData);

        let sumSq = 0;
        for (let i = 0; i < timeData.length; i++) {
          sumSq += timeData[i] * timeData[i];
        }
        const liveRms = Math.sqrt(sumSq / timeData.length);
        const bars = Array.from(freqData.slice(0, 24)).map((v) =>
          Math.max(0.06, v / 255)
        );
        const elapsedSeconds = (performance.now() - this.startTime) / 1000;
        onMeter({ rms: liveRms, elapsedSeconds, bars });
      }, 60);
    }
  }

  async stop(): Promise<RecordedWavResult> {
    if (this.meterTimer !== null) {
      clearInterval(this.meterTimer);
      this.meterTimer = null;
    }
    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode.onaudioprocess = null;
      this.processorNode = null;
    }
    if (this.analyserNode) {
      this.analyserNode.disconnect();
      this.analyserNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.audioCtx) {
      try {
        await this.audioCtx.close();
      } catch {
        // Ignore close errors
      }
      this.audioCtx = null;
    }

    const totalLength = this.chunks.reduce((acc, c) => acc + c.length, 0);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of this.chunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    this.chunks = [];

    const durationSeconds = totalLength / this.inputSampleRate;
    const resampled = downsampleFloat32(
      merged,
      this.inputSampleRate,
      TARGET_SAMPLE_RATE
    );
    const wavBlob = encodeMonoWav(resampled, TARGET_SAMPLE_RATE);

    return {
      blob: wavBlob,
      durationSeconds,
      peakRms: this.peakRms,
      averageRms: this.rmsCount > 0 ? this.rmsSum / this.rmsCount : 0,
      sampleRate: TARGET_SAMPLE_RATE,
    };
  }

  cancel(): void {
    if (this.meterTimer !== null) {
      clearInterval(this.meterTimer);
      this.meterTimer = null;
    }
    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode.onaudioprocess = null;
      this.processorNode = null;
    }
    if (this.analyserNode) {
      this.analyserNode.disconnect();
      this.analyserNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close().catch(() => {});
      this.audioCtx = null;
    }
    this.chunks = [];
  }
}

export async function normalizeAudioFileForUpload(file: File): Promise<File> {
  const lower = file.name.toLowerCase();
  if (lower.endsWith(".wav") || lower.endsWith(".flac")) {
    return file;
  }
  const arrayBuffer = await file.arrayBuffer();
  const AudioContextClass =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext })
      .webkitAudioContext;
  const ctx = new AudioContextClass();
  try {
    const decoded = await ctx.decodeAudioData(arrayBuffer);
    const ch0 = decoded.getChannelData(0);
    let mono: Float32Array;
    if (decoded.numberOfChannels > 1) {
      const ch1 = decoded.getChannelData(1);
      mono = new Float32Array(ch0.length);
      for (let i = 0; i < ch0.length; i++) {
        mono[i] = (ch0[i] + ch1[i]) * 0.5;
      }
    } else {
      mono = ch0;
    }
    const resampled = downsampleFloat32(
      mono,
      decoded.sampleRate,
      TARGET_SAMPLE_RATE
    );
    const wavBlob = encodeMonoWav(resampled, TARGET_SAMPLE_RATE);
    const baseName = file.name.replace(/\.[^/.]+$/, "");
    return new File([wavBlob], `${baseName}.wav`, { type: "audio/wav" });
  } finally {
    await ctx.close().catch(() => {});
  }
}
