"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Mic,
  Send,
  Sliders,
  PlusCircle,
  Trash2,
  ShieldCheck,
  Sparkles,
  Award,
  BookOpen,
  Activity,
  MessageSquare,
  UserCheck,
  AlertCircle,
  ChevronRight,
  ChevronDown,
  Volume2,
  Cpu,
  Globe,
  Lock,
  Loader2,
  CheckCircle2,
  Ticket,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import {
  AdmissionCategoryType,
  InputLanguageType,
  ProviderType,
  RuntimeHealth,
  StaffTicket,
  TurnSnapshot,
  VoiceType,
} from "@/lib/types";
import VoiceRecorderCard from "@/components/VoiceRecorderCard";
import TurnCard from "@/components/TurnCard";
import CutoffsExplorer from "@/components/CutoffsExplorer";
import KnowledgeExplorer from "@/components/KnowledgeExplorer";
import SystemStatusView from "@/components/SystemStatusView";

type ActiveTab = "helpdesk" | "cutoffs" | "knowledge" | "status";

const EMAIL_REGEX =
  /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$/;

function isValidEmail(val: string): boolean {
  const trimmed = val.trim();
  if (!trimmed) return true;
  return trimmed.length <= 254 && EMAIL_REGEX.test(trimmed);
}

const SUGGESTED_QUESTIONS: Array<{
  tag: string;
  lang: string;
  text: string;
}> = [
  {
    tag: "JoSAA Cutoff",
    lang: "English",
    text: "What are the opening and closing ranks for 2026 JoSAA round 5 CSE OPEN All India Gender-Neutral?",
  },
  {
    tag: "Hinglish · Admissions",
    lang: "Hinglish",
    text: "B.Tech admission kaise hota hai aur reporting ke liye kaunse documents chahiye?",
  },
  {
    tag: "Hindi · PM-Vidyalaxmi",
    lang: "Hindi",
    text: "PM Vidyalaxmi दिशानिर्देशों में ऋण चुकाने की अवधि क्या है?",
  },
  {
    tag: "Fees & Refund",
    lang: "English",
    text: "What is the B.Tech first semester fee structure and caution money refund rule?",
  },
  {
    tag: "Hostel & Campus",
    lang: "English",
    text: "What hostel and mess facilities are available for first-year B.Tech students?",
  },
  {
    tag: "Hindi · Scholarship",
    lang: "Hindi",
    text: "छत्तीसगढ़ पोस्ट-मैट्रिक छात्रवृत्ति के लिए आय सीमा और पात्रता क्या है?",
  },
];

