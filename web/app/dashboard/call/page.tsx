"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import CallTranscript from "@/components/CallTranscript";

function CallPageInner() {
  const params = useSearchParams();
  const sid = params.get("sid");
  const song = params.get("song");

  if (!sid) {
    return (
      <div className="max-w-2xl mx-auto px-8 py-16 text-center text-zinc-400">
        No call selected.{" "}
        <Link href="/dashboard" className="underline hover:text-zinc-600 dark:hover:text-zinc-300">
          Back to practice log
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-8 py-8">
      <Link
        href="/dashboard"
        className="text-sm text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
      >
        ← Practice Log
      </Link>
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50 mt-2">
        {song ? `Call transcript — ${song}` : "Call transcript"}
      </h1>
      <p className="text-zinc-500 dark:text-zinc-400 mt-1 mb-6">
        Turn-by-turn record of this phone coaching session.
      </p>
      <CallTranscript callSid={sid} full />
    </div>
  );
}

export default function CallPage() {
  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black font-sans">
      <Suspense fallback={<p className="px-8 py-16 text-center text-zinc-400">Loading…</p>}>
        <CallPageInner />
      </Suspense>
    </div>
  );
}
