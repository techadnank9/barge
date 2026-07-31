"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { supabase, CallTurn, CallChart } from "@/lib/supabase";

const LIVE_WINDOW_MS = 2 * 60 * 1000;

export default function LiveCallBanner() {
  const [callSid, setCallSid] = useState<string | null>(null);
  const [song, setSong] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const markIdleLater = () => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => setLive(false), LIVE_WINDOW_MS);
  };

  useEffect(() => {
    supabase
      .from("call_turns")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(1)
      .then(({ data }) => {
        const latest = (data as CallTurn[] | null)?.[0];
        if (!latest) return;
        setCallSid(latest.call_sid);
        const lastTs = new Date(latest.created_at).getTime();
        if (Date.now() - lastTs < LIVE_WINDOW_MS) {
          setLive(true);
          markIdleLater();
        }
      });

    const turnsChannel = supabase
      .channel("live-call-turns")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "call_turns" },
        (payload) => {
          const turn = payload.new as CallTurn;
          setCallSid(turn.call_sid);
          setLive(true);
          markIdleLater();
        }
      )
      .subscribe();

    const chartsChannel = supabase
      .channel("live-call-charts")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "call_charts" },
        (payload) => {
          const chart = payload.new as CallChart;
          setCallSid((sid) => {
            if (chart.call_sid === sid || sid === null) setSong(chart.song);
            return sid ?? chart.call_sid;
          });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(turnsChannel);
      supabase.removeChannel(chartsChannel);
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
  }, []);

  useEffect(() => {
    setSong(null);
    if (!callSid) return;
    supabase
      .from("call_charts")
      .select("*")
      .eq("call_sid", callSid)
      .maybeSingle()
      .then(({ data }) => {
        if (data) setSong((data as CallChart).song);
      });
  }, [callSid]);

  if (!live || !callSid) return null;

  return (
    <Link
      href={`/dashboard/call?sid=${encodeURIComponent(callSid)}${song ? `&song=${encodeURIComponent(song)}` : ""}`}
      className="flex items-center gap-3 rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 px-5 py-3 mb-6 hover:border-red-300 dark:hover:border-red-800 transition-colors"
    >
      <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse shrink-0" />
      <span className="font-medium text-red-900 dark:text-red-300">
        Call in progress{song ? ` — ${song}` : ""}
      </span>
      <span className="text-sm text-red-600 dark:text-red-400 ml-auto">
        view live →
      </span>
    </Link>
  );
}
