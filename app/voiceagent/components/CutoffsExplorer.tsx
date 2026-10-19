"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Filter,
  Search,
  MessageSquarePlus,
  Award,
  FileText,
  RefreshCw,
  ArrowUpDown,
  ShieldCheck,
} from "lucide-react";
import { CutoffRecord, CutoffsResponse } from "@/lib/types";

interface CutoffsExplorerProps {
  onAskQuestion: (q: string) => void;
}

export default function CutoffsExplorer({
  onAskQuestion,
}: CutoffsExplorerProps) {
  const [data, setData] = useState<CutoffsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState<string>("2026");
  const [authority, setAuthority] = useState<string>("");
  const [programme, setProgramme] = useState<string>("");
  const [quota, setQuota] = useState<string>("");
  const [category, setCategory] = useState<string>("");
  const [gender, setGender] = useState<string>("");
  const [round, setRound] = useState<string>("");
  const [selectedRow, setSelectedRow] = useState<CutoffRecord | null>(null);

  const fetchCutoffs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (year) params.set("year", year);
      if (authority) params.set("authority", authority);
      if (programme) params.set("programme", programme);
      if (quota) params.set("quota", quota);
      if (category) params.set("seat_category", category);
      if (gender) params.set("gender_pool", gender);
      if (round) params.set("round", round);
      params.set("limit", "250");

      const res = await fetch(`/api/py/kb/cutoffs?${params.toString()}`);
      if (res.ok) {
        const json: CutoffsResponse = await res.json();
        setData(json);
      }
    } finally {
      setLoading(false);
    }
  }, [year, authority, programme, quota, category, gender, round]);

  useEffect(() => {
    fetchCutoffs();
  }, [fetchCutoffs]);

  const facets = data?.facets;

  const resetFilters = () => {
    setYear("2026");
    setAuthority("");
    setProgramme("");
    setQuota("");
    setCategory("");
    setGender("");
    setRound("");
  };

  return (
    <div className="space-y-5">
      {/* Header Banner */}
      <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 dark:text-indigo-300">
                <Award className="h-3.5 w-3.5" />
                Relational Cutoff Sidecar (facts.sqlite)
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                <ShieldCheck className="h-3.5 w-3.5" />
                611 Verified Rows · 100% Numerical Precision
              </span>
            </div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              JoSAA & CSAB Opening and Closing Ranks Explorer
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-3xl">
              Explore official historical opening and closing ranks across 2022–2026 counselling rounds for CSE, DSAI, and ECE. Click any row to inspect verbatim evidence or ask the Voice Helpdesk directly.
            </p>
          </div>

          <button
            type="button"
            onClick={resetFilters}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Reset Filters
          </button>
        </div>

        {/* Multi-Dimensional Filter Grid */}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1">
              Year
            </label>
            <select
              value={year}
              onChange={(e) => setYear(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value="">All Years</option>
              {(facets?.year || [2026, 2025, 2024, 2023, 2022]).map((y) => (
                <option key={y} value={String(y)}>
                  {y}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1">
              Authority
            </label>
            <select
              value={authority}
              onChange={(e) => setAuthority(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value="">All Authorities</option>
              {(facets?.authority || ["JoSAA", "CSAB"]).map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1">
              Branch / Programme
            </label>
            <select
              value={programme}
              onChange={(e) => setProgramme(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value="">All Branches</option>
              {(facets?.programme || ["CSE", "DSAI", "ECE"]).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1">
              Quota
            </label>
            <select
              value={quota}
              onChange={(e) => setQuota(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value="">All Quotas</option>
              {(facets?.quota || ["AI"]).map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1">
              Seat Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value="">All Categories</option>
              {(
                facets?.seat_category || ["OPEN", "EWS", "OBC-NCL", "SC", "ST"]
              ).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1">
              Seat Pool
            </label>
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value="">All Pools</option>
              {(
                facets?.gender_pool || ["Gender-Neutral", "Female-only"]
              ).map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1">
              Round
            </label>
            <select
              value={round}
              onChange={(e) => setRound(e.target.value)}
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value="">All Rounds</option>
              {(facets?.round || ["1", "2", "3", "4", "5", "6"]).map((r) => (
                <option key={r} value={r}>
                  Round {r}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Selected Row Verbatim Evidence Drawer */}
      {selectedRow && (
        <div className="rounded-2xl border border-indigo-500/30 bg-indigo-50/50 dark:bg-indigo-950/30 p-4 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-indigo-900 dark:text-indigo-200">
              <FileText className="h-4 w-4 text-indigo-600" />
              <span>
                Verified Cutoff Record · {selectedRow.year}{" "}
                {selectedRow.authority} Round {selectedRow.round} ·{" "}
                {selectedRow.programme} ({selectedRow.seat_category} ·{" "}
                {selectedRow.gender_pool})
              </span>
            </div>
            <button
              type="button"
              onClick={() => setSelectedRow(null)}
              className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-white cursor-pointer"
            >
              Close
            </button>
          </div>
          {selectedRow.quote && (
            <pre className="rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 p-3 text-xs font-mono whitespace-pre-wrap text-slate-700 dark:text-slate-200">
              {selectedRow.quote}
            </pre>
          )}
        </div>
      )}

      {/* Results Table */}
      <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 bg-slate-50/80 dark:bg-slate-950/50 border-b border-slate-200/70 dark:border-slate-800">
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
            Showing {data?.records.length ?? 0} of {data?.total ?? 0} matching cutoff rows
          </span>
          <span className="text-[11px] text-slate-500">
            Historical cutoffs do not predict future seat allotment
          </span>
        </div>

        <div className="overflow-x-auto max-h-[540px]">
          <table className="w-full text-left border-collapse text-xs">
            <thead className="sticky top-0 bg-slate-100/95 dark:bg-slate-950/95 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="py-2.5 px-4 font-semibold">Year</th>
                <th className="py-2.5 px-4 font-semibold">Authority</th>
                <th className="py-2.5 px-4 font-semibold">Round</th>
                <th className="py-2.5 px-4 font-semibold">Branch</th>
                <th className="py-2.5 px-4 font-semibold">Quota</th>
                <th className="py-2.5 px-4 font-semibold">Category</th>
                <th className="py-2.5 px-4 font-semibold">Seat Pool</th>
                <th className="py-2.5 px-4 font-semibold text-right">
                  Opening Rank
                </th>
                <th className="py-2.5 px-4 font-semibold text-right">
                  Closing Rank
                </th>
                <th className="py-2.5 px-4 font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/60 dark:divide-slate-800/70">
              {loading ? (
                <tr>
                  <td
                    colSpan={10}
                    className="py-10 text-center text-slate-500 dark:text-slate-400"
                  >
                    Loading verified cutoff records from facts.sqlite…
                  </td>
                </tr>
              ) : data?.records.length === 0 ? (
                <tr>
                  <td
                    colSpan={10}
                    className="py-10 text-center text-slate-500 dark:text-slate-400"
                  >
                    No cutoff rows match the selected filters. Try broadening your filter selection.
                  </td>
                </tr>
              ) : (
                data?.records.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedRow(row)}
                    className="hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20 transition cursor-pointer"
                  >
                    <td className="py-2.5 px-4 font-mono font-semibold text-slate-900 dark:text-slate-100">
                      {row.year}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="rounded-md bg-slate-100 dark:bg-slate-800 px-2 py-0.5 font-medium text-slate-700 dark:text-slate-300">
                        {row.authority}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 font-mono">R{row.round}</td>
                    <td className="py-2.5 px-4">
                      <span className="rounded-md bg-indigo-500/10 px-2 py-0.5 font-semibold text-indigo-700 dark:text-indigo-300">
                        {row.programme}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 font-mono text-slate-600 dark:text-slate-400">
                      {row.quota}
                    </td>
                    <td className="py-2.5 px-4 font-medium text-slate-800 dark:text-slate-200">
                      {row.seat_category}
                    </td>
                    <td className="py-2.5 px-4 text-slate-600 dark:text-slate-400">
                      {row.gender_pool}
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono font-semibold text-emerald-700 dark:text-emerald-400">
                      {row.opening_rank}
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono font-semibold text-indigo-700 dark:text-indigo-300">
                      {row.closing_rank}
                    </td>
                    <td
                      className="py-2.5 px-4 text-right"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={() =>
                          onAskQuestion(
                            `What are the opening and closing ranks for ${row.year} ${row.authority} round ${row.round} ${row.programme} ${row.seat_category} ${row.quota} ${row.gender_pool}?`
                          )
                        }
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-600/10 px-2.5 py-1 text-[11px] font-semibold text-indigo-700 dark:text-indigo-300 hover:bg-indigo-600 hover:text-white transition cursor-pointer"
                      >
                        <MessageSquarePlus className="h-3 w-3" />
                        Ask Agent
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
