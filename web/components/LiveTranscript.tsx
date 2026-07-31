"use client";

import { useEffect, useRef, useState } from "react";
import { supabase, CallTurn } from "@/lib/supabase";

const IDLE_MS = 2 * 60 * 1000; // no new turn for 2min -> treat call as ended

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function LiveTranscript() {
  const [turns, setTurns] = useState<CallTurn[]>([]);
  const [callSid, setCallSid] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const markIdleLater = () => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => setLive(false), IDLE_MS);
  };

  useEffect(() => {
    supabase
      .from("call_turns")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(50)
      .then(({ data }) => {
        if (!data || data.length === 0) return;
        const latestSid = (data as CallTurn[])[0].call_sid;
        const thisCall = (data as CallTurn[])
          .filter((t) => t.call_sid === latestSid)
          .reverse();
        setCallSid(latestSid);
        setTurns(thisCall);
        const lastTs = new Date(thisCall[thisCall.length - 1].created_at).getTime();
        if (Date.now() - lastTs < IDLE_MS) {
          setLive(true);
          markIdleLater();
        }
      });

    const channel = supabase
      .channel("call_turns")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "call_turns" },
        (payload) => {
          const turn = payload.new as CallTurn;
          setCallSid((prevSid) => {
            if (turn.call_sid !== prevSid) {
              setTurns([turn]);
            } else {
              setTurns((prev) => (prev.some((t) => t.id === turn.id) ? prev : [...prev, turn]));
            }
            return turn.call_sid;
          });
          setLive(true);
          markIdleLater();
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  if (!callSid) return null;

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-zinc-200 dark:border-zinc-800">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            live ? "bg-red-500 animate-pulse" : "bg-zinc-300 dark:bg-zinc-700"
          }`}
        />
        <h2 className="font-medium text-zinc-900 dark:text-zinc-50">
          {live ? "Live call" : "Last call"}
        </h2>
        <span className="text-xs text-zinc-400 ml-auto">{callSid.slice(0, 12)}</span>
      </div>
      <div ref={scrollRef} className="max-h-72 overflow-y-auto px-5 py-4 flex flex-col gap-3">
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
                  : "bg-zinc-100 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
              }`}
            >
              {t.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
