/**
 * upload.ts — Client API for AWS Telemetry File Ingestion & Parsing
 */

export interface FileRowPreview {
  station_code: string;
  timestamp: string;
  temperature?: number | null;
  humidity?: number | null;
  pressure?: number | null;
  wind_speed?: number | null;
  rainfall?: number | null;
  qc_verdict?: string | null;
  fault_type?: string | null;
}

export interface FileUploadResponse {
  status: string;
  filename: string;
  total_rows: number;
  ingested_count: number;
  duplicates_skipped: number;
  anomalies_detected: number;
  stations_affected: string[];
  preview: FileRowPreview[];
  message: string;
}

import { apiUrl, fetchJson } from './client';

export async function uploadTelemetryFile(
  file: File,
  defaultStationCode?: string
): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (defaultStationCode) {
    formData.append('default_station_code', defaultStationCode);
  }

  return fetchJson<FileUploadResponse>(apiUrl('/api/ingest/upload-file'), {
    method: 'POST',
    body: formData,
  });
}


export async function uploadRawCsvText(
  csvContent: string,
  filename: string = 'batch_data.csv',
  defaultStationCode?: string
): Promise<FileUploadResponse> {
  const blob = new Blob([csvContent], { type: 'text/csv' });
  const file = new File([blob], filename, { type: 'text/csv' });
  return uploadTelemetryFile(file, defaultStationCode);
}
