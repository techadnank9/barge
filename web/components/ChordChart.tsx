"use client";

import { useEffect, useState } from "react";
import { supabase, CallChart } from "@/lib/supabase";

function ChordRow({ label, chords }: { label: string; chords: string[] }) {
  if (chords.length === 0) return null;
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-xs font-medium uppercase tracking-wide text-amber-700 dark:text-amber-500 w-14 shrink-0">
        {label}
      </span>
      <div className="flex flex-wrap gap-1.5">
        {chords.map((c, i) => (
          <span
            key={i}
            className="font-mono text-sm font-semibold px-2 py-0.5 rounded-md bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200 border border-amber-200 dark:border-amber-900"
          >
            {c}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function ChordChart({ callSid }: { callSid: string }) {
  const [chart, setChart] = useState<CallChart | null>(null);

  useEffect(() => {
    let cancelled = false;

    supabase
      .from("call_charts")
      .select("*")
      .eq("call_sid", callSid)
      .maybeSingle()
      .then(({ data }) => {
        if (!cancelled && data) setChart(data as CallChart);
      });

    const channel = supabase
      .channel(`call_charts:${callSid}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "call_charts", filter: `call_sid=eq.${callSid}` },
        (payload) => setChart(payload.new as CallChart)
      )
      .subscribe();

    return () => {
      cancelled = true;
      supabase.removeChannel(channel);
    };
  }, [callSid]);

  if (!chart) return null;

  return (
    <div className="rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/60 dark:bg-amber-950/20 p-4 mb-4">
      <div className="flex items-center gap-2 mb-2">
        <h3 className="font-semibold text-zinc-900 dark:text-zinc-50">{chart.song}</h3>
        {!chart.confident && (
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-200">
            unverified chords
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1.5">
        <ChordRow label="Verse" chords={chart.verse} />
        <ChordRow label="Chorus" chords={chart.chorus} />
      </div>
      {chart.hard_spots.length > 0 && (
        <p className="mt-2 text-xs text-amber-800 dark:text-amber-400">
          Watch for: {chart.hard_spots.join(", ")}
        </p>
      )}
    </div>
  );
}
