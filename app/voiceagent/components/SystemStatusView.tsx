"use client";

import React from "react";
import {
  Activity,
  Database,
  Cpu,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Server,
  HardDrive,
  RefreshCw,
  Layers,
  GitBranch,
  Volume2,
} from "lucide-react";
import { RuntimeHealth } from "@/lib/types";

interface SystemStatusViewProps {
  health: RuntimeHealth | null;
  onRefresh: () => void;
  refreshing: boolean;
}

const LANGGRAPH_NODES = [
  {
    id: "1. classify_intent",
    file: "assistant/nodes.py::classify_intent_node",
    desc: "Inspects 10-turn history, applies 0ms regex fast-paths (greetings/thanks/confirmations), or rewrites query into standalone English search query & category.",
  },
  {
    id: "2. retrieve",
    file: "assistant/nodes.py::retrieve_node",
    desc: "3-Way Hybrid Retrieval: Dense (multilingual-e5-small 384d) + Sparse (Rank-BM25) merged via Reciprocal Rank Fusion + Relational SQLite Cutoff Sidecar (611 exact rows).",
  },
  {
    id: "3. generate_answer",
    file: "assistant/nodes.py::generate_answer_node",
    desc: "Two-Pass Grounding Verification: Pass 1 drafts JSON answer with quotes; Pass 2 cross-examines every claim against verbatim source chunks or abstains safely.",
  },
  {
    id: "4. escalate",
    file: "assistant/nodes.py::escalate_node",
    desc: "Creates local staff-review draft in tickets.sqlite with student profile and category without falsely promising instant callback or sending email.",
  },
  {
    id: "5. handle_reminder",
    file: "assistant/nodes.py::handle_reminder_node",
    desc: "Multi-turn state machine validating future ISO dates and student email; explicitly disabled in Demo 2 supervised mode.",
  },
  {
    id: "6. finalize_turn",
    file: "assistant/nodes.py::finalize_turn_node",
    desc: "Prunes history to 10 turns, records resolved_query on AIMessage for follow-up pronoun resolution, and commits SQLite checkpoint.",
  },
];

