"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { Sparkles, FastForward } from "lucide-react";

interface StreamingAnswerProps {
  turnId: string;
  text: string;
  isNew: boolean;
  onComplete?: (turnId: string) => void;
}

export default function StreamingAnswer({
  turnId,
  text,
  isNew,
  onComplete,
}: StreamingAnswerProps) {
  // Split into tokens preserving words, spaces, and line breaks
  const tokens = useMemo(() => text.match(/\S+|\s+/g) || [text], [text]);

  // If not new, start fully displayed
  const [displayedCount, setDisplayedCount] = useState<number>(() =>
    isNew ? 1 : tokens.length
  );

  const isStreaming = isNew && displayedCount < tokens.length;

  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const completedReportedRef = useRef(false);

  useEffect(() => {
    // If not new or trivially short, show full text immediately
    if (!isNew || tokens.length <= 1) {
      setDisplayedCount(tokens.length);
      return;
    }

    // Reset index for active streaming
    completedReportedRef.current = false;
    let currentIndex = 1;
    setDisplayedCount(1);

    const interval = window.setInterval(() => {
      let step = 1;
      if (currentIndex < tokens.length && /^\s+$/.test(tokens[currentIndex] || "")) {
        step = 2;
      }
      currentIndex += step;

      if (currentIndex >= tokens.length) {
        clearInterval(interval);
        setDisplayedCount(tokens.length);
        if (!completedReportedRef.current) {
          completedReportedRef.current = true;
          // Defer callback with setTimeout to avoid mutating parent state during render
          setTimeout(() => {
            onCompleteRef.current?.(turnId);
          }, 0);
        }
      } else {
        setDisplayedCount(currentIndex);
      }
    }, 24); // ~40 words/second natural reading cadence

    return () => clearInterval(interval);
  }, [turnId, text, isNew, tokens]);

  const handleSkip = () => {
    setDisplayedCount(tokens.length);
    if (!completedReportedRef.current) {
      completedReportedRef.current = true;
      setTimeout(() => {
        onCompleteRef.current?.(turnId);
      }, 0);
    }
  };

  const visibleText = isStreaming
    ? tokens.slice(0, displayedCount).join("")
    : text;

  return (
    <div className="space-y-2">
      <div
        className="text-sm leading-relaxed text-slate-800 dark:text-slate-100 whitespace-pre-wrap select-text"
        onClick={() => {
          if (isStreaming) handleSkip();
        }}
      >
        <span>{visibleText}</span>
        {isStreaming && (
          <span
            className="inline-block w-1.5 h-4 ml-0.5 bg-indigo-600 dark:bg-indigo-400 animate-pulse align-middle rounded-xs"
            aria-hidden="true"
          />
        )}
      </div>

      {isStreaming && (
        <div className="flex items-center justify-between text-[11px] text-indigo-600 dark:text-indigo-400 font-medium pt-0.5 select-none">
          <span className="inline-flex items-center gap-1.5 bg-indigo-50 dark:bg-indigo-950/40 px-2 py-0.5 rounded-md border border-indigo-200/50 dark:border-indigo-800/50">
            <Sparkles className="h-3 w-3 animate-spin text-indigo-500" />
            Streaming response…
          </span>
          <button
            type="button"
            onClick={handleSkip}
            className="inline-flex items-center gap-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition cursor-pointer"
            title="Click to show full text instantly"
          >
            <FastForward className="h-3 w-3" />
            <span>Show all</span>
          </button>
        </div>
      )}
    </div>
  );
}
