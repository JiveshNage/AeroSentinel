import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  CheckCircle,
  AlertCircle,
  Download,
  Shield,
  FileSpreadsheet,
  RefreshCw,
  MapPin,
  ArrowRight,
} from 'lucide-react';
import { uploadTelemetryFile, uploadRawCsvText, FileUploadResponse } from '../api/upload';
import { AuthUser } from '../api/auth';

interface FileUploadViewProps {
  currentUser: AuthUser | null;
  onInspectStation: (stationCode: string) => void;
}

const PRESET_DATASETS = [
  {
    name: 'NCR Monsoon Cloudburst Batch',
    desc: 'Simulated high-volume precipitation telemetry across Delhi, Gurugram, and Noida.',
    csv: `station_code,timestamp,temperature,humidity,pressure,wind_speed,wind_direction,rainfall,solar_radiation
NCR001,2026-09-24T14:00:00Z,27.5,92.0,998.4,14.2,110,48.5,120.0
NCR001,2026-09-24T14:15:00Z,26.8,94.5,997.9,16.5,105,62.0,90.0
NCR002,2026-09-24T14:00:00Z,28.1,89.0,999.1,12.8,115,35.0,150.0
NCR003,2026-09-24T14:00:00Z,27.2,93.5,998.0,15.1,108,55.2,105.0
NCR004,2026-09-24T14:00:00Z,28.4,87.0,1000.2,10.4,120,28.0,180.0`,
  },
  {
    name: 'Severe Heatwave Sensor Spike Test',
    desc: 'Contains normal baseline readings mixed with step-change thermal anomaly spikes (+51.5°C).',
    csv: `station_code,timestamp,temperature,humidity,pressure,wind_speed,wind_direction,rainfall,solar_radiation
NCR001,2026-09-24T15:00:00Z,38.2,34.0,1008.2,4.5,280,0.0,920.0
NCR001,2026-09-24T15:15:00Z,51.8,32.5,1008.0,4.8,285,0.0,940.0
NCR002,2026-09-24T15:00:00Z,37.9,35.2,1008.9,4.2,275,0.0,900.0
NCR005,2026-09-24T15:00:00Z,38.6,33.1,1007.8,5.1,290,0.0,935.0`,
  },
  {
    name: 'Barometric Sensor Flatline Batch',
    desc: 'Simulates analog transducer freeze with identical atmospheric pressure for 4 steps.',
    csv: `station_code,timestamp,temperature,humidity,pressure,wind_speed,wind_direction,rainfall,solar_radiation
NCR007,2026-09-24T16:00:00Z,33.4,52.0,1012.3,3.1,240,0.0,750.0
NCR007,2026-09-24T16:15:00Z,33.5,51.8,1012.3,3.3,245,0.0,740.0
NCR007,2026-09-24T16:30:00Z,33.6,51.5,1012.3,3.0,240,0.0,730.0
NCR007,2026-09-24T16:45:00Z,33.4,51.9,1012.3,3.2,250,0.0,710.0`,
  },
];

