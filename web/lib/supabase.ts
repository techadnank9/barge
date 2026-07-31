import { createClient } from "@supabase/supabase-js";

export type PracticeEntry = {
  id: number;
  created_at: string;
  source: "phone" | "voiceos";
  song: string;
  hard_spots: string[];
  note: string;
  confident: boolean;
};

export type CallTurn = {
  id: number;
  created_at: string;
  call_sid: string;
  speaker: "caller" | "agent";
  text: string;
};

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);