export default function VoiceHelpdeskApp() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("helpdesk");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Session & Turns State
  const [sessionId, setSessionId] = useState<string>("");
  const [turns, setTurns] = useState<TurnSnapshot[]>([]);
  const [tickets, setTickets] = useState<StaffTicket[]>([]);
  const [playedIds, setPlayedIds] = useState<Set<string>>(new Set());
  const [streamedIds, setStreamedIds] = useState<Set<string>>(new Set());
  const [deletePending, setDeletePending] = useState(false);
  const initialTurnsSeededRef = useRef(false);

  // Configuration Rail State (mirrors Streamlit sidebar defaults)
  const [provider, setProvider] = useState<ProviderType>(
    process.env.NEXT_PUBLIC_DEFAULT_PROVIDER === "groq" ? "groq" : "ollama"
  );
  const [language, setLanguage] = useState<InputLanguageType>("Hindi");
  const [voice, setVoice] = useState<VoiceType>("Female");
  const [speed, setSpeed] = useState<number>(1.0);
  const [spoken, setSpoken] = useState<boolean>(true);
  const [onlineSpeech, setOnlineSpeech] = useState<boolean>(false);
  const [autoplay, setAutoplay] = useState<boolean>(true);

  // Optional Student Profile Context
  const [showProfile, setShowProfile] = useState(false);
  const [studentId, setStudentId] = useState("");
  const [studentEmail, setStudentEmail] = useState("");
  const [studentCategory, setStudentCategory] =
    useState<AdmissionCategoryType>("general");

  // Composer & Notifications
  const [questionInput, setQuestionInput] = useState("");
  const [bannerError, setBannerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Runtime Health State
  const [health, setHealth] = useState<RuntimeHealth | null>(null);
  const [refreshingHealth, setRefreshingHealth] = useState(false);
  const [showSidebarRuntime, setShowSidebarRuntime] = useState(false);

  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const profileValid = isValidEmail(studentEmail);

  const fetchHealth = useCallback(async () => {
    setRefreshingHealth(true);
    try {
      const res = await fetch("/api/py/health", { cache: "no-store" });
      if (res.ok) {
        const data: RuntimeHealth = await res.json();
        setHealth(data);
      }
    } catch {
      // ignore transient startup
    } finally {
      setRefreshingHealth(false);
    }
  }, []);

  const startNewSession = useCallback(async (prevId?: string) => {
    setBannerError(null);
    setDeletePending(false);
    try {
      const res = await fetch("/api/py/session/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ previous_session_id: prevId || null }),
      });
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.session_id);
        setTurns([]);
        setTickets([]);
        setPlayedIds(new Set());
        setStreamedIds(new Set());
        initialTurnsSeededRef.current = false;
        window.sessionStorage.setItem("demo2_session_id", data.session_id);
      }
    } catch {
      const fallbackId = crypto.randomUUID();
      setSessionId(fallbackId);
      setTurns([]);
      setTickets([]);
      setPlayedIds(new Set());
      setStreamedIds(new Set());
      initialTurnsSeededRef.current = false;
    }
  }, []);

  const pollSession = useCallback(async (sid: string) => {
    if (!sid) return;
    try {
      const res = await fetch(`/api/py/session/${sid}`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        const incomingTurns: TurnSnapshot[] = data.turns || [];
        if (!initialTurnsSeededRef.current && incomingTurns.length > 0) {
          initialTurnsSeededRef.current = true;
          setStreamedIds(
            new Set(incomingTurns.filter((t) => t.is_terminal && t.answer_text).map((t) => t.id))
          );
        }
        setTurns(incomingTurns);
        setTickets(data.tickets || []);
      }
    } catch {
      // ignore transient network errors
    }
  }, []);

  // Initialize session & health on mount
  useEffect(() => {
    fetchHealth();
    const existing = window.sessionStorage.getItem("demo2_session_id");
    if (existing) {
      setSessionId(existing);
      pollSession(existing);
    } else {
      startNewSession();
    }
  }, [fetchHealth, pollSession, startNewSession]);

  // Progressive 0.5s polling while any turn is non-terminal or deletePending is active
  const hasActiveTurn = turns.some((t) => !t.is_terminal);

  useEffect(() => {
    if (!sessionId) return;
    if (!hasActiveTurn && !deletePending) return;

    const timer = window.setInterval(async () => {
      if (deletePending) {
        try {
          const res = await fetch(`/api/py/session/${sessionId}`, {
            method: "DELETE",
          });
          if (res.ok) {
            const d = await res.json();
            if (d.deleted) {
              await startNewSession();
              return;
            }
          }
        } catch {
          // keep polling until drained
        }
      } else {
        await pollSession(sessionId);
      }
    }, 500);

    return () => clearInterval(timer);
  }, [sessionId, hasActiveTurn, deletePending, pollSession, startNewSession]);

  const handleMarkPlayed = useCallback((turnId: string) => {
    setPlayedIds((prev) => {
      const next = new Set(prev);
      next.add(turnId);
      return next;
    });
  }, []);

  const handleStreamComplete = useCallback((turnId: string) => {
    setStreamedIds((prev) => {
      if (prev.has(turnId)) return prev;
      const next = new Set(prev);
      next.add(turnId);
      return next;
    });
  }, []);

  const submitTextQuestion = async (textOverride?: string) => {
    const q = (textOverride ?? questionInput).trim();
    if (!q || !sessionId || !profileValid || deletePending || submitting) return;

    setBannerError(null);
    setSubmitting(true);
    if (!textOverride) setQuestionInput("");
    if (activeTab !== "helpdesk") setActiveTab("helpdesk");

    try {
      const res = await fetch("/api/py/turns/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          question: q,
          profile: {
            student_id: studentId.trim(),
            student_email: studentEmail.trim(),
            student_category: studentCategory,
          },
          provider,
          voice,
          speed,
          spoken,
          online_speech: onlineSpeech,
          input_language: language,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setBannerError(
          data?.detail?.message ||
            "The request could not be submitted. Please retry."
        );
      } else {
        await pollSession(sessionId);
        setTimeout(() => {
          chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }, 100);
      }
    } catch {
      setBannerError("Network error while submitting question. Please retry.");
    } finally {
      setSubmitting(false);
    }
  };

  const submitAudioTurn = async (wavBlob: Blob, filename: string) => {
    if (!sessionId || !profileValid || deletePending) return;
    setBannerError(null);
    if (activeTab !== "helpdesk") setActiveTab("helpdesk");

    const formData = new FormData();
    formData.append("session_id", sessionId);
    formData.append("provider", provider);
    formData.append("voice", voice);
    formData.append("speed", String(speed));
    formData.append("spoken", String(spoken));
    formData.append("online_speech", String(onlineSpeech));
    formData.append("input_language", language);
    formData.append("student_id", studentId.trim());
    formData.append("student_email", studentEmail.trim());
    formData.append("student_category", studentCategory);
    formData.append("file", wavBlob, filename);

    const res = await fetch("/api/py/turns/audio", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      setBannerError(
        data?.detail?.message ||
          "The recording could not be submitted. Please retry."
      );
      return;
    }
    await pollSession(sessionId);
    setTimeout(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  };

  const handleCancelTurn = async (turnId: string) => {
    if (!sessionId) return;
    await fetch(`/api/py/session/${sessionId}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ turn_id: turnId }),
    });
    await pollSession(sessionId);
  };

  const handleRetryTurn = async (turnId: string) => {
    if (!sessionId) return;
    setBannerError(null);
    setStreamedIds((prev) => {
      const next = new Set(prev);
      next.delete(turnId);
      return next;
    });
    const res = await fetch(
      `/api/py/turns/${sessionId}/${encodeURIComponent(turnId)}/retry`,
      { method: "POST" }
    );
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      setBannerError(d?.detail?.message || "Could not retry request.");
    }
    await pollSession(sessionId);
  };

  const handleRetryAudio = async (turnId: string) => {
    if (!sessionId) return;
    setBannerError(null);
    const res = await fetch(
      `/api/py/turns/${sessionId}/${encodeURIComponent(turnId)}/retry-audio`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          voice,
          speed,
          online_speech: onlineSpeech,
        }),
      }
    );
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      setBannerError(d?.detail?.message || "Could not synthesize audio.");
    } else {
      // Allow autoplay on explicitly requested speech
      setPlayedIds((prev) => {
        const next = new Set(prev);
        next.delete(turnId);
        return next;
      });
    }
    await pollSession(sessionId);
  };

  const handleDeleteConversation = async () => {
    if (!sessionId) return;
    setDeletePending(true);
    try {
      const res = await fetch(`/api/py/session/${sessionId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        const d = await res.json();
        if (d.deleted) {
          await startNewSession();
        }
      }
    } catch {
      // polling loop will finish draining & deleting
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      {/* Top Product Header */}
      <header className="sticky top-0 z-30 border-b border-slate-200/80 dark:border-slate-800/80 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          {/* Brand & Sidebar Toggle */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
              title={sidebarOpen ? "Collapse settings sidebar" : "Expand settings sidebar"}
            >
              {sidebarOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </button>

            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-700 text-white font-bold shadow-sm">
                <Mic className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm sm:text-base tracking-tight text-slate-900 dark:text-white">
                    IIIT-NR Voice Helpdesk
                  </span>
                  <span className="hidden sm:inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 dark:text-indigo-300 border border-indigo-500/20">
                    संवाद AI · Demo 2
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:block">
                  Dr. SPM International Institute of Information Technology, Naya Raipur
                </p>
              </div>
            </div>
          </div>

          {/* Primary Navigation Tabs */}
          <nav className="hidden lg:flex items-center gap-1 rounded-xl bg-slate-100 dark:bg-slate-800/80 p-1">
            {[
              {
                id: "helpdesk" as const,
                label: "Voice & Chat Helpdesk",
                icon: MessageSquare,
              },
              {
                id: "cutoffs" as const,
                label: "JoSAA & CSAB Cutoffs (611)",
                icon: Award,
              },
              {
                id: "knowledge" as const,
                label: "Knowledge & Verbalizer",
                icon: BookOpen,
              },
              {
                id: "status" as const,
                label: "Runtime & Architecture",
                icon: Activity,
              },
            ].map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition cursor-pointer ${
                    active
                      ? "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              );
            })}
          </nav>

          {/* Right Status & Session Actions */}
          <div className="flex items-center gap-2">
            {health && (
              <button
                type="button"
                onClick={() => setActiveTab("status")}
                className={`hidden md:inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium border transition cursor-pointer ${
                  health.release_ok
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                    : "border-amber-500/30 bg-amber-500/10 text-amber-700"
                }`}
                title="Inspect active knowledge release and runtime health"
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    health.release_ok ? "bg-emerald-500" : "bg-amber-500"
                  }`}
                />
                <span>
                  KB {health.release_ok ? "Verified" : "Degraded"} ·{" "}
                  {provider === "ollama" ? "Local Qwen3.5" : "Groq Cloud"}
                </span>
              </button>
            )}

            <button
              type="button"
              onClick={() => startNewSession(sessionId)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
              title="Start an independent conversation memory"
            >
              <PlusCircle className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
              <span className="hidden sm:inline">New conversation</span>
            </button>
          </div>
        </div>

        {/* Mobile Navigation Strip */}
        <div className="flex lg:hidden items-center gap-1 overflow-x-auto px-4 py-2 border-t border-slate-200/60 dark:border-slate-800/60 bg-slate-50/70 dark:bg-slate-950/60">
          {[
            { id: "helpdesk" as const, label: "Helpdesk", icon: MessageSquare },
            { id: "cutoffs" as const, label: "Cutoffs (611)", icon: Award },
            { id: "knowledge" as const, label: "Knowledge Base", icon: BookOpen },
            { id: "status" as const, label: "Runtime Status", icon: Activity },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold shrink-0 ${
                  active
                    ? "bg-indigo-600 text-white"
                    : "text-slate-600 dark:text-slate-400"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content Layout with Sidebar Rail */}
      <div className="flex-1 max-w-[1600px] w-full mx-auto flex">
        {/* Left Control Rail (Matches 100% of Streamlit sidebar controls) */}
        {sidebarOpen && (
          <aside className="w-80 shrink-0 border-r border-slate-200/80 dark:border-slate-800/80 bg-white dark:bg-slate-900/70 p-4 space-y-5 overflow-y-auto max-h-[calc(100vh-4rem)] sticky top-16 hidden md:block">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-indigo-600" />
                Your Conversation
              </h2>
              <span className="font-mono text-[10px] text-slate-400">
                ID: {sessionId ? sessionId.slice(0, 8) : "…"}
              </span>
            </div>

            {/* Answer Model Selector */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Answer model
              </label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value as ProviderType)}
                className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-800 dark:text-slate-200"
              >
                <option value="ollama">Local · Ollama (qwen3.5:9b)</option>
                <option value="groq">Groq · Cloud</option>
              </select>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                Groq sends your question, conversation context and source excerpts to the cloud when selected.
              </p>
            </div>

            {/* Recording Language */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Recording language
              </label>
              <select
                value={language}
                onChange={(e) =>
                  setLanguage(e.target.value as InputLanguageType)
                }
                className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-800 dark:text-slate-200"
              >
                <option value="Hindi">Hindi</option>
                <option value="English">English</option>
                <option value="Hinglish">Hinglish</option>
                <option value="Chhattisgarhi (experimental)">
                  Chhattisgarhi (experimental)
                </option>
              </select>
            </div>

            {/* Voice & Speed */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Voice
                </label>
                <select
                  value={voice}
                  onChange={(e) => setVoice(e.target.value as VoiceType)}
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-800 dark:text-slate-200"
                >
                  <option value="Female">Female</option>
                  <option value="Male">Male</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Speed
                  </label>
                  <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                    {speed.toFixed(1)}x
                  </span>
                </div>
                <input
                  type="range"
                  min={0.7}
                  max={1.4}
                  step={0.1}
                  value={speed}
                  onChange={(e) => setSpeed( parseFloat(e.target.value) )}
                  className="w-full accent-indigo-600 mt-2 cursor-pointer"
                />
              </div>
            </div>

            {/* Speech Toggles */}
            <div className="space-y-2.5 pt-2 border-t border-slate-100 dark:border-slate-800">
              <label className="flex items-center justify-between gap-2 cursor-pointer">
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Generate spoken replies
                </span>
                <input
                  type="checkbox"
                  checked={spoken}
                  onChange={(e) => setSpoken(e.target.checked)}
                  className="h-4 w-4 rounded accent-indigo-600"
                />
              </label>

              <label className="flex items-center justify-between gap-2 cursor-pointer">
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Allow online English/Hinglish speech
                </span>
                <input
                  type="checkbox"
                  checked={onlineSpeech}
                  onChange={(e) => setOnlineSpeech(e.target.checked)}
                  className="h-4 w-4 rounded accent-indigo-600"
                />
              </label>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                Online speech sends answer text to the voice service. Hindi speech uses the local VITS voice.
              </p>

              <label className="flex items-center justify-between gap-2 cursor-pointer">
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Play new replies automatically
                </span>
                <input
                  type="checkbox"
                  checked={autoplay}
                  onChange={(e) => setAutoplay(e.target.checked)}
                  className="h-4 w-4 rounded accent-indigo-600"
                />
              </label>
            </div>

            {/* Student Details Expander */}
            <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/40 overflow-hidden">
              <button
                type="button"
                onClick={() => setShowProfile(!showProfile)}
                className="w-full flex items-center justify-between px-3.5 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100/70 dark:hover:bg-slate-900 cursor-pointer"
              >
                <span className="flex items-center gap-1.5">
                  <UserCheck className="h-3.5 w-3.5 text-indigo-600" />
                  Student details (optional)
                </span>
                {showProfile ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
              </button>

              {showProfile && (
                <div className="p-3.5 pt-1 space-y-2.5 border-t border-slate-200/60 dark:border-slate-800">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1">
                      Student reference
                    </label>
                    <input
                      type="text"
                      maxLength={100}
                      value={studentId}
                      onChange={(e) => setStudentId(e.target.value)}
                      placeholder="e.g. JEE App No. / Roll No."
                      className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1">
                      Follow-up email
                    </label>
                    <input
                      type="email"
                      maxLength={254}
                      value={studentEmail}
                      onChange={(e) => setStudentEmail(e.target.value)}
                      placeholder="student@example.com"
                      className={`w-full rounded-lg border px-2.5 py-1.5 text-xs bg-white dark:bg-slate-900 ${
                        profileValid
                          ? "border-slate-200 dark:border-slate-700"
                          : "border-rose-500"
                      }`}
                    />
                    {!profileValid && (
                      <p className="text-[11px] text-rose-600 mt-1">
                        Enter a valid follow-up email or leave it blank.
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1">
                      Admission category
                    </label>
                    <select
                      value={studentCategory}
                      onChange={(e) =>
                        setStudentCategory(
                          e.target.value as AdmissionCategoryType
                        )
                      }
                      className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs"
                    >
                      <option value="general">general</option>
                      <option value="CG">CG (Chhattisgarh Quota)</option>
                    </select>
                  </div>

                  <p className="text-[10px] text-slate-500 leading-relaxed">
                    These details provide context; they do not verify your identity.
                  </p>
                </div>
              )}
            </div>

            {/* Session Actions (New vs Delete Conversation) */}
            <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                Conversations and local drafts expire after 24 hours. New conversation starts fresh; Delete conversation erases this conversation.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => startNewSession(sessionId)}
                  className="flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 cursor-pointer"
                >
                  <PlusCircle className="h-3.5 w-3.5" />
                  New
                </button>
                <button
                  type="button"
                  disabled={deletePending}
                  onClick={handleDeleteConversation}
                  className="flex items-center justify-center gap-1.5 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs font-semibold text-rose-700 dark:text-rose-300 hover:bg-rose-500/20 disabled:opacity-50 cursor-pointer"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>
              <p className="text-[10px] text-slate-400">
                Staff-review requests save local drafts. Email delivery and reminders are disabled.
              </p>
            </div>

            {/* Sidebar Runtime Status Expander */}
            <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/40 overflow-hidden">
              <button
                type="button"
                onClick={() => setShowSidebarRuntime(!showSidebarRuntime)}
                className="w-full flex items-center justify-between px-3.5 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100/70 dark:hover:bg-slate-900 cursor-pointer"
              >
                <span className="flex items-center gap-1.5">
                  <Activity className="h-3.5 w-3.5 text-emerald-500" />
                  Runtime status
                </span>
                {showSidebarRuntime ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
              </button>

              {showSidebarRuntime && health && (
                <div className="p-3.5 pt-2 space-y-1.5 border-t border-slate-200/60 dark:border-slate-800 text-[11px] text-slate-600 dark:text-slate-300">
                  <div>
                    Knowledge release:{" "}
                    <strong className="font-mono">
                      {health.release || "Missing"}
                    </strong>
                  </div>
                  <div>
                    Knowledge stores:{" "}
                    <strong>{health.release_ok ? "Ready" : "Unavailable"}</strong>
                  </div>
                  <div>
                    Release integrity:{" "}
                    <strong>{health.release_integrity || "bound"}</strong>
                  </div>
                  <div className="text-[10px] text-slate-500">
                    Source owners unassigned: {health.sources_unassigned ?? "?"} ·
                    Reviews overdue: {health.sources_review_overdue ?? "?"} ·
                    Evidence blocks: {health.evidence_blocks ?? "?"}
                  </div>
                  <div>
                    Router:{" "}
                    <strong className="font-mono">
                      {health.jev_mode} · {health.jev_artifact} ·{" "}
                      {health.jev_activation}
                    </strong>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveTab("status")}
                    className="mt-1 inline-flex items-center gap-1 text-indigo-600 dark:text-indigo-400 font-semibold hover:underline cursor-pointer"
                  >
                    Open full diagnostics →
                  </button>
                </div>
              )}
            </div>
          </aside>
        )}

        {/* Main Workspace Area */}
        <main className="flex-1 min-w-0 p-4 sm:p-6 max-w-5xl mx-auto w-full">
          {activeTab === "helpdesk" && (
            <div className="space-y-5 pb-24">
              {/* Institutional Welcome Header */}
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
                    Ask your institute.
                  </h1>
                  <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1">
                    Speak or type in Hindi, English, or Hinglish. Read the reviewed answer and its verified sources while neural speech is prepared.
                  </p>
                  <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
                    Chhattisgarhi recording is experimental; replies may use Hindi. This is a supervised local demonstration.
                  </p>
                </div>

                {/* Quick Badges */}
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 font-medium text-slate-700 dark:text-slate-300">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                    2-Pass Verbatim Grounding
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 font-medium text-slate-700 dark:text-slate-300">
                    <Volume2 className="h-3.5 w-3.5 text-indigo-500" />
                    Voice: {voice} ({speed.toFixed(1)}x)
                  </span>
                </div>
              </div>

              {/* Invalid Profile Email Warning */}
              {!profileValid && (
                <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs font-medium text-amber-800 dark:text-amber-200">
                  <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" />
                  <span>Enter a valid follow-up email or leave it blank.</span>
                </div>
              )}

              {/* Submission / Queue Warning Banner */}
              {bannerError && (
                <div className="flex items-center justify-between gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs font-medium text-rose-800 dark:text-rose-200">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                    <span>{bannerError}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setBannerError(null)}
                    className="text-xs font-semibold hover:underline cursor-pointer"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {/* Deleting Conversation State */}
              {deletePending && (
                <div className="flex items-center gap-2.5 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 text-xs font-medium text-indigo-800 dark:text-indigo-200">
                  <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
                  <span>Cancelling work and deleting this conversation…</span>
                </div>
              )}

              {/* Voice Studio Recorder & WAV/FLAC Uploader */}
              <VoiceRecorderCard
                disabled={!profileValid || deletePending}
                isBusy={hasActiveTurn}
                language={language}
                onLanguageChange={setLanguage}
                voice={voice}
                onVoiceChange={setVoice}
                onAudioSubmit={submitAudioTurn}
              />

              {/* Suggested Starter Questions when conversation is empty */}
              {turns.length === 0 && !deletePending && (
                <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-600 dark:text-slate-300 flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                      Try asking by voice or click a verified starter question:
                    </span>
                    <span className="text-[11px] text-slate-400">
                      Hindi · English · Hinglish
                    </span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {SUGGESTED_QUESTIONS.map((item, idx) => (
                      <button
                        key={idx}
                        type="button"
                        disabled={!profileValid || hasActiveTurn}
                        onClick={() => submitTextQuestion(item.text)}
                        className="group text-left rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/50 p-3 hover:border-indigo-500/50 hover:bg-indigo-50/30 dark:hover:bg-indigo-950/20 transition cursor-pointer disabled:opacity-50"
                      >
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="rounded-md bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-700 dark:text-indigo-300">
                            {item.tag}
                          </span>
                          <span className="text-[10px] text-slate-400 group-hover:text-indigo-500 transition">
                            Ask →
                          </span>
                        </div>
                        <p className="text-xs text-slate-700 dark:text-slate-200 line-clamp-2">
                          &ldquo;{item.text}&rdquo;
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Conversation Turn Feed */}
              <div className="space-y-5">
                {turns.map((turn) => {
                  const matchedTicket = tickets.find(
                    (t) =>
                      t.turn_id === turn.id ||
                      (turn.ticket_id && String(t.id) === String(turn.ticket_id))
                  );
                  return (
                    <TurnCard
                      key={turn.id}
                      sessionId={sessionId}
                      turn={turn}
                      ticket={matchedTicket}
                      defaultProvider={provider}
                      autoplay={autoplay}
                      alreadyPlayed={playedIds.has(turn.id)}
                      isNewTurn={!streamedIds.has(turn.id)}
                      onStreamComplete={handleStreamComplete}
                      onMarkPlayed={handleMarkPlayed}
                      onCancel={handleCancelTurn}
                      onRetryTurn={handleRetryTurn}
                      onRetryAudio={handleRetryAudio}
                    />
                  );
                })}
                <div ref={chatEndRef} />
              </div>

              {/* Sticky Bottom Text Question Composer */}
              <div className="fixed bottom-0 left-0 right-0 z-20 border-t border-slate-200/80 dark:border-slate-800/80 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md py-3 px-4">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    submitTextQuestion();
                  }}
                  className="max-w-4xl mx-auto flex items-center gap-2.5"
                >
                  <input
                    type="text"
                    maxLength={2000}
                    disabled={!profileValid || deletePending || hasActiveTurn}
                    value={questionInput}
                    onChange={(e) => setQuestionInput(e.target.value)}
                    placeholder={
                      hasActiveTurn
                        ? "Waiting for active turn to complete (or click Cancel above)…"
                        : "Or type your question in Hindi, English, or Hinglish (up to 2,000 chars)…"
                    }
                    className="flex-1 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-4 py-2.5 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
                  />
                  <button
                    type="submit"
                    disabled={
                      !questionInput.trim() ||
                      !profileValid ||
                      deletePending ||
                      hasActiveTurn ||
                      submitting
                    }
                    className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50 cursor-pointer"
                  >
                    <Send className="h-4 w-4" />
                    <span>Ask</span>
                  </button>
                </form>
              </div>
            </div>
          )}

          {activeTab === "cutoffs" && (
            <CutoffsExplorer
              onAskQuestion={(q) => {
                setActiveTab("helpdesk");
                submitTextQuestion(q);
              }}
            />
          )}

          {activeTab === "knowledge" && (
            <KnowledgeExplorer
              defaultVoice={voice}
              onAskQuestion={(q) => {
                setActiveTab("helpdesk");
                submitTextQuestion(q);
              }}
            />
          )}

          {activeTab === "status" && (
            <SystemStatusView
              health={health}
              onRefresh={fetchHealth}
              refreshing={refreshingHealth}
            />
          )}
        </main>
      </div>
    </div>
  );
}
