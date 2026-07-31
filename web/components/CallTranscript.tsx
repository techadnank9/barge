"use client";

import { useEffect, useRef, useState } from "react";
import { supabase, CallTurn } from "@/lib/supabase";

const LIVE_WINDOW_MS = 2 * 60 * 1000; // last turn within 2min -> still "live"

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function CallTranscript({ callSid, full = false }: { callSid: string; full?: boolean }) {
  const [turns, setTurns] = useState<CallTurn[]>([]);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    supabase
      .from("call_turns")
      .select("*")
      .eq("call_sid", callSid)
      .order("created_at", { ascending: true })
      .then(({ data }) => {
        if (cancelled) return;
        const rows = (data ?? []) as CallTurn[];
        setTurns(rows);
        setLoading(false);
        if (rows.length > 0) {
          const lastTs = new Date(rows[rows.length - 1].created_at).getTime();
          setLive(Date.now() - lastTs < LIVE_WINDOW_MS);
        }
      });

    const channel = supabase
      .channel(`call_turns:${callSid}`)
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "call_turns", filter: `call_sid=eq.${callSid}` },
        (payload) => {
          const turn = payload.new as CallTurn;
          setTurns((prev) => (prev.some((t) => t.id === turn.id) ? prev : [...prev, turn]));
          setLive(true);
        }
      )
      .subscribe();

    return () => {
      cancelled = true;
      supabase.removeChannel(channel);
    };
  }, [callSid]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-200 dark:border-zinc-800">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            live ? "bg-red-500 animate-pulse" : "bg-zinc-300 dark:bg-zinc-700"
          }`}
        />
        <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {live ? "Live transcript" : "Transcript"}
        </h3>
      </div>

      {loading ? (
        <p className="px-4 py-4 text-sm text-zinc-400">Loading…</p>
      ) : turns.length === 0 ? (
        <p className="px-4 py-4 text-sm text-zinc-400">No transcript recorded for this call.</p>
      ) : (
        <div
          ref={scrollRef}
          className={`${full ? "" : "max-h-72"} overflow-y-auto px-4 py-3 flex flex-col gap-3`}
        >
          {turns.map((t) => (
            <div
              key={t.id}
              className={`flex flex-col max-w-[85%] ${t.speaker === "caller" ? "self-end items-end" : "self-start items-start"}`}
            >
              <span className="text-[10px] uppercase tracking-wide text-zinc-400 mb-0.5">
                {t.speaker === "caller" ? "Caller" : "Coach"} · {formatTime(t.created_at)}
              </span>
              <p
                className={`text-sm rounded-2xl px-3 py-2 ${
                  t.speaker === "caller"
                    ? "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200"
                    : "bg-white text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
                }`}
              >
                {t.text}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