export default function SystemStatusView({
  health,
  onRefresh,
  refreshing,
}: SystemStatusViewProps) {
  if (!health) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-8 text-center text-sm text-slate-500">
        Loading runtime telemetry from Demo 2 backend…
      </div>
    );
  }

  const cache = health.cache_telemetry;
  const formatBytes = (b?: number) => {
    if (typeof b !== "number") return "0 B";
    if (b < 1024) return `${b} B`;
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
    return `${(b / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                health.release_ok
                  ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  : "bg-rose-500/10 text-rose-700 dark:text-rose-300"
              }`}
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Knowledge Stores: {health.release_ok ? "Ready" : "Unavailable"}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs font-mono font-semibold text-indigo-700 dark:text-indigo-300">
              Integrity: {health.release_integrity || "bound"}
            </span>
          </div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">
            Runtime Status, Telemetry & 6-Node LangGraph Architecture
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Live inspection of the active knowledge release pointer, bounded admission queue, SQLite stores, and model stack (`python ops.py status`).
          </p>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
          />
          Refresh Telemetry
        </button>
      </div>

      {/* Top 4 Diagnostic Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Active Release */}
        <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-2.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
              Active Knowledge Release
            </span>
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="font-mono text-sm font-bold text-slate-900 dark:text-white truncate">
            {health.release || "Missing"}
          </div>
          <div className="grid grid-cols-2 gap-1.5 text-[11px] text-slate-600 dark:text-slate-300 pt-1">
            <div>Chunks: <strong>{health.chunks ?? 0}</strong></div>
            <div>Cutoffs: <strong>{health.cutoff_records ?? 0}</strong></div>
            <div>Evidence: <strong>{health.evidence_blocks ?? 0}</strong></div>
            <div>Records: <strong>{health.structured_records ?? 0}</strong></div>
          </div>
          <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 dark:border-slate-800">
            Unassigned owners: {health.sources_unassigned ?? 0} · Overdue reviews:{" "}
            {health.sources_review_overdue ?? 0}
          </div>
        </div>

        {/* 2. JobManager Queue & Concurrency */}
        <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-2.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
              Bounded JobManager Queue
            </span>
            <Activity className="h-4 w-4 text-indigo-500" />
          </div>
          <div className="font-mono text-sm font-bold text-slate-900 dark:text-white">
            Active: {health.queue?.active_jobs ?? 0} · Queued:{" "}
            {health.queue?.queued_jobs ?? 0} / {health.queue?.capacity ?? 3}
          </div>
          <div className="grid grid-cols-2 gap-1.5 text-[11px] text-slate-600 dark:text-slate-300 pt-1">
            <div>Queue Limit: <strong>{health.queue?.queue_timeout_seconds ?? 60}s</strong></div>
            <div>Turn Deadline: <strong>{health.queue?.turn_timeout_seconds ?? 120}s</strong></div>
            <div>Retention: <strong>{health.queue?.retention_hours ?? 24}h</strong></div>
            <div>Tracked Jobs: <strong>{health.queue?.total_tracked_jobs ?? 0}</strong></div>
          </div>
          <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 dark:border-slate-800">
            1 reasoning worker (`demo-reasoning`) + 1 speech worker (`demo-speech`)
          </div>
        </div>

        {/* 3. Router & Speech Voices */}
        <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-2.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
              Router & Local VITS Voices
            </span>
            <Volume2 className="h-4 w-4 text-violet-500" />
          </div>
          <div className="font-mono text-sm font-bold text-slate-900 dark:text-white truncate">
            Router: {health.jev_mode} · {health.jev_artifact}
          </div>
          <div className="flex items-center gap-2 pt-1">
            {Object.entries(health.voices || {}).map(([vName, ok]) => (
              <span
                key={vName}
                className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-semibold ${
                  ok
                    ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                    : "bg-rose-500/10 text-rose-700"
                }`}
              >
                <CheckCircle2 className="h-3 w-3" />
                VITS {vName}: {ok ? "Ready" : "Missing"}
              </span>
            ))}
          </div>
          <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 dark:border-slate-800">
            Activation: {health.jev_activation} · LRU Voice Cache: 2 CPU slots
          </div>
        </div>

        {/* 4. RAG Cache Telemetry */}
        <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-2.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
              Cryptographic RAG Cache
            </span>
            <Database className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="font-mono text-sm font-bold text-slate-900 dark:text-white">
            Hit Rate:{" "}
            {cache ? `${(cache.hit_rate * 100).toFixed(1)}%` : "0.0%"}
          </div>
          <div className="grid grid-cols-3 gap-1 text-[11px] text-slate-600 dark:text-slate-300 pt-1">
            <div>Hits: <strong>{cache?.hit ?? 0}</strong></div>
            <div>Misses: <strong>{cache?.miss ?? 0}</strong></div>
            <div>Puts: <strong>{cache?.put ?? 0}</strong></div>
            <div>Bypass: <strong>{cache?.bypass ?? 0}</strong></div>
            <div>Evicts: <strong>{cache?.evict ?? 0}</strong></div>
            <div>Errors: <strong>{cache?.error ?? 0}</strong></div>
          </div>
          <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 dark:border-slate-800">
            1-hour TTL · Max 2,000 entries (64 MiB cap)
          </div>
        </div>
      </div>

      {/* SQLite Stores & Environment Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* SQLite Databases Table */}
        <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2">
            <HardDrive className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              Durable SQLite Stores (`demo2/data`)
            </h3>
          </div>
          <div className="divide-y divide-slate-200/70 dark:divide-slate-800">
            {Object.entries(health.storage || {}).map(([dbName, info]) => (
              <div
                key={dbName}
                className="py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs"
              >
                <div>
                  <div className="font-mono font-semibold text-slate-900 dark:text-white">
                    {dbName}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {info.rows
                      ? Object.entries(info.rows)
                          .map(([tbl, cnt]) => `${tbl}: ${cnt}`)
                          .join(" · ")
                      : info.error || "No tables"}
                  </div>
                </div>
                <div className="flex items-center gap-2 font-mono text-[11px]">
                  <span className="text-slate-600 dark:text-slate-400">
                    {formatBytes(info.bytes)}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 font-semibold ${
                      info.integrity === "ok"
                        ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                        : "bg-amber-500/10 text-amber-700"
                    }`}
                  >
                    {info.integrity || "ok"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* System Environment & Package Versions */}
        <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              Environment & Protected Model Stack (`minor` Conda Env)
            </h3>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(health.environment || {}).map(([k, v]) => (
              <div
                key={k}
                className="rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200/60 dark:border-slate-800 px-3 py-1.5"
              >
                <div className="text-[10px] font-medium text-slate-400 uppercase">
                  {k.replace(/_/g, " ")}
                </div>
                <div className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                  {String(v)}
                </div>
              </div>
            ))}
          </div>

          <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
            <div className="text-[11px] font-semibold text-slate-500 mb-2">
              Verified Package Versions:
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(health.dependencies || {}).map(([pkg, ver]) => (
                <span
                  key={pkg}
                  className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2.5 py-1 font-mono text-[11px] text-slate-700 dark:text-slate-300"
                >
                  {pkg}: <strong>{ver}</strong>
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 6-Node LangGraph Architecture Reference */}
      <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs space-y-4">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            Compiled 6-Node LangGraph StateGraph (`assistant/graph.py`)
          </h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {LANGGRAPH_NODES.map((node) => (
            <div
              key={node.id}
              className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 p-3.5 space-y-1.5"
            >
              <div className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                {node.id}
              </div>
              <div className="font-mono text-[10px] text-slate-400 truncate">
                {node.file}
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {node.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
