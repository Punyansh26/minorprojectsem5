"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  User,
  Bot,
  FileText,
  ExternalLink,
  Download,
  Volume2,
  RefreshCw,
  XCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  ShieldCheck,
  AlertTriangle,
  Ticket,
  Mic,
  Cpu,
  Database,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { TurnSnapshot, StaffTicket } from "@/lib/types";
import StreamingAnswer from "./StreamingAnswer";

interface TurnCardProps {
  sessionId: string;
  turn: TurnSnapshot;
  ticket?: StaffTicket;
  defaultProvider: string;
  autoplay: boolean;
  alreadyPlayed: boolean;
  isNewTurn?: boolean;
  onStreamComplete?: (turnId: string) => void;
  onMarkPlayed: (turnId: string) => void;
  onCancel: (turnId: string) => void;
  onRetryTurn: (turnId: string) => void;
  onRetryAudio: (turnId: string) => void;
}

const PIPELINE_STEPS = [
  { key: "queued", label: "Queue" },
  { key: "transcribing", label: "ASR / STT" },
  { key: "routing", label: "Intent Router" },
  { key: "retrieval", label: "3-Way Hybrid RAG" },
  { key: "answer", label: "2-Pass Grounding" },
  { key: "speech", label: "Neural TTS" },
];

function resolveStepIndex(stage: string): number {
  if (stage === "queued") return 0;
  if (stage === "transcribing") return 1;
  if (stage === "reasoning" || stage === "routing" || stage === "routing_model")
    return 2;
  if (stage === "retrieval") return 3;
  if (
    stage === "answer" ||
    stage === "generation_model" ||
    stage === "review_model" ||
    stage === "saving_action"
  )
    return 4;
  if (stage === "speech") return 5;
  return 6;
}

