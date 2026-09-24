/**
 * realtime.ts — Supabase Realtime Subscriptions
 * AeroSentinel (SIH26073)
 *
 * Implements real-time row-level subscriptions for:
 * 1. Alerts (INSERT, UPDATE) -> Synchronizes live operational feed
 * 2. Stations (UPDATE) -> Reflects online/offline/degraded status transitions
 * 3. Anomalies / QC Results (INSERT) -> Immediate notification of detected flags
 * 4. Maintenance Tasks (INSERT, UPDATE) -> Task status updates
 */

import { supabase } from './supabase';
import { RealtimeChannel } from '@supabase/supabase-js';

export interface RealtimeSubscriptionOptions {
  onInsert?: (payload: any) => void;
  onUpdate?: (payload: any) => void;
  onDelete?: (payload: any) => void;
}

/**
 * Subscribe to Supabase Realtime changes on the alerts table.
 * Returns an unsubscribe teardown function.
 */
export function subscribeToAlerts(options: RealtimeSubscriptionOptions): () => void {
  const client = supabase;
  if (!client) return () => {};

  const channel: RealtimeChannel = client
    .channel('realtime:alerts')
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'alerts' },
      (payload) => {
        if (options.onInsert) options.onInsert(payload.new);
      }
    )
    .on(
      'postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'alerts' },
      (payload) => {
        if (options.onUpdate) options.onUpdate(payload.new);
      }
    )
    .subscribe();

  return () => {
    client.removeChannel(channel);
  };
}

/**
 * Subscribe to Supabase Realtime changes on stations.
 */
export function subscribeToStations(options: RealtimeSubscriptionOptions): () => void {
  const client = supabase;
  if (!client) return () => {};

  const channel: RealtimeChannel = client
    .channel('realtime:stations')
    .on(
      'postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'stations' },
      (payload) => {
        if (options.onUpdate) options.onUpdate(payload.new);
      }
    )
    .subscribe();

  return () => {
    client.removeChannel(channel);
  };
}

/**
 * Subscribe to Supabase Realtime changes on anomalies / qc_results.
 */
export function subscribeToAnomalies(options: RealtimeSubscriptionOptions): () => void {
  const client = supabase;
  if (!client) return () => {};

  const channel: RealtimeChannel = client
    .channel('realtime:qc_results')
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'qc_results' },
      (payload) => {
        if (options.onInsert) options.onInsert(payload.new);
      }
    )
    .subscribe();

  return () => {
    client.removeChannel(channel);
  };
}

/**
 * Subscribe to Supabase Realtime changes on system_tasks / maintenance_tasks.
 */
export function subscribeToMaintenanceTasks(options: RealtimeSubscriptionOptions): () => void {
  const client = supabase;
  if (!client) return () => {};

  const channel: RealtimeChannel = client
    .channel('realtime:system_tasks')
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'system_tasks' },
      (payload) => {
        if (options.onInsert) options.onInsert(payload.new);
      }
    )
    .subscribe();

  return () => {
    client.removeChannel(channel);
  };
}
