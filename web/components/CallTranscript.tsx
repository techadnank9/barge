"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { supabase, CallTurn } from "@/lib/supabase";
import ChordChart from "@/components/ChordChart";

const LIVE_WINDOW_MS = 2 * 60 * 1000; // last turn within 2min -> still "live"
const GROUP_GAP_MS = 20 * 1000; // consecutive same-speaker turns within 20s render as one group

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

type TurnGroup = { speaker: CallTurn["speaker"]; turns: CallTurn[] };

function groupTurns(turns: CallTurn[]): TurnGroup[] {
  const groups: TurnGroup[] = [];
  for (const t of turns) {
    const last = groups[groups.length - 1];
    const lastTurn = last?.turns[last.turns.length - 1];
    const withinGap =
      lastTurn && new Date(t.created_at).getTime() - new Date(lastTurn.created_at).getTime() < GROUP_GAP_MS;
    if (last && last.speaker === t.speaker && withinGap) {
      last.turns.push(t);
    } else {
      groups.push({ speaker: t.speaker, turns: [t] });
    }
  }
  return groups;
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

  const groups = useMemo(() => groupTurns(turns), [turns]);

  return (
    <div>
      <div className="sticky top-4 z-10">
        <ChordChart callSid={callSid} />
      </div>
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
          className={`${full ? "" : "max-h-72"} overflow-y-auto px-4 py-4 flex flex-col gap-4`}
        >
          {groups.map((g, gi) => {
            const isCaller = g.speaker === "caller";
            return (
              <div
                key={g.turns[0].id}
                className={`flex flex-col max-w-[85%] ${isCaller ? "self-end items-end" : "self-start items-start"}`}
              >
                <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-zinc-400 mb-1 px-1">
                  {!isCaller && (
                    <span className="w-3.5 h-3.5 rounded-full bg-amber-500 dark:bg-amber-600 shrink-0" />
                  )}
                  {isCaller ? "Caller" : "Coach"} · {formatTime(g.turns[0].created_at)}
                </span>
                <div className={`flex flex-col gap-1 w-full ${isCaller ? "items-end" : "items-start"}`}>
                  {g.turns.map((t, ti) => (
                    <p
                      key={t.id}
                      className={`text-sm leading-relaxed px-3.5 py-2 shadow-sm ${
                        isCaller
                          ? "bg-blue-600 text-white dark:bg-blue-600"
                          : "bg-white text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-700"
                      } ${
                        // iMessage-style corner rounding: tight between grouped bubbles, round at the group's outer corners
                        ti === 0 && ti === g.turns.length - 1
                          ? "rounded-2xl"
                          : ti === 0
                          ? isCaller
                            ? "rounded-2xl rounded-br-md"
                            : "rounded-2xl rounded-bl-md"
                          : ti === g.turns.length - 1
                          ? isCaller
                            ? "rounded-2xl rounded-tr-md"
                            : "rounded-2xl rounded-tl-md"
                          : isCaller
                          ? "rounded-2xl rounded-r-md"
                          : "rounded-2xl rounded-l-md"
                      }`}
                    >
                      {t.text}
                    </p>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      </div>
    </div>
  );
}