export const FileUploadView: React.FC<FileUploadViewProps> = ({ currentUser, onInspectStation }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [defaultStation, setDefaultStation] = useState<string>('NCR001');
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadResult, setUploadResult] = useState<FileUploadResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activeRole = currentUser?.role || 'admin';
  const hasUploadClearance = activeRole === 'admin' || activeRole === 'data_quality_officer';

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (!hasUploadClearance) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0]);
      setUploadResult(null);
      setErrorMessage(null);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setUploadResult(null);
      setErrorMessage(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setErrorMessage(null);
    try {
      const res = await uploadTelemetryFile(selectedFile, defaultStation);
      setUploadResult(res);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Upload processing failed');
    } finally {
      setUploading(false);
    }
  };

  const handleLoadPreset = async (preset: typeof PRESET_DATASETS[0]) => {
    if (!hasUploadClearance) return;
    setUploading(true);
    setErrorMessage(null);
    try {
      const res = await uploadRawCsvText(preset.csv, `${preset.name.toLowerCase().replace(/\s+/g, '_')}.csv`, defaultStation);
      setUploadResult(res);
      setSelectedFile(null);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Preset processing failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-panel border border-line rounded-lg p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[0.75rem] font-mono uppercase tracking-wider text-accent font-semibold flex items-center space-x-1">
                <UploadCloud className="w-3.5 h-3.5" />
                <span>Telemetry Ingestion Gateway</span>
              </span>
              <span className="text-line">•</span>
              <span className="text-[0.75rem] font-mono text-muted">Feature F1 & F2 Ingestion</span>
            </div>
            <h2 className="text-[1.25rem] font-semibold text-ink mt-1 font-sans">
              Batch AWS Observation File Ingestion
            </h2>
            <p className="text-[0.8125rem] text-muted mt-1 max-w-3xl font-sans">
              Upload historical CSV, NetCDF, or JSON weather records. Every record is automatically
              validated, deduplicated, and processed in real time through the IsolationForest and 3D
              KDTree QC engines.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <a
              href="/api/ingest/template.csv"
              download="aerosentinel_sample_template.csv"
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-surface border border-line text-ink text-xs font-medium hover:bg-panel transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-accent" />
              <span>Download CSV Template</span>
            </a>
          </div>
        </div>

        {/* RBAC Role Notice */}
        {!hasUploadClearance && (
          <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded text-amber-300 text-xs flex items-center space-x-2">
            <Shield className="w-4 h-4 shrink-0 text-amber-400" />
            <span>
              <strong>RBAC Notice:</strong> You are currently logged in as{' '}
              <strong>{activeRole}</strong>. Telemetry file ingestion requires{' '}
              <strong>Admin</strong> or <strong>Data Quality Officer</strong> role privileges. Switch
              roles in the top navbar to upload data.
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Dropzone & Controls (Left 2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-panel border border-line rounded-lg p-5 space-y-4">
            <h3 className="text-sm font-semibold text-ink font-sans flex items-center space-x-2">
              <FileSpreadsheet className="w-4 h-4 text-accent" />
              <span>Upload Weather Station Observation File</span>
            </h3>

            {/* Drag & Drop Area */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleFileDrop}
              onClick={() => hasUploadClearance && fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-all cursor-pointer ${
                !hasUploadClearance
                  ? 'border-line/40 bg-surface/30 cursor-not-allowed opacity-60'
                  : isDragOver
                  ? 'border-accent bg-accent/5 scale-[0.99]'
                  : selectedFile
                  ? 'border-status-valid/50 bg-status-valid/5'
                  : 'border-line hover:border-accent/50 bg-surface/50'
              }`}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept=".csv,.json,.txt"
                disabled={!hasUploadClearance}
                className="hidden"
              />

              <div className="flex flex-col items-center justify-center space-y-2">
                <UploadCloud
                  className={`w-10 h-10 ${
                    selectedFile
                      ? 'text-status-valid'
                      : isDragOver
                      ? 'text-accent'
                      : 'text-muted'
                  }`}
                />
                {selectedFile ? (
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-ink font-sans">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-muted font-mono">
                      {(selectedFile.size / 1024).toFixed(1)} KB · Ready to ingest
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-ink">
                      Drag & drop weather observation file, or click to browse
                    </p>
                    <p className="text-[0.6875rem] text-muted font-mono">
                      Supports .CSV, .JSON (station_code, timestamp, temperature, humidity, pressure, wind...)
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Options bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center space-x-2 text-xs">
                <span className="text-muted font-mono">Default Station Fallback:</span>
                <select
                  value={defaultStation}
                  onChange={(e) => setDefaultStation(e.target.value)}
                  className="bg-surface border border-line rounded px-2.5 py-1 text-ink focus:outline-none cursor-pointer text-xs"
                >
                  <option value="NCR001">NCR001 — Delhi Safdarjung</option>
                  <option value="NCR002">NCR002 — Gurugram</option>
                  <option value="NCR003">NCR003 — Noida</option>
                  <option value="NCR005">NCR005 — Ghaziabad</option>
                  <option value="NCR010">NCR010 — Alwar</option>
                </select>
              </div>

              <div className="flex items-center space-x-2">
                {selectedFile && (
                  <button
                    onClick={() => {
                      setSelectedFile(null);
                      setUploadResult(null);
                    }}
                    className="px-3 py-1.5 rounded bg-surface border border-line text-muted hover:text-ink text-xs"
                  >
                    Clear
                  </button>
                )}
                <button
                  disabled={!selectedFile || !hasUploadClearance || uploading}
                  onClick={handleUpload}
                  className="flex items-center space-x-1.5 px-4 py-1.5 rounded bg-accent text-white text-xs font-semibold hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors"
                >
                  {uploading ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Ingesting & Running QC...</span>
                    </>
                  ) : (
                    <>
                      <UploadCloud className="w-3.5 h-3.5" />
                      <span>Process & Ingest File</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {errorMessage && (
              <div className="p-3 bg-status-anomalous/10 border border-status-anomalous/30 rounded text-status-anomalous text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}
          </div>

          {/* Upload Results & Ingested Telemetry Preview */}
          {uploadResult && (
            <div className="bg-panel border border-line rounded-lg p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="w-5 h-5 text-status-valid" />
                  <div>
                    <h4 className="text-sm font-semibold text-ink">
                      Ingestion & Multi-Tier QC Completed
                    </h4>
                    <p className="text-xs text-muted font-mono">{uploadResult.filename}</p>
                  </div>
                </div>
                <span className="text-[0.6875rem] font-mono text-status-valid bg-status-valid/10 px-2 py-0.5 rounded border border-status-valid/30">
                  PIPELINE VERIFIED
                </span>
              </div>

              {/* Statistics Counters */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="p-3 rounded bg-surface border border-line">
                  <div className="text-xs font-mono text-muted uppercase">Total Rows</div>
                  <div className="text-lg font-bold text-ink mt-0.5 font-mono">
                    {uploadResult.total_rows}
                  </div>
                </div>
                <div className="p-3 rounded bg-surface border border-line">
                  <div className="text-xs font-mono text-muted uppercase">Ingested</div>
                  <div className="text-lg font-bold text-status-valid mt-0.5 font-mono">
                    {uploadResult.ingested_count}
                  </div>
                </div>
                <div className="p-3 rounded bg-surface border border-line">
                  <div className="text-xs font-mono text-muted uppercase">Duplicates</div>
                  <div className="text-lg font-bold text-muted mt-0.5 font-mono">
                    {uploadResult.duplicates_skipped}
                  </div>
                </div>
                <div className="p-3 rounded bg-surface border border-line">
                  <div className="text-xs font-mono text-muted uppercase">QC Anomalies</div>
                  <div className="text-lg font-bold text-status-anomalous mt-0.5 font-mono">
                    {uploadResult.anomalies_detected}
                  </div>
                </div>
              </div>

              {/* Affected Stations */}
              {uploadResult.stations_affected.length > 0 && (
                <div className="flex items-center space-x-2 text-xs">
                  <span className="text-muted font-mono">Stations Updated:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {uploadResult.stations_affected.map((code) => (
                      <button
                        key={code}
                        onClick={() => onInspectStation(code)}
                        className="px-2 py-0.5 rounded bg-surface border border-line text-accent hover:underline text-[0.6875rem] font-mono flex items-center space-x-1"
                      >
                        <MapPin className="w-2.5 h-2.5" />
                        <span>{code}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Preview Rows Table */}
              {uploadResult.preview.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-ink font-sans">
                    Ingested Records & Real-Time QC Triage Preview
                  </div>
                  <div className="overflow-x-auto border border-line rounded">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-surface border-b border-line text-muted text-[0.6875rem]">
                        <tr>
                          <th className="p-2">Station</th>
                          <th className="p-2">Timestamp (UTC)</th>
                          <th className="p-2 text-right">Temp (°C)</th>
                          <th className="p-2 text-right">Humidity (%)</th>
                          <th className="p-2 text-right">Pres (hPa)</th>
                          <th className="p-2 text-center">QC Verdict</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {uploadResult.preview.map((row, idx) => {
                          const isAnom = row.qc_verdict === 'anomalous';
                          const isSusp = row.qc_verdict === 'suspect';
                          const isDup = row.qc_verdict === 'duplicate_skipped';

                          return (
                            <tr
                              key={idx}
                              className={`hover:bg-surface/50 ${
                                isAnom ? 'bg-status-anomalous/5' : isSusp ? 'bg-amber-500/5' : ''
                              }`}
                            >
                              <td className="p-2 font-semibold text-ink flex items-center space-x-1">
                                <span>{row.station_code}</span>
                              </td>
                              <td className="p-2 text-muted text-[0.6875rem]">
                                {row.timestamp.replace('T', ' ').slice(0, 19)}
                              </td>
                              <td className="p-2 text-right text-ink">
                                {row.temperature !== null ? `${row.temperature}°C` : '—'}
                              </td>
                              <td className="p-2 text-right text-ink">
                                {row.humidity !== null ? `${row.humidity}%` : '—'}
                              </td>
                              <td className="p-2 text-right text-ink">
                                {row.pressure !== null ? `${row.pressure}` : '—'}
                              </td>
                              <td className="p-2 text-center">
                                <span
                                  className={`px-2 py-0.5 rounded text-[0.625rem] font-bold ${
                                    isAnom
                                      ? 'bg-status-anomalous text-white'
                                      : isSusp
                                      ? 'bg-amber-500 text-black'
                                      : isDup
                                      ? 'bg-surface text-muted border border-line'
                                      : 'bg-status-valid text-white'
                                  }`}
                                >
                                  {isDup
                                    ? 'DUPLICATE'
                                    : (row.qc_verdict || 'VALID').toUpperCase()}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Demo Test Presets Sidebar (Right col) */}
        <div className="space-y-4">
          <div className="bg-panel border border-line rounded-lg p-5 space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-ink font-sans">
                Quick-Test Meteorological Batches
              </h3>
              <p className="text-xs text-muted mt-1">
                One-click test datasets to demonstrate instant ingestion, duplicate handling, and
                anomaly detection without uploading external files.
              </p>
            </div>

            <div className="space-y-3">
              {PRESET_DATASETS.map((preset, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg border border-line bg-surface hover:border-accent/40 transition-colors space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-xs font-semibold text-ink font-sans">{preset.name}</h4>
                    <span className="text-[0.625rem] font-mono text-accent bg-accent/10 px-1.5 py-0.2 rounded border border-accent/20">
                      PRESET
                    </span>
                  </div>
                  <p className="text-[0.6875rem] text-muted font-sans leading-relaxed">
                    {preset.desc}
                  </p>
                  <button
                    disabled={!hasUploadClearance || uploading}
                    onClick={() => handleLoadPreset(preset)}
                    className="w-full flex items-center justify-center space-x-1.5 px-3 py-1.5 rounded bg-surface border border-line text-ink hover:bg-accent hover:text-white text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    <span>Load & Ingest This Batch</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* File Format Guidance Card */}
          <div className="bg-panel border border-line rounded-lg p-5 space-y-3 text-xs">
            <h4 className="font-semibold text-ink font-sans">Expected CSV Headers</h4>
            <div className="font-mono text-[0.6875rem] bg-surface p-2.5 rounded border border-line text-muted space-y-1">
              <div>station_code (e.g. NCR001)</div>
              <div>timestamp (ISO 8601 UTC)</div>
              <div>temperature (°C)</div>
              <div>humidity (%)</div>
              <div>pressure (hPa)</div>
              <div>wind_speed (m/s)</div>
              <div>rainfall (mm)</div>
              <div>solar_radiation (W/m²)</div>
            </div>
            <p className="text-[0.6875rem] text-muted">
              Auto-maps alternative column names (temp, rhum, pres, wspd, srad) from Meteostat and IMD archives.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
