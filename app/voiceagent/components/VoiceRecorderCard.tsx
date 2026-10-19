"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Mic,
  Square,
  Upload,
  Volume2,
  AlertCircle,
  CheckCircle2,
  X,
  Radio,
  Sparkles,
  FileAudio,
} from "lucide-react";
import { InputLanguageType, VoiceType } from "@/lib/types";
import {
  WavVoiceRecorder,
  normalizeAudioFileForUpload,
} from "@/lib/wavRecorder";

interface VoiceRecorderCardProps {
  disabled: boolean;
  isBusy: boolean;
  language: InputLanguageType;
  onLanguageChange: (lang: InputLanguageType) => void;
  voice: VoiceType;
  onVoiceChange: (v: VoiceType) => void;
  onAudioSubmit: (wavBlob: Blob, filename: string) => Promise<void>;
}

const LANGUAGE_META: Record<
  InputLanguageType,
  { short: string; native: string; engine: string }
> = {
  Hindi: {
    short: "Hindi",
    native: "हिंदी",
    engine: "Faster-Whisper (hi) → Coqui VITS",
  },
  English: {
    short: "English",
    native: "IN",
    engine: "Faster-Whisper (en) → Edge Neural",
  },
  Hinglish: {
    short: "Hinglish",
    native: "हिंग्लिश",
    engine: "Faster-Whisper (auto) → Hybrid TTS",
  },
  "Chhattisgarhi (experimental)": {
    short: "Chhattisgarhi",
    native: "छत्तीसगढ़ी",
    engine: "Meta MMS-1B (hne) → Local VITS",
  },
};

