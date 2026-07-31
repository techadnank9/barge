import Link from "next/link";

const PHONE_NUMBER = "+1 (313) 479-6171";
const PHONE_HREF = "tel:+13134796171";

function StringsBackdrop() {
  return (
    <svg
      className="pointer-events-none absolute inset-x-0 top-0 h-[420px] w-full opacity-[0.15] dark:opacity-[0.12]"
      viewBox="0 0 1200 420"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {[60, 110, 160, 210, 260, 310].map((y, i) => (
        <path
          key={y}
          d={`M -100 ${y} Q 600 ${y - 40 + i * 6} 1300 ${y}`}
          stroke="currentColor"
          strokeWidth={i === 0 || i === 5 ? 2.5 : 1.2}
          fill="none"
        />
      ))}
    </svg>
  );
}

function PickIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d="M12 2c5 0 8.5 4.2 8.5 8.8 0 6-5.3 10.4-8.5 11.2-3.2-.8-8.5-5.2-8.5-11.2C3.5 6.2 7 2 12 2Z" />
    </svg>
  );
}

function WaveIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M2 12h2l2-7 3 14 3-11 2 4h8" />
    </svg>
  );
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#fbf4e9] dark:bg-[#1a120a] font-sans flex flex-col relative overflow-hidden text-[#3a2a18] dark:text-[#f2e4cc]">
      <StringsBackdrop />

      <main className="relative flex-1 flex flex-col items-center justify-center px-8 py-20 text-center">
        <div className="flex items-center gap-2 mb-5">
          <PickIcon className="w-4 h-4 text-amber-700 dark:text-amber-500" />
          <span className="text-xs font-semibold tracking-widest uppercase text-amber-800 dark:text-amber-500">
            Voice-AI guitar coach
          </span>
        </div>

        <h1 className="text-5xl sm:text-6xl font-serif font-bold max-w-2xl leading-tight text-[#2b1c0e] dark:text-[#f7ecd8]">
          Close the Loop
        </h1>
        <p className="mt-5 max-w-lg text-lg text-[#5c452c] dark:text-[#c9b28c]">
          Call a real number, get coached through a song by voice, and get the
          chords texted to you. Or log a practice by voice in VoiceOS and
          watch it land on the dashboard live.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row gap-4">
          <a
            href={PHONE_HREF}
            className="rounded-full bg-gradient-to-b from-amber-700 to-amber-900 dark:from-amber-600 dark:to-amber-800 text-amber-50 px-6 py-3 font-medium shadow-lg shadow-amber-900/20 hover:brightness-110 transition-[filter]"
          >
            Call {PHONE_NUMBER}
          </a>
          <Link
            href="/dashboard"
            className="rounded-full border-2 border-amber-800/40 dark:border-amber-500/40 px-6 py-3 font-medium text-[#2b1c0e] dark:text-[#f7ecd8] hover:bg-amber-900/5 dark:hover:bg-amber-500/10 transition-colors"
          >
            View live dashboard →
          </Link>
        </div>

        <div className="mt-16 grid sm:grid-cols-2 gap-6 max-w-2xl text-left">
          <div className="rounded-xl border border-amber-900/15 dark:border-amber-100/10 bg-white/70 dark:bg-[#241a0f]/70 backdrop-blur-sm p-5">
            <div className="flex items-center gap-2">
              <PickIcon className="w-4 h-4 text-amber-700 dark:text-amber-500" />
              <h2 className="font-semibold text-[#2b1c0e] dark:text-[#f7ecd8]">Phone</h2>
            </div>
            <p className="mt-2 text-sm text-[#6b543a] dark:text-[#c9b28c]">
              Call, name a song, get coached through it by voice. The chords
              land by SMS — only after the text actually sends.
            </p>
          </div>
          <div className="rounded-xl border border-amber-900/15 dark:border-amber-100/10 bg-white/70 dark:bg-[#241a0f]/70 backdrop-blur-sm p-5">
            <div className="flex items-center gap-2">
              <WaveIcon className="w-4 h-4 text-amber-700 dark:text-amber-500" />
              <h2 className="font-semibold text-[#2b1c0e] dark:text-[#f7ecd8]">VoiceOS</h2>
            </div>
            <p className="mt-2 text-sm text-[#6b543a] dark:text-[#c9b28c]">
              A custom MCP connector. Say &ldquo;log my practice&rdquo; and a
              row appears on the dashboard the instant it&apos;s written.
            </p>
          </div>
        </div>

        <p className="mt-12 text-sm text-[#8a7256] dark:text-[#9c8562] max-w-md">
          Never claims a side effect that didn&apos;t happen — it says
          &ldquo;texted you&rdquo; or &ldquo;logged&rdquo; only after the fact,
          and says so honestly when it fails.
        </p>
      </main>

      <footer className="relative px-8 py-6 text-center text-xs text-[#8a7256] dark:text-[#9c8562] border-t border-amber-900/10 dark:border-amber-100/10">
        <a
          href="https://github.com/techadnank9/barge"
          className="hover:text-amber-800 dark:hover:text-amber-400"
        >
          Source on GitHub
        </a>
      </footer>
    </div>
  );
}
