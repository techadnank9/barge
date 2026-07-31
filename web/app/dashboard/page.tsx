"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { supabase, PracticeEntry } from "@/lib/supabase";
import ServiceStatus from "@/components/ServiceStatus";
import LiveCallBanner from "@/components/LiveCallBanner";

const SOURCE_LABEL: Record<PracticeEntry["source"], string> = {
  phone: "Phone",
  voiceos: "VoiceOS",
};

const SOURCE_STYLE: Record<PracticeEntry["source"], string> = {
  phone: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
  voiceos: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300",
};

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function Dashboard() {
  const [entries, setEntries] = useState<PracticeEntry[]>([]);
  const [freshId, setFreshId] = useState<number | null>(null);

  useEffect(() => {
    supabase
      .from("practice_entries")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(50)
      .then(({ data }) => {
        if (data) setEntries(data as PracticeEntry[]);
      });

    const channel = supabase
      .channel("practice")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "practice_entries" },
        (payload) => {
          const entry = payload.new as PracticeEntry;
          setEntries((prev) => [entry, ...prev]);
          setFreshId(entry.id);
          setTimeout(() => setFreshId((cur) => (cur === entry.id ? null : cur)), 2000);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black font-sans">
      <header className="border-b border-zinc-200 dark:border-zinc-800 px-8 py-6">
        <Link
          href="/"
          className="text-sm text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
        >
          ← Close the Loop
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4 mt-2">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
            Practice Log
          </h1>
          <div className="flex items-center gap-3">
            <ServiceStatus />
            <Link
              href="/dashboard/logs"
              className="text-xs font-medium text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 underline"
            >
              View logs
            </Link>
          </div>
        </div>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Live feed of guitar coaching sessions from phone and VoiceOS. Click a
          phone entry to see its call transcript.
        </p>
      </header>

      <main className="max-w-3xl mx-auto px-8 py-8">
        <LiveCallBanner />

        {entries.length === 0 && (
          <p className="text-zinc-400 text-center py-16">
            No practice entries yet. Call the coach or log a session in VoiceOS.
          </p>
        )}

        <ul className="flex flex-col gap-3">
          {entries.map((e) => {
            const clickable = e.source === "phone" && !!e.call_sid;
            const content = (
              <>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${SOURCE_STYLE[e.source]}`}
                    >
                      {SOURCE_LABEL[e.source]}
                    </span>
                    <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
                      {e.song}
                    </h2>
                    {!e.confident && (
                      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                        unverified chords
                      </span>
                    )}
                    {clickable && (
                      <span className="text-xs text-zinc-400">view transcript →</span>
                    )}
                  </div>
                  <time className="text-sm text-zinc-400 shrink-0">
                    {formatTime(e.created_at)}
                  </time>
                </div>

                {e.hard_spots.length > 0 && (
                  <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                    Hard spots: {e.hard_spots.join(", ")}
                  </p>
                )}
                {e.note && (
                  <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-500">{e.note}</p>
                )}
              </>
            );

            const className = `block rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-5 transition-colors duration-1000 ${
              freshId === e.id ? "!bg-amber-50 dark:!bg-amber-950/40" : ""
            } ${clickable ? "hover:border-zinc-300 dark:hover:border-zinc-700 cursor-pointer" : ""}`;

            return (
              <li key={e.id}>
                {clickable ? (
                  <Link
                    href={`/dashboard/call?sid=${encodeURIComponent(e.call_sid!)}&song=${encodeURIComponent(e.song)}`}
                    className={className}
                  >
                    {content}
                  </Link>
                ) : (
                  <div className={className}>{content}</div>
                )}
              </li>
            );
          })}
        </ul>
      </main>
    </div>
  );
}
