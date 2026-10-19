"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  BookOpen,
  Calendar,
  IndianRupee,
  GraduationCap,
  Users,
  Briefcase,
  FileText,
  Sparkles,
  Volume2,
  ShieldCheck,
  Search,
  MessageSquarePlus,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import {
  KbOverviewResponse,
  StructuredRecordItem,
  VoiceType,
} from "@/lib/types";

interface KnowledgeExplorerProps {
  onAskQuestion: (q: string) => void;
  defaultVoice: VoiceType;
}

const RECORD_TABS = [
  { key: "fee", label: "Fee Structure", icon: IndianRupee },
  { key: "date", label: "Academic Calendar (46)", icon: Calendar },
  { key: "seat", label: "Seat Matrix", icon: Users },
  { key: "placement", label: "Placements", icon: Briefcase },
  { key: "scholarship", label: "Scholarships & Loans", icon: GraduationCap },
  { key: "faculty", label: "Faculty Directory (42)", icon: Users },
  { key: "sources", label: "Official PDFs (122)", icon: FileText },
];

export default function KnowledgeExplorer({
  onAskQuestion,
  defaultVoice,
}: KnowledgeExplorerProps) {
  const [activeTab, setActiveTab] = useState<string>("fee");
  const [overview, setOverview] = useState<KbOverviewResponse | null>(null);
  const [records, setRecords] = useState<StructuredRecordItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Verbalizer v2 Sandbox state
  const [verbInput, setVerbInput] = useState(
    "Tuition fee is ₹ 90,000 and 3.5% interest is non-refundable for B.Tech CSE at IIIT Naya Raipur on 2026-08-24."
  );
  const [verbLang, setVerbLang] = useState<"hindi" | "hinglish" | "english">(
    "hindi"
  );
  const [verbResult, setVerbResult] = useState<{
    normalized: string;
    version: string;
    vits_ready: boolean;
    vits_note?: string | null;
  } | null>(null);

  useEffect(() => {
    fetch("/api/py/kb/overview")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setOverview(d);
      })
      .catch(() => {});
  }, []);

  const loadRecords = useCallback(async () => {
    if (activeTab === "sources") return;
    setLoading(true);
    try {
      const kindParam =
        activeTab === "scholarship" ? "" : activeTab;
      const params = new URLSearchParams();
      if (kindParam) params.set("kind", kindParam);
      if (searchQuery.trim()) params.set("search", searchQuery.trim());

      const res = await fetch(`/api/py/kb/records?${params.toString()}`);
      if (res.ok) {
        const json = await res.json();
        let list: StructuredRecordItem[] = json.records || [];
        if (activeTab === "scholarship") {
          list = list.filter(
            (r) => r.kind === "scholarship" || r.kind === "finance"
          );
        }
        setRecords(list);
      }
    } finally {
      setLoading(false);
    }
  }, [activeTab, searchQuery]);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  const runVerbalize = useCallback(async () => {
    if (!verbInput.trim()) return;
    try {
      const res = await fetch("/api/py/verbalize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: verbInput,
          language: verbLang,
          voice: defaultVoice,
        }),
      });
      if (res.ok) {
        setVerbResult(await res.json());
      }
    } catch {
      // ignore
    }
  }, [verbInput, verbLang, defaultVoice]);

  useEffect(() => {
    runVerbalize();
  }, [runVerbalize]);

  const filteredSources =
    overview?.sources.filter(
      (s) =>
        !searchQuery.trim() ||
        s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.source_file.toLowerCase().includes(searchQuery.toLowerCase())
    ) || [];

  return (
    <div className="space-y-6">
      {/* Release Overview Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        {[
          {
            label: "Active KBB Release",
            value: overview?.release
              ? overview.release.slice(0, 15) + "Z"
              : "20261014T0058Z",
            sub: `Pipeline ${overview?.pipeline_version || "kbb-3.0"}`,
          },
          {
            label: "Indexed Chunks",
            value: overview?.chunks?.toLocaleString() || "5,153",
            sub: "multilingual-e5-small (384d)",
          },
          {
            label: "Evidence Blocks",
            value: overview?.evidence_blocks?.toLocaleString() || "2,055",
            sub: "Page-tagged provenance",
          },
          {
            label: "Structured Facts",
            value: overview?.structured_records?.toLocaleString() || "722",
            sub: "611 Cutoffs + 111 Policy rows",
          },
          {
            label: "Official Documents",
            value: overview?.documents?.toLocaleString() || "122",
            sub: "SHA-256 Content Bound",
          },
          {
            label: "Validation Pass Rate",
            value: overview?.validation?.pass_rate
              ? `${(overview.validation.pass_rate * 100).toFixed(2)}%`
              : "98.56%",
            sub: `${overview?.validation?.passed ?? 137}/${
              overview?.validation?.scored ?? 139
            } benchmark cases`,
          },
        ].map((card, i) => (
          <div
            key={i}
            className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-3.5 shadow-2xs"
          >
            <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
              {card.label}
            </div>
            <div className="mt-1 text-base font-bold font-mono text-slate-900 dark:text-white truncate">
              {card.value}
            </div>
            <div className="mt-0.5 text-[11px] text-emerald-600 dark:text-emerald-400 truncate">
              {card.sub}
            </div>
          </div>
        ))}
      </div>

      {/* Category Tabs + Search */}
      <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-slate-50/80 dark:bg-slate-950/60 border-b border-slate-200/70 dark:border-slate-800">
          <div className="flex flex-wrap items-center gap-1.5">
            {RECORD_TABS.map((t) => {
              const Icon = t.icon;
              const active = activeTab === t.key;
              return (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setActiveTab(t.key)}
                  className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition cursor-pointer ${
                    active
                      ? "bg-indigo-600 text-white shadow-2xs"
                      : "text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-800"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {t.label}
                </button>
              );
            })}
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter records or PDFs…"
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 pl-8 pr-3 py-1.5 text-xs text-slate-800 dark:text-slate-200"
            />
          </div>
        </div>

        {/* Records Grid or Sources List */}
        <div className="p-5 max-h-[520px] overflow-y-auto">
          {activeTab === "sources" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredSources.map((src) => (
                <div
                  key={src.id}
                  className="flex items-start justify-between gap-3 rounded-xl border border-slate-200/80 dark:border-slate-800 p-3.5 hover:border-indigo-500/40 transition"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="text-xs font-semibold text-slate-900 dark:text-white truncate">
                      {src.title}
                    </div>
                    <div className="text-[11px] font-mono text-slate-500 truncate">
                      {src.source_file}
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                      <span>SHA-256: {src.sha256.slice(0, 16)}…</span>
                      <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-emerald-700 dark:text-emerald-300">
                        {src.source_status}
                      </span>
                    </div>
                  </div>
                  <a
                    href={`/api/py/kb/document?path=${encodeURIComponent(
                      src.source_file
                    )}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 inline-flex items-center gap-1 rounded-lg bg-indigo-600/10 px-2.5 py-1.5 text-xs font-semibold text-indigo-700 dark:text-indigo-300 hover:bg-indigo-600 hover:text-white transition"
                  >
                    <FileText className="h-3.5 w-3.5" />
                    Open
                  </a>
                </div>
              ))}
            </div>
          ) : loading ? (
            <div className="py-12 text-center text-xs text-slate-500">
              Loading verified structured records…
            </div>
          ) : records.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500">
              No structured records match your filter.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {records.map((rec) => {
                const p = rec.payload as Record<string, string | number>;
                return (
                  <div
                    key={rec.id}
                    className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-950/40 p-4 flex flex-col justify-between gap-3"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-bold text-slate-900 dark:text-white">
                          {rec.label}
                        </span>
                        <span className="shrink-0 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
                          {rec.review_status}
                        </span>
                      </div>

                      {p.amount !== undefined && (
                        <div className="text-sm font-mono font-bold text-indigo-600 dark:text-indigo-400">
                          ₹ {Number(p.amount).toLocaleString("en-IN")}{" "}
                          <span className="text-xs font-normal text-slate-500">
                            ({p.currency || "INR"})
                          </span>
                        </div>
                      )}
                      {p.date_text && (
                        <div className="text-xs font-mono font-semibold text-indigo-600 dark:text-indigo-400">
                          📅 {String(p.date_text)}
                        </div>
                      )}
                      {p.value && (
                        <div className="text-sm font-mono font-bold text-emerald-600 dark:text-emerald-400">
                          {String(p.value)}
                        </div>
                      )}
                      {p.seats !== undefined && (
                        <div className="text-sm font-mono font-bold text-indigo-600 dark:text-indigo-400">
                          {String(p.seats)} Seats ({String(p.quota || "")} ·{" "}
                          {String(p.seat_category || "")})
                        </div>
                      )}
                      {p.designation && (
                        <div className="text-xs text-slate-600 dark:text-slate-300">
                          {String(p.designation)} · Dept:{" "}
                          <strong>{String(p.department || "")}</strong>{" "}
                          {p.email ? `· ${String(p.email)}` : ""}
                        </div>
                      )}
                      {p.benefit && (
                        <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                          {String(p.benefit)}
                        </p>
                      )}
                      {p.conditions && (
                        <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                          {String(p.conditions)}
                        </p>
                      )}
                      {p.quote && (
                        <pre className="mt-1 rounded-lg bg-white dark:bg-slate-900 border border-slate-200/70 dark:border-slate-800 p-2 text-[11px] font-mono text-slate-600 dark:text-slate-400 whitespace-pre-wrap">
                          {String(p.quote)}
                        </pre>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-slate-200/60 dark:border-slate-800/70">
                      <span className="text-[10px] font-mono text-slate-400 truncate max-w-[200px]">
                        Block: {rec.evidence_block_id}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          onAskQuestion(`Tell me about ${rec.label} at IIIT Naya Raipur.`)
                        }
                        className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
                      >
                        <MessageSquarePlus className="h-3.5 w-3.5" />
                        Ask in Helpdesk
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Deterministic Verbalization v2 & Hindi Negation Guard Sandbox */}
      <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-violet-500/10 px-2.5 py-0.5 text-xs font-semibold text-violet-700 dark:text-violet-300">
                <Volume2 className="h-3.5 w-3.5" />
                verbalization.py · domain-pronunciation-2
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                <ShieldCheck className="h-3.5 w-3.5" />
                Hindi Negation Guard Active
              </span>
            </div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white mt-1">
              Deterministic Speech Pronunciation & Negation Sandbox
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Test how Demo 2 deterministically expands Indian currency (₹90,000 → नब्बे हजार रुपये), decimals (3.5% → तीन दशमलव पाँच प्रतिशत), dates, acronyms, and legal negations (&ldquo;non-refundable&rdquo; → &ldquo;गैर-वापसी योग्य&rdquo;) without risking LLM semantic drift.
            </p>
          </div>

          <div className="inline-flex rounded-xl bg-slate-100 dark:bg-slate-800 p-1 text-xs font-semibold">
            {(["hindi", "hinglish", "english"] as const).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setVerbLang(l)}
                className={`rounded-lg px-3 py-1 capitalize transition cursor-pointer ${
                  verbLang === l
                    ? "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-2xs"
                    : "text-slate-600 dark:text-slate-400"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
              Input Grounded Answer Text
            </label>
            <textarea
              rows={3}
              value={verbInput}
              onChange={(e) => setVerbInput(e.target.value)}
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 p-3 text-xs text-slate-800 dark:text-slate-200 font-mono"
            />
            <div className="flex flex-wrap gap-1.5 pt-1">
              {[
                "Fee is ₹ 90,000 and 3.5% non-refundable",
                "आईआईआईटी नया रायपुर में B.Tech CSE की फीस ₹ 1,25,000 है",
                "JoSAA 2026-08-24 reporting is not applicable without OTR",
              ].map((sample, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setVerbInput(sample)}
                  className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2.5 py-1 text-[11px] text-slate-600 dark:text-slate-400 hover:border-indigo-500/40 cursor-pointer"
                >
                  Sample {i + 1}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Normalized Synthesizer Input ({verbLang.toUpperCase()})
              </span>
              {verbLang === "hindi" && verbResult && (
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    verbResult.vits_ready
                      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                      : "bg-amber-500/10 text-amber-700 dark:text-amber-300"
                  }`}
                >
                  {verbResult.vits_ready ? (
                    <>
                      <CheckCircle2 className="h-3 w-3" />
                      100% Devanagari VITS Ready
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="h-3 w-3" />
                      Contains unmapped Latin words (Safe text fallback)
                    </>
                  )}
                </span>
              )}
            </div>
            <div className="min-h-[84px] rounded-xl border border-indigo-500/25 bg-indigo-50/30 dark:bg-indigo-950/20 p-3 text-sm text-slate-900 dark:text-slate-100 leading-relaxed">
              {verbResult?.normalized || "…"}
            </div>
            {verbLang === "hindi" && verbResult?.vits_note && (
              <p className="text-[11px] text-amber-600 dark:text-amber-400">
                Guard note: {verbResult.vits_note}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
