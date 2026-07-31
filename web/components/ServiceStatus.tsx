"use client";

import { useCallback, useEffect, useState } from "react";

const SERVICES = [
  { key: "phone", label: "Phone", url: "https://close-the-loop-phone.onrender.com/" },
  { key: "mcp", label: "MCP", url: "https://close-the-loop-mcp.onrender.com/" },
] as const;

type Status = "checking" | "awake" | "asleep";

const DOT: Record<Status, string> = {
  checking: "bg-amber-500 animate-pulse",
  awake: "bg-emerald-500",
  asleep: "bg-zinc-400 dark:bg-zinc-500",
};

const LABEL: Record<Status, string> = {
  checking: "waking…",
  awake: "awake",
  asleep: "asleep — click to wake",
};

function ServiceButton({ label, url }: { label: string; url: string }) {
  const [status, setStatus] = useState<Status>("checking");

  // Pings the real endpoint (no client-side timeout) so a sleeping Render
  // free-tier service actually gets woken, not just probed.
  const ping = useCallback(async () => {
    setStatus("checking");
    try {
      await fetch(url, { mode: "no-cors", cache: "no-store" });
      setStatus("awake");
    } catch {
      setStatus("asleep");
    }
  }, [url]);

  useEffect(() => {
    ping();
    // Re-ping periodically — doubles as a keep-warm heartbeat while the
    // dashboard tab is open.
    const id = setInterval(ping, 60000);
    return () => clearInterval(id);
  }, [ping]);

  return (
    <button
      onClick={ping}
      disabled={status === "checking"}
      title={url}
      className="flex items-center gap-2 rounded-full border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-3 py-1.5 text-xs font-medium text-zinc-700 dark:text-zinc-300 disabled:cursor-default enabled:hover:bg-zinc-50 dark:enabled:hover:bg-zinc-900 transition-colors"
    >
      <span className={`w-2 h-2 rounded-full shrink-0 ${DOT[status]}`} />
      {label}: {LABEL[status]}
    </button>
  );
}

export default function ServiceStatus() {
  return (
    <div className="flex flex-wrap gap-2">
      {SERVICES.map((s) => (
        <ServiceButton key={s.key} label={s.label} url={s.url} />
      ))}
    </div>
  );
}