export default function TurnCard({
  sessionId,
  turn,
  ticket,
  defaultProvider,
  autoplay,
  alreadyPlayed,
  isNewTurn,
  onStreamComplete,
  onMarkPlayed,
  onCancel,
  onRetryTurn,
  onRetryAudio,
}: TurnCardProps) {
  const [showSources, setShowSources] = useState(false);
  const [showSpokenText, setShowSpokenText] = useState(false);
  const [showTimings, setShowTimings] = useState(false);
  const [showTicket, setShowTicket] = useState(false);
  const [autoplayBlocked, setAutoplayBlocked] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  const isVoiceTurn = turn.id.startsWith("recording:");
  const audioStreamUrl = turn.audio?.available
    ? `/api/py${turn.audio.url.replace(/^\/api/, "")}`
    : null;
  const audioDownloadUrl = turn.audio?.available
    ? `/api/py/turns/${sessionId}/${encodeURIComponent(turn.id)}/audio?download=true`
    : null;

  useEffect(() => {
    if (
      audioStreamUrl &&
      autoplay &&
      !alreadyPlayed &&
      audioRef.current
    ) {
      onMarkPlayed(turn.id);
      audioRef.current.play().catch(() => {
        setAutoplayBlocked(true);
      });
    }
  }, [audioStreamUrl, autoplay, alreadyPlayed, turn.id, onMarkPlayed]);

  const metrics = turn.rag_metrics || {};
  const timings = turn.timings || {};
  const stepIdx = resolveStepIndex(turn.stage);

  const timingParts: string[] = [];
  if (typeof timings.queue_seconds === "number") {
    timingParts.push(`Queue ${timings.queue_seconds.toFixed(1)}s`);
  }
  if (typeof timings.stt_seconds === "number") {
    timingParts.push(`STT ${timings.stt_seconds.toFixed(1)}s`);
  }
  if (typeof turn.agent_seconds === "number") {
    timingParts.push(`Answer ${turn.agent_seconds.toFixed(1)}s`);
  }
  if (typeof timings.reviewed_text_seconds === "number") {
    timingParts.push(`Text ready ${timings.reviewed_text_seconds.toFixed(1)}s`);
  }
  if (typeof turn.speech_seconds === "number") {
    timingParts.push(`Speech ${turn.speech_seconds.toFixed(1)}s`);
  }
  if (typeof timings.audio_ready_seconds === "number") {
    timingParts.push(`Total ${timings.audio_ready_seconds.toFixed(1)}s`);
  }

  const stageMsEntries = timings.stage_ms
    ? Object.entries(timings.stage_ms)
    : [];
  const maxStageMs =
    stageMsEntries.length > 0
      ? Math.max(...stageMsEntries.map(([, v]) => v), 1)
      : 1;

  return (
    <div className="space-y-3">
      {/* User Message Bubble */}
      <div className="flex items-start justify-end gap-3">
        <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-3 text-white shadow-xs">
          <div className="flex items-center gap-2 mb-1">
            {isVoiceTurn && (
              <span className="inline-flex items-center gap-1 rounded-full bg-white/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-indigo-100">
                <Mic className="h-2.5 w-2.5" />
                Voice Utterance
              </span>
            )}
            <span className="text-[11px] text-indigo-200 font-medium">You</span>
          </div>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {turn.question ||
              (turn.stage === "transcribing" || turn.stage === "queued"
                ? "Transcribing recorded question…"
                : "Recorded question")}
          </p>
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600/10 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-300 border border-indigo-500/20">
          <User className="h-4 w-4" />
        </div>
      </div>

      {/* Assistant Response Card */}
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-600/10 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300 border border-emerald-500/20">
          <Bot className="h-4 w-4" />
        </div>

        <div className="flex-1 min-w-0 rounded-2xl rounded-tl-sm border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs overflow-hidden">
          {/* Header status strip */}
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 bg-slate-50/80 dark:bg-slate-950/50 border-b border-slate-100 dark:border-slate-800/70">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                IIIT-NR Grounded Assistant
              </span>
              {turn.language && (
                <span className="rounded-md bg-slate-200/70 dark:bg-slate-800 px-2 py-0.5 text-[11px] font-medium capitalize text-slate-700 dark:text-slate-300">
                  {turn.language}
                </span>
              )}
              {turn.response_status === "answered" && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
                  <ShieldCheck className="h-3 w-3" />
                  2-Pass Grounding Verified
                </span>
              )}
              {turn.response_status === "insufficient" && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-300 border border-amber-500/20">
                  <AlertTriangle className="h-3 w-3" />
                  Abstained (Unverified in Official Docs)
                </span>
              )}
            </div>

            {/* Active processing stage badge + Cancel */}
            {!turn.is_terminal && (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs font-medium text-indigo-700 dark:text-indigo-300">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {turn.stage_label}
                </span>
                <button
                  type="button"
                  onClick={() => onCancel(turn.id)}
                  className="inline-flex items-center gap-1 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-0.5 text-xs font-medium text-rose-700 dark:text-rose-300 hover:bg-rose-500/20 cursor-pointer"
                >
                  <XCircle className="h-3.5 w-3.5" />
                  Cancel
                </button>
              </div>
            )}
          </div>

          {/* Live Pipeline Progress Stepper while running */}
          {!turn.is_terminal && (
            <div className="px-4 py-2.5 bg-indigo-50/40 dark:bg-indigo-950/20 border-b border-slate-100 dark:border-slate-800/70">
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
                {PIPELINE_STEPS.map((s, idx) => {
                  const done = idx < stepIdx;
                  const active = idx === stepIdx;
                  return (
                    <div
                      key={s.key}
                      className={`flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-medium transition ${
                        active
                          ? "bg-indigo-600 text-white shadow-2xs"
                          : done
                          ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                          : "bg-slate-100 dark:bg-slate-800/60 text-slate-400"
                      }`}
                    >
                      {done ? (
                        <CheckCircle2 className="h-3 w-3 shrink-0" />
                      ) : active ? (
                        <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
                      ) : (
                        <span className="h-1.5 w-1.5 rounded-full bg-current shrink-0" />
                      )}
                      <span className="truncate">{s.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Main Answer Content */}
          <div className="p-4 space-y-3.5">
            {turn.answer_text ? (
              <StreamingAnswer
                turnId={turn.id}
                text={turn.answer_text}
                isNew={isNewTurn ?? false}
                onComplete={onStreamComplete}
              />
            ) : !turn.is_terminal ? (
              <div className="space-y-2 py-1">
                <div className="flex items-center gap-2.5 text-xs text-indigo-700 dark:text-indigo-300 font-medium">
                  <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
                  <span>Inferencing: {turn.stage_label}…</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
                  <span className="flex gap-1 items-center">
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-bounce" />
                  </span>
                  <span className="text-[11px]">Preparing grounded tokens…</span>
                </div>
              </div>
            ) : null}

            {/* Cancelled Notice */}
            {turn.stage === "cancelled" && (
              <div className="rounded-xl bg-slate-100 dark:bg-slate-800/70 px-3.5 py-2 text-xs text-slate-600 dark:text-slate-300">
                Request cancelled. Any draft already saved remains listed below.
              </div>
            )}

            {/* Error Alert + Retry */}
            {turn.error_code && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2.5 text-xs text-amber-800 dark:text-amber-200">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                  <span>{turn.error_message}</span>
                </div>
                {(turn.can_retry_question || turn.can_retry_transcription) && (
                  <button
                    type="button"
                    onClick={() => onRetryTurn(turn.id)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1 text-xs font-semibold text-white hover:bg-amber-500 cursor-pointer"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    {turn.can_retry_transcription
                      ? "Retry transcription"
                      : "Retry question"}
                  </button>
                )}
              </div>
            )}

            {/* Unavailable Service Caption */}
            {turn.response_status === "unavailable" && (
              <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 px-3.5 py-2 text-xs text-rose-700 dark:text-rose-300">
                {turn.llm_error ||
                  "The answer service is temporarily unavailable."}
              </div>
            )}

            {/* Staff-Review Ticket Draft Badge */}
            {turn.ticket_id && (
              <div className="rounded-xl border border-indigo-500/25 bg-indigo-500/5 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-indigo-700 dark:text-indigo-300">
                    <Ticket className="h-4 w-4" />
                    <span>Local staff-review draft #{turn.ticket_id}</span>
                    <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-[10px] font-medium">
                      Saved locally · No email sent
                    </span>
                  </div>
                  {ticket && (
                    <button
                      type="button"
                      onClick={() => setShowTicket(!showTicket)}
                      className="text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
                    >
                      {showTicket ? "Hide draft" : "Inspect draft"}
                    </button>
                  )}
                </div>
                {showTicket && ticket && (
                  <div className="mt-2.5 pt-2.5 border-t border-indigo-500/20 text-xs space-y-1 text-slate-600 dark:text-slate-300">
                    <div>
                      <span className="font-medium">Office Target:</span>{" "}
                      {ticket.recipient_email} ({ticket.detected_category})
                    </div>
                    <div>
                      <span className="font-medium">Subject:</span>{" "}
                      {ticket.email_subject}
                    </div>
                    <pre className="mt-1 rounded-lg bg-white/80 dark:bg-slate-950/60 p-2 text-[11px] whitespace-pre-wrap font-mono">
                      {ticket.email_body}
                    </pre>
                  </div>
                )}
              </div>
            )}

            {/* Neural Speech Audio Player OR Retry Audio Controls */}
            {turn.audio?.available && audioStreamUrl ? (
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/50 p-3 space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600/10 px-2.5 py-1 text-xs font-semibold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">
                      <Volume2 className="h-3.5 w-3.5" />
                      {turn.audio.provider}
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">
                      {turn.audio.extension.toUpperCase()} ·{" "}
                      {(turn.audio.size_bytes / 1024).toFixed(1)} KB
                    </span>
                    {autoplayBlocked && (
                      <span className="text-[11px] text-amber-600 dark:text-amber-400">
                        Press Play below (browser blocked un-gestured autoplay)
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onRetryAudio(turn.id)}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 cursor-pointer"
                      title="Re-synthesize with current voice & speed settings without re-running LLM"
                    >
                      <RefreshCw className="h-3 w-3" />
                      Re-synthesize
                    </button>
                    {audioDownloadUrl && (
                      <a
                        href={audioDownloadUrl}
                        download={`reply-${turn.id.slice(0, 8)}.${turn.audio.extension}`}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100"
                      >
                        <Download className="h-3 w-3" />
                        Download reply
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() => setShowSpokenText(!showSpokenText)}
                      className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 cursor-pointer"
                    >
                      <span>Spoken text</span>
                      {showSpokenText ? (
                        <ChevronUp className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                <audio
                  ref={audioRef}
                  src={audioStreamUrl}
                  controls
                  onPlay={() => setAutoplayBlocked(false)}
                  className="w-full h-9"
                />

                {showSpokenText && (
                  <div className="rounded-lg bg-white dark:bg-slate-900 border border-slate-200/70 dark:border-slate-800 p-2.5 text-xs space-y-1">
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span>
                        Deterministic Verbalization (domain-pronunciation-2 · Negation Guard Active)
                      </span>
                      <span className="font-mono">{turn.audio.provider}</span>
                    </div>
                    <p className="text-slate-800 dark:text-slate-200 leading-relaxed">
                      {turn.audio.spoken_text}
                    </p>
                  </div>
                )}
              </div>
            ) : turn.answer_text && turn.is_terminal ? (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/40 px-3.5 py-2.5">
                <div className="text-xs text-slate-600 dark:text-slate-400">
                  {turn.audio_error ? (
                    <span className="text-amber-700 dark:text-amber-300">
                      {turn.audio_error}
                    </span>
                  ) : (
                    <span>
                      Reviewed text is ready. Generate spoken audio when needed.
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => onRetryAudio(turn.id)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 cursor-pointer shrink-0"
                >
                  <Volume2 className="h-3.5 w-3.5" />
                  {turn.audio_error ? "Retry audio" : "Speak this reply"}
                </button>
              </div>
            ) : null}

            {/* Verified Sources Expander */}
            {turn.sources && turn.sources.length > 0 && (
              <div className="rounded-xl border border-slate-200/90 dark:border-slate-800 overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowSources(!showSources)}
                  className="flex w-full items-center justify-between px-3.5 py-2.5 bg-slate-50/70 dark:bg-slate-950/50 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100/80 dark:hover:bg-slate-900 cursor-pointer"
                >
                  <span className="flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
                    View sources ({turn.sources.length} verified citation
                    {turn.sources.length === 1 ? "" : "s"})
                  </span>
                  {showSources ? (
                    <ChevronUp className="h-4 w-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  )}
                </button>

                {showSources && (
                  <div className="divide-y divide-slate-200/70 dark:divide-slate-800 bg-white dark:bg-slate-900">
                    {turn.sources.map((src, idx) => {
                      const localDocUrl = src.source_file
                        ? `/api/py/kb/document?path=${encodeURIComponent(
                            src.source_file
                          )}${
                            src.page_number ? `#page=${src.page_number}` : ""
                          }`
                        : null;
                      return (
                        <div key={idx} className="p-3.5 space-y-2 text-xs">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                              <span>{src.source_name}</span>
                              <span className="rounded-md bg-indigo-500/10 px-2 py-0.5 text-[11px] font-mono text-indigo-700 dark:text-indigo-300">
                                page {src.page_number ?? "?"}
                              </span>
                            </div>

                            <div className="flex items-center gap-2">
                              {localDocUrl && (
                                <a
                                  href={localDocUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 rounded-md border border-slate-200 dark:border-slate-700 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                                >
                                  <FileText className="h-3 w-3" />
                                  Open PDF
                                </a>
                              )}
                              {src.source_url &&
                                (src.source_url.startsWith("https://") ||
                                  src.source_url.startsWith("http://")) && (
                                  <a
                                    href={src.source_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 rounded-md bg-indigo-600/10 px-2 py-0.5 text-[11px] font-medium text-indigo-700 dark:text-indigo-300 hover:bg-indigo-600/20"
                                  >
                                    <ExternalLink className="h-3 w-3" />
                                    Official source
                                  </a>
                                )}
                            </div>
                          </div>

                          {/* Metadata notes */}
                          <div className="flex flex-wrap gap-1.5">
                            {(
                              [
                                "period",
                                "audience",
                                "conflict_note",
                                "scope_note",
                              ] as const
                            ).map((key) =>
                              src[key] ? (
                                <span
                                  key={key}
                                  className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[11px] text-slate-600 dark:text-slate-400"
                                >
                                  {src[key]}
                                </span>
                              ) : null
                            )}
                          </div>

                          {src.quote && (
                            <pre className="rounded-lg bg-slate-50 dark:bg-slate-950/70 border border-slate-200/60 dark:border-slate-800/80 p-2.5 text-[11px] text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">
                              {src.quote}
                            </pre>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer Telemetry & Timing Breakdown */}
          {turn.answer_text && (
            <div className="px-4 py-2.5 bg-slate-50/70 dark:bg-slate-950/50 border-t border-slate-100 dark:border-slate-800/80 text-[11px] text-slate-500 dark:text-slate-400 space-y-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="inline-flex items-center gap-1 font-medium text-slate-700 dark:text-slate-300">
                    <Cpu className="h-3 w-3 text-indigo-500" />
                    {turn.llm_provider || defaultProvider}
                    {metrics.model ? ` · ${metrics.model}` : ""}
                  </span>
                  {timingParts.length > 0 && (
                    <span>· {timingParts.join(" · ")}</span>
                  )}
                </div>

                {stageMsEntries.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowTimings(!showTimings)}
                    className="inline-flex items-center gap-1 text-indigo-600 dark:text-indigo-400 hover:underline font-medium cursor-pointer"
                  >
                    <Clock className="h-3 w-3" />
                    Timing breakdown
                    {showTimings ? (
                      <ChevronUp className="h-3 w-3" />
                    ) : (
                      <ChevronDown className="h-3 w-3" />
                    )}
                  </button>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="inline-flex items-center gap-1">
                  <Database className="h-3 w-3 text-emerald-500" />
                  Model calls: {metrics.model_calls ?? 0}
                </span>
                <span>
                  · Retrieval cache:{" "}
                  <strong className="font-mono text-slate-700 dark:text-slate-300">
                    {metrics.retrieval_cache || "bypass"}
                  </strong>
                </span>
                <span>
                  · Draft cache:{" "}
                  <strong className="font-mono text-slate-700 dark:text-slate-300">
                    {metrics.draft_cache || "bypass"}
                  </strong>
                </span>
                {typeof metrics.history_pairs === "number" && (
                  <span>· Context pairs: {metrics.history_pairs}</span>
                )}
              </div>

              {showTimings && stageMsEntries.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-200/70 dark:border-slate-800 space-y-1.5">
                  {stageMsEntries.map(([stageName, ms]) => (
                    <div
                      key={stageName}
                      className="grid grid-cols-12 items-center gap-2 font-mono text-[11px]"
                    >
                      <span className="col-span-4 sm:col-span-3 truncate text-slate-600 dark:text-slate-300">
                        {stageName}
                      </span>
                      <div className="col-span-6 sm:col-span-7 h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-indigo-500"
                          style={{
                            width: `${Math.max(
                              3,
                              Math.round((ms / maxStageMs) * 100)
                            )}%`,
                          }}
                        />
                      </div>
                      <span className="col-span-2 text-right text-slate-700 dark:text-slate-300">
                        {ms} ms
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