export default function VoiceRecorderCard({
  disabled,
  isBusy,
  language,
  onLanguageChange,
  voice,
  onVoiceChange,
  onAudioSubmit,
}: VoiceRecorderCardProps) {
  const [mode, setMode] = useState<"mic" | "upload">("mic");
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [rms, setRms] = useState(0);
  const [bars, setBars] = useState<number[]>(new Array(24).fill(0.08));
  const [localError, setLocalError] = useState<string | null>(null);
  const [lastClipUrl, setLastClipUrl] = useState<string | null>(null);
  const [lastClipDuration, setLastClipDuration] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const recorderRef = useRef<WavVoiceRecorder | null>(null);
  const stoppingRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    return () => {
      recorderRef.current?.cancel();
      if (lastClipUrl) URL.revokeObjectURL(lastClipUrl);
    };
  }, [lastClipUrl]);

  const stopAndSubmit = useCallback(async () => {
    if (!recorderRef.current || stoppingRef.current) return;
    stoppingRef.current = true;
    setRecording(false);
    try {
      const result = await recorderRef.current.stop();
      recorderRef.current = null;
      setBars(new Array(24).fill(0.08));
      setRms(0);

      if (result.durationSeconds < 0.35) {
        setLocalError(
          `Recording too short (${result.durationSeconds.toFixed(1)}s). Please speak for at least 0.5 seconds.`
        );
        stoppingRef.current = false;
        return;
      }
      if (result.peakRms < 0.002) {
        setLocalError(
          "No clear speech energy detected (RMS < 0.002). Please check your microphone and speak clearly."
        );
        stoppingRef.current = false;
        return;
      }

      if (lastClipUrl) URL.revokeObjectURL(lastClipUrl);
      const url = URL.createObjectURL(result.blob);
      setLastClipUrl(url);
      setLastClipDuration(result.durationSeconds);

      setSubmitting(true);
      await onAudioSubmit(result.blob, `mic-${Date.now()}.wav`);
    } catch (err) {
      setLocalError(
        err instanceof Error ? err.message : "Failed to process recording."
      );
    } finally {
      setSubmitting(false);
      stoppingRef.current = false;
    }
  }, [lastClipUrl, onAudioSubmit]);

  const startRecording = async () => {
    if (disabled || isBusy || submitting) return;
    setLocalError(null);
    const rec = new WavVoiceRecorder();
    recorderRef.current = rec;
    stoppingRef.current = false;
    try {
      await rec.start((reading) => {
        setRms(reading.rms);
        setElapsed(reading.elapsedSeconds);
        setBars(reading.bars);
        // Auto-stop at 29.4s to stay safely within Demo 2's 30.0s hard cap
        if (reading.elapsedSeconds >= 29.4 && !stoppingRef.current) {
          stopAndSubmit();
        }
      });
      setRecording(true);
      setElapsed(0);
    } catch (err) {
      recorderRef.current = null;
      setLocalError(
        err instanceof Error
          ? err.message
          : "Microphone access denied. Ensure you are on localhost or HTTPS."
      );
    }
  };

  const cancelRecording = () => {
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setRecording(false);
    setElapsed(0);
    setRms(0);
    setBars(new Array(24).fill(0.08));
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLocalError(null);
    if (file.size > 12 * 1024 * 1024) {
      setLocalError("Audio file must be smaller than 12 MB.");
      e.target.value = "";
      return;
    }
    setSubmitting(true);
    try {
      const normalized = await normalizeAudioFileForUpload(file);
      if (lastClipUrl) URL.revokeObjectURL(lastClipUrl);
      setLastClipUrl(URL.createObjectURL(normalized));
      setLastClipDuration(null);
      await onAudioSubmit(normalized, normalized.name);
    } catch (err) {
      setLocalError(
        err instanceof Error
          ? err.message
          : "Could not decode uploaded audio file. Use a valid WAV or FLAC file (0.3–30s)."
      );
    } finally {
      setSubmitting(false);
      e.target.value = "";
    }
  };

  const formatSec = (s: number) => {
    const sec = Math.floor(s);
    const tenths = Math.floor((s - sec) * 10);
    return `${String(sec).padStart(2, "0")}.${tenths}s`;
  };

  const voiceDetected = rms >= 0.002;

  return (
    <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900/90 shadow-sm overflow-hidden">
      {/* Top Studio Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 bg-slate-50/80 dark:bg-slate-950/60 border-b border-slate-200/70 dark:border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/10 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-400">
            <Radio className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Start with your voice
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
                16 kHz Mono PCM
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {LANGUAGE_META[language].engine}
            </p>
          </div>
        </div>

        {/* Mode Switcher + Quick Voice Toggle */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg bg-slate-200/70 dark:bg-slate-800 p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => {
                if (recording) cancelRecording();
                setMode("mic");
              }}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 transition ${
                mode === "mic"
                  ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              <Mic className="h-3.5 w-3.5" />
              Microphone
            </button>
            <button
              type="button"
              onClick={() => {
                if (recording) cancelRecording();
                setMode("upload");
              }}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 transition ${
                mode === "upload"
                  ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              <Upload className="h-3.5 w-3.5" />
              Upload WAV/FLAC
            </button>
          </div>

          <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700/80 bg-white dark:bg-slate-900 p-0.5 text-xs">
            {(["Female", "Male"] as VoiceType[]).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => onVoiceChange(v)}
                className={`flex items-center gap-1 rounded-md px-2.5 py-1 font-medium transition ${
                  voice === v
                    ? "bg-indigo-600 text-white"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                }`}
                title={`Select ${v} synthesis voice`}
              >
                <Volume2 className="h-3 w-3" />
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Language Quick Selector Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-2.5 bg-slate-50/40 dark:bg-slate-900/40 border-b border-slate-100 dark:border-slate-800/60">
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
          Recognition Language:
        </span>
        <div className="flex flex-wrap items-center gap-1.5">
          {(Object.keys(LANGUAGE_META) as InputLanguageType[]).map((lang) => {
            const active = language === lang;
            const meta = LANGUAGE_META[lang];
            return (
              <button
                key={lang}
                type="button"
                disabled={recording}
                onClick={() => onLanguageChange(lang)}
                className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition border ${
                  active
                    ? "border-indigo-600 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-950/70 dark:text-indigo-200"
                    : "border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:border-slate-300"
                }`}
              >
                <span>{meta.short}</span>
                <span className="text-[11px] opacity-75">· {meta.native}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Studio Body */}
      <div className="p-5">
        {mode === "mic" ? (
          <div className="flex flex-col md:flex-row items-center justify-between gap-5">
            {/* Left: Main Mic Button + Status */}
            <div className="flex items-center gap-4 w-full md:w-auto">
              {!recording ? (
                <button
                  type="button"
                  disabled={disabled || isBusy || submitting}
                  onClick={startRecording}
                  className="group relative flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-500/20 transition hover:scale-[1.03] hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
                  aria-label="Start recording question"
                >
                  <Mic className="h-7 w-7 transition-transform group-hover:scale-110" />
                  <span className="sr-only">Record your question</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={stopAndSubmit}
                  className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-rose-600 text-white shadow-lg shadow-rose-500/30 transition hover:bg-rose-500 cursor-pointer animate-pulse"
                  aria-label="Stop recording and submit"
                >
                  <Square className="h-6 w-6 fill-current" />
                </button>
              )}

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-semibold text-slate-900 dark:text-white">
                    {recording
                      ? "Listening… Tap Stop to submit"
                      : submitting
                      ? "Submitting audio turn…"
                      : isBusy
                      ? "Processing active turn…"
                      : "Tap microphone to speak your question"}
                  </h3>
                  {recording && (
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        voiceDetected
                          ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                          : "bg-amber-500/15 text-amber-700 dark:text-amber-300"
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          voiceDetected ? "bg-emerald-500" : "bg-amber-500"
                        }`}
                      />
                      {voiceDetected ? "Speech Active" : "Waiting for speech"}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Stop recording to receive an automatic spoken answer with verified citations (0.3–30 seconds, localhost/HTTPS).
                </p>
                {recording && (
                  <div className="mt-2 flex items-center gap-3">
                    <span className="font-mono text-xs font-semibold text-rose-600 dark:text-rose-400">
                      {formatSec(elapsed)} / 30.0s
                    </span>
                    <span className="font-mono text-[11px] text-slate-500">
                      RMS: {rms.toFixed(4)} (gate ≥ 0.0020)
                    </span>
                    <button
                      type="button"
                      onClick={cancelRecording}
                      className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      <X className="h-3.5 w-3.5" />
                      Discard
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Live Equalizer / Last Recorded Preview */}
            <div className="flex flex-col items-end gap-2 w-full md:w-auto">
              <div className="flex items-center justify-center gap-1 h-12 px-4 py-2 rounded-xl bg-slate-950/5 dark:bg-slate-950/70 border border-slate-200/60 dark:border-slate-800 w-full md:w-64">
                {bars.map((val, idx) => (
                  <div
                    key={idx}
                    className={`w-1.5 rounded-full transition-all duration-75 ${
                      recording
                        ? voiceDetected
                          ? "bg-indigo-600 dark:bg-indigo-400"
                          : "bg-amber-500"
                        : "bg-slate-300 dark:bg-slate-700"
                    }`}
                    style={{
                      height: `${Math.max(14, Math.min(100, Math.round(val * 100)))}%`,
                    }}
                  />
                ))}
              </div>
              {lastClipUrl && !recording && (
                <div className="flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                  <span>
                    Last clip{lastClipDuration ? ` (${lastClipDuration.toFixed(1)}s)` : ""}:
                  </span>
                  <audio
                    src={lastClipUrl}
                    controls
                    className="h-6 w-40 opacity-85"
                  />
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Upload WAV / FLAC Mode */
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/30 p-4">
            <div className="flex items-center gap-3.5">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-indigo-600/10 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-400">
                <FileAudio className="h-6 w-6" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                  Choose a WAV or FLAC recording
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Mono or stereo audio, 0.3–30 seconds, up to 12 MB. Resampled automatically to 16 kHz PCM.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <input
                ref={fileInputRef}
                type="file"
                accept=".wav,.flac,audio/wav,audio/x-wav,audio/flac"
                onChange={handleFileChange}
                disabled={disabled || isBusy || submitting}
                className="hidden"
              />
              <button
                type="button"
                disabled={disabled || isBusy || submitting}
                onClick={() => fileInputRef.current?.click()}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-indigo-500 disabled:opacity-50 cursor-pointer"
              >
                <Upload className="h-4 w-4" />
                {submitting ? "Uploading & Transcribing…" : "Select Audio File"}
              </button>
            </div>
          </div>
        )}

        {localError && (
          <div className="mt-3 flex items-center justify-between gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-xs text-amber-800 dark:text-amber-200">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <span>{localError}</span>
            </div>
            <button
              type="button"
              onClick={() => setLocalError(null)}
              className="text-amber-700 dark:text-amber-300 hover:underline text-[11px]"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
