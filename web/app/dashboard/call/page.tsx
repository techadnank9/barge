"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import ChordChart from "@/components/ChordChart";
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
    <div className="max-w-2xl mx-auto px-8 pb-10">
      <div className="sticky top-0 z-20 pt-5 pb-4 bg-zinc-50/95 dark:bg-black/95 backdrop-blur-md border-b border-zinc-200 dark:border-zinc-800 shadow-sm shadow-black/[0.03] dark:shadow-black/20">
        <div className="flex items-center justify-between">
          <Link
            href="/dashboard"
            className="text-sm text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
          >
            ← Practice Log
          </Link>
          <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">
            Call transcript
          </span>
        </div>
        <div className="mt-3">
          <ChordChart callSid={sid} />
        </div>
      </div>

      <div className="pt-5">
        <CallTranscript callSid={sid} full />
      </div>
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
