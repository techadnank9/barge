"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const SOURCES = [
  { key: "phone", label: "Phone", url: "https://close-the-loop-phone.onrender.com/logs" },
  { key: "mcp", label: "MCP", url: "https://close-the-loop-mcp.onrender.com/logs" },
] as const;

type LogEntry = {
  ts: number;
  kind: string;
  message: string;
  source: "phone" | "mcp";
};

function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

const KIND_STYLE: Record<string, string> = {
  voice: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
  "handle-song": "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
  finish: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  log_turn_error: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  log_practice_error: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  schedule_practice_error: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  get_chord_chart: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300",
  log_practice: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300",
  schedule_practice: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300",
};

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const results = await Promise.all(
          SOURCES.map(async (s) => {
            const res = await fetch(s.url, { cache: "no-store" });
            const data = (await res.json()) as Omit<LogEntry, "source">[];
            return data.map((d) => ({ ...d, source: s.key as "phone" | "mcp" }));
          })
        );
        if (cancelled) return;
        const merged = results.flat().sort((a, b) => b.ts - a.ts);
        setLogs(merged);
        setError(null);
      } catch {
        if (!cancelled) setError("Couldn't reach one or both services. They may be asleep.");
      }
    };

    poll();
    const id = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black font-sans">
      <header className="border-b border-zinc-200 dark:border-zinc-800 px-8 py-6">
        <Link
          href="/dashboard"
          className="text-sm text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
        >
          ← Practice Log
        </Link>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50 mt-2">Logs</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Live request/event feed from the phone and MCP services. In-memory only —
          resets on redeploy.
        </p>
      </header>

      <main className="max-w-3xl mx-auto px-8 py-8">
        {error && <p className="text-amber-600 dark:text-amber-400 text-sm mb-4">{error}</p>}

        {logs.length === 0 ? (
          <p className="text-zinc-400 text-center py-16">No events yet.</p>
        ) : (
          <ul className="flex flex-col gap-2 font-mono text-xs">
            {logs.map((l, i) => (
              <li
                key={`${l.source}-${l.ts}-${i}`}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-3 py-2"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-zinc-400">{formatTime(l.ts)}</span>
                  <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                    {l.source}
                  </span>
                  <span
                    className={`text-[10px] uppercase px-1.5 py-0.5 rounded ${
                      KIND_STYLE[l.kind] ?? "bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400"
                    }`}
                  >
                    {l.kind}
                  </span>
                </div>
                <p className="text-zinc-700 dark:text-zinc-300 break-all whitespace-pre-wrap">
                  {l.message}
                </p>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
