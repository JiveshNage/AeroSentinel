/**
 * supabase.ts — Supabase Client Initialization & Utilities
 * AeroSentinel (SIH26073)
 *
 * Connects to Supabase for:
 * 1. PostgreSQL Realtime subscriptions (alerts, stations, anomalies)
 * 2. Supabase Auth (Email + Password)
 * 3. Secure file uploads to Supabase Storage (aerosentinel-uploads, aerosentinel-reports)
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl: string =
  import.meta.env.VITE_SUPABASE_URL ||
  import.meta.env.NEXT_PUBLIC_SUPABASE_URL ||
  '';

const supabaseAnonKey: string =
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  import.meta.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
  '';

export const isSupabaseConfigured = (): boolean => {
  return Boolean(
    supabaseUrl &&
      supabaseAnonKey &&
      supabaseUrl !== 'https://your-project.supabase.co' &&
      !supabaseUrl.includes('placeholder')
  );
};

export const supabase: SupabaseClient | null = isSupabaseConfigured()
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
      realtime: {
        params: {
          eventsPerSecond: 10,
        },
      },
    })
  : null;

if (!supabase) {
  console.info(
    '[AeroSentinel] Supabase credentials not fully configured. Running with local FastAPI backend & fallback auth.'
  );
} else {
  console.info('[AeroSentinel] Connected to Supabase:', supabaseUrl);
}
