/**
 * retrain.ts — API client for Model Retraining and Governance (F14)
 */

export interface RetrainMetrics {
  job_id: string;
  total_training_samples: number;
  feedback_samples_used: number;
  false_alarms_count: number;
  confirmed_faults_count: number;
  previous_version?: string | null;
  previous_threshold: number;
  new_threshold: number;
  false_alarms_eliminated_count: number;
  false_alarm_reduction_pct: number;
  retained_fault_recall_pct: number;
}

export interface RetrainResponse {
  job_id: string;
  variable: string;
  previous_version?: string | null;
  new_version: string;
  model_registry_id: number;
  metrics: RetrainMetrics;
  artifact_path: string;
  trained_at: string;
  message: string;
}

export interface ModelRegistryItem {
  id: number;
  model_type: string;
  variable: string;
  version: string;
  trained_at: string;
  training_data_range?: string | null;
  metrics: Record<string, any>;
  artifact_path: string;
  is_active: boolean;
}

export interface ModelRegistryListResponse {
  total: number;
  models: ModelRegistryItem[];
}

export interface FeedbackPoolStats {
  variable: string;
  total_feedback_count: number;
  confirmed_faults_count: number;
  false_alarms_count: number;
  unsure_count: number;
  can_retrain: boolean;
  active_model_version?: string | null;
}

import { apiUrl, fetchJson } from './client';

export async function fetchRetrainStats(variable: string = 'temperature'): Promise<FeedbackPoolStats> {
  return fetchJson<FeedbackPoolStats>(apiUrl(`/api/retrain/stats?variable=${encodeURIComponent(variable)}`));
}

export async function triggerRetraining(params?: {
  variable?: string;
  new_version?: string;
  target_false_alarm_reduction?: number;
}): Promise<RetrainResponse> {
  return fetchJson<RetrainResponse>(apiUrl('/api/retrain/trigger'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      variable: params?.variable || 'temperature',
      new_version: params?.new_version || null,
      target_false_alarm_reduction: params?.target_false_alarm_reduction ?? 1.0,
    }),
  });
}

export async function fetchRegisteredModels(variable?: string): Promise<ModelRegistryListResponse> {
  const qs = variable ? `?variable=${encodeURIComponent(variable)}` : '';
  return fetchJson<ModelRegistryListResponse>(apiUrl(`/api/retrain/models${qs}`));
}

export async function activateModelVersion(modelId: number): Promise<ModelRegistryItem> {
  return fetchJson<ModelRegistryItem>(apiUrl(`/api/retrain/models/${modelId}/activate`), {
    method: 'POST',
  });
}

