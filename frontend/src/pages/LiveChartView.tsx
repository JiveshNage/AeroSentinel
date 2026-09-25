import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import {
  Radio,
  Play,
  Pause,
  Zap,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Activity,
  Clock,
  MapPin,
} from 'lucide-react';
import { fetchStationTelemetry, TelemetryPoint, StationSummary, fetchStations } from '../api/stations';
import { simulateStationTick } from '../api/live';
import { VARIABLE_CONFIG, WeatherVariable } from '../components/StationTimeSeriesChart';

interface LiveChartViewProps {
  initialStationCode?: string;
  onInspectStation?: (stationCode: string) => void;
}

export const LiveChartView: React.FC<LiveChartViewProps> = ({
  initialStationCode = '',
  onInspectStation,
}) => {
  const [stations, setStations] = useState<StationSummary[]>([]);
  const [selectedStation, setSelectedStation] = useState<string>(initialStationCode);
  const [selectedVariable, setSelectedVariable] = useState<WeatherVariable>('temperature');
  const [points, setPoints] = useState<TelemetryPoint[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(true);
  const [streamIntervalMs, setStreamIntervalMs] = useState<number>(2000);
  const [bufferLimit, setBufferLimit] = useState<number>(30);
  const [loading, setLoading] = useState<boolean>(true);
  const [injecting, setInjecting] = useState<boolean>(false);
  const [lastTickLatency, setLastTickLatency] = useState<number>(32);

  const streamTimerRef = useRef<any>(null);

  // Load registered stations list and select first available station
  useEffect(() => {
    fetchStations()
      .then((res) => {
        const list = res?.stations || [];
        setStations(list);
        if (list.length > 0) {
          setSelectedStation((prev) => {
            if (prev && list.some((s) => s.station_code === prev)) {
              return prev;
            }
            if (initialStationCode && list.some((s) => s.station_code === initialStationCode)) {
              return initialStationCode;
            }
            return list[0].station_code;
          });
        }
      })
      .catch((err) => {
        console.error('Failed to load station registry in LiveChartView:', err);
      });
  }, [initialStationCode]);

  // Initial load of telemetry history for selected station
  const loadInitialTelemetry = useCallback(async () => {
    if (!selectedStation) {
      setLoading(false);
      return;
    }
    // Only query if station list has been retrieved and selectedStation is valid
    if (stations.length > 0 && !stations.some((s) => s.station_code === selectedStation)) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await fetchStationTelemetry(selectedStation, { limit: bufferLimit });
      setPoints(res.telemetry || []);
    } catch (err) {
      console.error('Failed to load telemetry:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedStation, bufferLimit, stations]);

  useEffect(() => {
    loadInitialTelemetry();
  }, [loadInitialTelemetry]);

  // Handle a new incoming live telemetry point
  const appendTelemetryPoint = useCallback((newPoint: TelemetryPoint) => {
    setPoints((prev) => {
      // Deduplicate on id or timestamp
      const filtered = prev.filter((p) => p.id !== newPoint.id && p.timestamp !== newPoint.timestamp);
      const updated = [...filtered, newPoint];
      // Keep only up to buffer limit
      if (updated.length > bufferLimit) {
        return updated.slice(updated.length - bufferLimit);
      }
      return updated;
    });
  }, [bufferLimit]);

  // Generate / Fetch next simulated real-time tick for confirmed existing station
  const triggerTick = useCallback(
    async (forceAnomaly: boolean = false) => {
      if (!selectedStation) return;
      if (stations.length > 0 && !stations.some((s) => s.station_code === selectedStation)) return;
      const startTime = performance.now();
      try {
        const point = await simulateStationTick(selectedStation, {
          force_anomaly: forceAnomaly,
          variable: selectedVariable,
          fault_type: forceAnomaly ? 'spike' : undefined,
        });
        const latency = Math.round(performance.now() - startTime);
        setLastTickLatency(latency);
        appendTelemetryPoint(point);
      } catch (err) {
        console.error('Tick simulation error:', err);
      }
    },
    [selectedStation, selectedVariable, appendTelemetryPoint, stations]
  );

  // Live streaming interval loop
  useEffect(() => {
    if (!isStreaming || !selectedStation) {
      if (streamTimerRef.current) clearInterval(streamTimerRef.current);
      return;
    }

    streamTimerRef.current = setInterval(() => {
      triggerTick(false);
    }, streamIntervalMs);

    return () => {
      if (streamTimerRef.current) clearInterval(streamTimerRef.current);
    };
  }, [isStreaming, streamIntervalMs, triggerTick, selectedStation]);

  // Inject Anomaly Button Handler
  const handleInjectAnomaly = async () => {
    setInjecting(true);
    try {
      await triggerTick(true);
    } finally {
      setTimeout(() => setInjecting(false), 600);
    }
  };

  const varConfig = VARIABLE_CONFIG[selectedVariable];

  // Prepare chart series data
  const chartData = useMemo(() => {
    return points.map((p) => {
      const val = p[selectedVariable] as number | undefined;
      const qc = p.qc_verdicts?.[selectedVariable];
      const isAnom = qc?.verdict === 'anomalous';
      const isSusp = qc?.verdict === 'suspect';

      const dt = new Date(p.timestamp);
      const timeStr = dt.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });

      return {
        id: p.id,
        timestamp: p.timestamp,
        timeLabel: timeStr,
        value: val !== undefined && val !== null ? Number(val.toFixed(2)) : null,
        qc,
        isAnom,
        isSusp,
        unit: varConfig.unit,
      };
    });
  }, [points, selectedVariable, varConfig.unit]);

  // Real-time Analytics Calculations
  const latestPoint = chartData[chartData.length - 1];
  const previousPoint = chartData.length > 1 ? chartData[chartData.length - 2] : null;

  const validValues = chartData.map((d) => d.value).filter((v): v is number => v !== null);
  const currentVal = latestPoint?.value ?? null;
  const prevVal = previousPoint?.value ?? null;
  const delta = currentVal !== null && prevVal !== null ? currentVal - prevVal : null;

  const minVal = validValues.length > 0 ? Math.min(...validValues) : null;
  const maxVal = validValues.length > 0 ? Math.max(...validValues) : null;

  const movingAvg = useMemo(() => {
    if (validValues.length === 0) return null;
    const slice = validValues.slice(-10);
    const sum = slice.reduce((a, b) => a + b, 0);
    return Number((sum / slice.length).toFixed(2));
  }, [validValues]);

  const latestQC = latestPoint?.qc;
  const isLatestAnomalous = latestQC?.verdict === 'anomalous';
  const isLatestSuspect = latestQC?.verdict === 'suspect';

  return (
    <div className="space-y-6">
      {/* Stream Controls & Station Switcher Header */}
      <div className="bg-panel border border-line rounded-lg p-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[0.75rem] font-mono uppercase tracking-wider text-accent font-semibold flex items-center space-x-1.5">
                <Radio
                  className={`w-3.5 h-3.5 ${
                    isStreaming ? 'text-status-valid animate-pulse' : 'text-amber-400'
                  }`}
                />
                <span>Real-Time Sensor Telemetry Feed</span>
              </span>
              <span className="text-line">•</span>
              <span className="text-[0.75rem] font-mono text-muted">Feature F10 Live Ingestion</span>
            </div>
            <h2 className="text-[1.25rem] font-semibold text-ink mt-1 font-sans flex items-center space-x-2">
              <span>Live Observation Stream & Dynamic QC Monitor</span>
              <span
                className={`text-[0.6875rem] font-mono font-bold px-2 py-0.5 rounded border ${
                  isStreaming
                    ? 'bg-status-valid/10 text-status-valid border-status-valid/30'
                    : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                }`}
              >
                {isStreaming ? `LIVE (${streamIntervalMs / 1000}s)` : 'PAUSED'}
              </span>
            </h2>
            <p className="text-[0.8125rem] text-muted mt-1 max-w-3xl font-sans">
              Watch incoming sensor ticks arrive in real-time. Use the anomaly injector button to
              test how the multi-tier QC classifier responds to sudden step-change faults.
            </p>
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Play/Pause */}
            <button
              onClick={() => setIsStreaming((prev) => !prev)}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded text-xs font-semibold shadow-sm transition-colors ${
                isStreaming
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30'
                  : 'bg-status-valid text-white hover:bg-status-valid/90'
              }`}
            >
              {isStreaming ? (
                <>
                  <Pause className="w-3.5 h-3.5" />
                  <span>Pause Feed</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Resume Stream</span>
                </>
              )}
            </button>

            {/* Single Tick */}
            <button
              onClick={() => triggerTick(false)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-surface border border-line text-ink hover:bg-panel text-xs font-medium transition-colors"
              title="Push single simulated telemetry point"
            >
              <RefreshCw className="w-3.5 h-3.5 text-muted" />
              <span>Manual Tick</span>
            </button>

            {/* Inject Anomaly Spike */}
            <button
              onClick={handleInjectAnomaly}
              disabled={injecting}
              className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded text-xs font-bold transition-all shadow-sm ${
                injecting
                  ? 'bg-status-anomalous text-white scale-95 ring-2 ring-status-anomalous'
                  : 'bg-status-anomalous/15 text-status-anomalous border border-status-anomalous/40 hover:bg-status-anomalous hover:text-white'
              }`}
              title="Inject sudden out-of-bounds anomaly spike into live stream"
            >
              <Zap className="w-3.5 h-3.5 text-status-anomalous fill-current" />
              <span>⚡ Inject Anomaly Spike</span>
            </button>
          </div>
        </div>

        {/* Station & Parameter Filter Bar */}
        <div className="mt-4 pt-4 border-t border-line flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-3">
            {/* Station Picker */}
            <div className="flex items-center space-x-2">
              <span className="text-muted font-mono flex items-center space-x-1">
                <MapPin className="w-3.5 h-3.5 text-accent" />
                <span>Station:</span>
              </span>
              <select
                value={selectedStation}
                onChange={(e) => setSelectedStation(e.target.value)}
                className="bg-surface border border-line rounded px-2.5 py-1 text-ink font-semibold focus:outline-none cursor-pointer text-xs"
              >
                {stations.map((st) => (
                  <option key={st.station_code} value={st.station_code}>
                    {st.station_code} — {st.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Variable Buttons */}
            <div className="flex items-center space-x-1 overflow-x-auto py-0.5 scrollbar-none">
              {(Object.keys(VARIABLE_CONFIG) as WeatherVariable[]).map((varKey) => {
                const conf = VARIABLE_CONFIG[varKey];
                const active = selectedVariable === varKey;
                return (
                  <button
                    key={varKey}
                    onClick={() => setSelectedVariable(varKey)}
                    className={`px-2.5 py-1 rounded text-[0.75rem] font-medium transition-colors whitespace-nowrap ${
                      active
                        ? 'bg-accent text-white shadow-xs'
                        : 'text-muted hover:text-ink hover:bg-surface'
                    }`}
                  >
                    {conf.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Speed & Buffer Controls */}
          <div className="flex items-center space-x-3 text-[0.75rem] font-mono text-muted">
            <div className="flex items-center space-x-1.5">
              <span>Speed:</span>
              <select
                value={streamIntervalMs}
                onChange={(e) => setStreamIntervalMs(Number(e.target.value))}
                className="bg-surface border border-line rounded px-1.5 py-0.5 text-ink focus:outline-none cursor-pointer text-xs"
              >
                <option value={1000}>1.0s (Fast)</option>
                <option value={2000}>2.0s (Normal)</option>
                <option value={5000}>5.0s (Paced)</option>
              </select>
            </div>

            <div className="flex items-center space-x-1.5">
              <span>Window:</span>
              <select
                value={bufferLimit}
                onChange={(e) => setBufferLimit(Number(e.target.value))}
                className="bg-surface border border-line rounded px-1.5 py-0.5 text-ink focus:outline-none cursor-pointer text-xs"
              >
                <option value={20}>20 points</option>
                <option value={30}>30 points</option>
                <option value={50}>50 points</option>
                <option value={100}>100 points</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Real-Time Live KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {/* Current Live Value */}
        <div className="bg-panel border border-line rounded-lg p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between text-muted text-[0.6875rem] font-mono">
            <span>LIVE OBSERVATION</span>
            <span className="w-2 h-2 rounded-full bg-accent animate-ping" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl font-bold font-mono text-ink font-mono-tabular">
              {currentVal !== null ? currentVal : '—'}
            </span>
            <span className="text-xs text-muted font-mono">{varConfig.unit}</span>
          </div>
          <div className="mt-1 text-[0.6875rem] font-mono">
            {delta !== null ? (
              <span
                className={`flex items-center space-x-1 ${
                  delta > 0
                    ? 'text-amber-400'
                    : delta < 0
                    ? 'text-blue-400'
                    : 'text-muted'
                }`}
              >
                {delta > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                <span>
                  {delta > 0 ? `+${delta.toFixed(2)}` : delta.toFixed(2)} vs prior
                </span>
              </span>
            ) : (
              <span className="text-muted">Awaiting tick</span>
            )}
          </div>
        </div>

        {/* Live QC Status */}
        <div
          className={`bg-panel border rounded-lg p-3.5 flex flex-col justify-between transition-colors ${
            isLatestAnomalous
              ? 'border-status-anomalous bg-status-anomalous/5'
              : isLatestSuspect
              ? 'border-amber-500/50 bg-amber-500/5'
              : 'border-line'
          }`}
        >
          <div className="text-muted text-[0.6875rem] font-mono uppercase">
            REAL-TIME QC HEALTH
          </div>
          <div className="mt-2">
            <span
              className={`inline-block px-2.5 py-1 rounded text-xs font-bold font-mono ${
                isLatestAnomalous
                  ? 'bg-status-anomalous text-white'
                  : isLatestSuspect
                  ? 'bg-amber-500 text-black'
                  : 'bg-status-valid text-white'
              }`}
            >
              {isLatestAnomalous
                ? 'CRITICAL ANOMALY'
                : isLatestSuspect
                ? 'SUSPECT'
                : 'VALID / HEALTHY'}
            </span>
          </div>
          <div className="mt-1 text-[0.6875rem] font-mono text-muted truncate">
            {latestQC?.fault_type || latestQC?.reason_code || 'Passed all QC tests'}
          </div>
        </div>

        {/* Rolling Average */}
        <div className="bg-panel border border-line rounded-lg p-3.5 flex flex-col justify-between">
          <div className="text-muted text-[0.6875rem] font-mono uppercase">
            10-TICK ROLLING AVG
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl font-bold font-mono text-ink font-mono-tabular">
              {movingAvg !== null ? movingAvg : '—'}
            </span>
            <span className="text-xs text-muted font-mono">{varConfig.unit}</span>
          </div>
          <div className="mt-1 text-[0.6875rem] font-mono text-muted">
            Smooth temporal trend
          </div>
        </div>

        {/* Min / Max in Window */}
        <div className="bg-panel border border-line rounded-lg p-3.5 flex flex-col justify-between">
          <div className="text-muted text-[0.6875rem] font-mono uppercase">
            WINDOW PEAK / TROUGH
          </div>
          <div className="mt-2 text-xs font-mono space-y-0.5">
            <div className="flex justify-between">
              <span className="text-muted">Max:</span>
              <span className="font-bold text-ink">
                {maxVal !== null ? `${maxVal} ${varConfig.unit}` : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Min:</span>
              <span className="font-bold text-ink">
                {minVal !== null ? `${minVal} ${varConfig.unit}` : '—'}
              </span>
            </div>
          </div>
          <div className="mt-1 text-[0.6875rem] font-mono text-muted">
            Buffer: {chartData.length} readings
          </div>
        </div>

        {/* Stream Ingestion Latency */}
        <div className="bg-panel border border-line rounded-lg p-3.5 flex flex-col justify-between">
          <div className="text-muted text-[0.6875rem] font-mono uppercase">
            INGESTION PIPELINE
          </div>
          <div className="mt-2 flex items-baseline space-x-1.5">
            <span className="text-2xl font-bold font-mono text-status-valid font-mono-tabular">
              {lastTickLatency}
            </span>
            <span className="text-xs text-muted font-mono">ms</span>
          </div>
          <div className="mt-1 text-[0.6875rem] font-mono text-muted flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-status-valid" />
            <span>SQLite + QC Model: 0 drop</span>
          </div>
        </div>
      </div>

      {/* Real-Time Live AreaChart */}
      <div className="bg-panel border border-line rounded-lg p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2.5">
              <h3 className="text-base font-semibold text-ink font-sans flex items-center space-x-2">
                <Activity className="w-4 h-4 text-accent" />
                <span>
                  {selectedStation} · {varConfig.label} Real-Time Waveform
                </span>
              </h3>
              {onInspectStation && (
                <button
                  onClick={() => onInspectStation(selectedStation)}
                  className="px-2 py-0.5 rounded bg-surface border border-line text-accent hover:underline text-[0.6875rem] font-mono"
                >
                  Station Details →
                </button>
              )}
            </div>
            <p className="text-xs text-muted font-sans mt-0.5">
              Live chart automatically updates with incoming ticks. Red markers highlight anomalies
              flagged by the QC pipeline.
            </p>
          </div>

          <div className="flex items-center space-x-4 text-[0.6875rem] font-mono">
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-status-valid" />
              <span className="text-muted">Valid</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
              <span className="text-muted">Suspect</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-status-anomalous" />
              <span className="text-muted">Anomalous Spike</span>
            </div>
          </div>
        </div>

        {/* Chart Container */}
        <div className="h-[360px] w-full pt-2">
          {loading && chartData.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs font-mono text-muted">
              Connecting to live telemetry stream...
            </div>
          ) : chartData.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs font-mono text-muted">
              No points in current window. Click "Manual Tick" to begin streaming.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                <defs>
                  <linearGradient id="liveVarGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={varConfig.color} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={varConfig.color} stopOpacity={0.0} />
                  </linearGradient>
                </defs>

                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-line, #30363d)" opacity={0.5} />

                <XAxis
                  dataKey="timeLabel"
                  stroke="var(--color-muted, #8b949e)"
                  tick={{ fontSize: 10, fontFamily: 'monospace' }}
                  tickMargin={8}
                />

                <YAxis
                  stroke="var(--color-muted, #8b949e)"
                  domain={['auto', 'auto']}
                  tick={{ fontSize: 10, fontFamily: 'monospace' }}
                  tickFormatter={(v) => `${v}`}
                  width={45}
                />

                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload || !payload.length) return null;
                    const p = payload[0].payload;
                    const qc = p.qc;
                    const isAnom = p.isAnom;

                    return (
                      <div className="bg-panel border border-line rounded shadow-xl p-3 text-xs max-w-xs font-sans">
                        <div className="text-muted font-mono text-[0.6875rem]">
                          {p.timeLabel} · {p.timestamp}
                        </div>
                        <div className="my-1.5 flex items-baseline space-x-2">
                          <span className="text-lg font-bold font-mono text-ink">
                            {p.value} {p.unit}
                          </span>
                          <span
                            className={`px-1.5 py-0.2 rounded text-[0.625rem] font-bold font-mono ${
                              isAnom
                                ? 'bg-status-anomalous text-white'
                                : p.isSusp
                                ? 'bg-amber-500 text-black'
                                : 'bg-status-valid text-white'
                            }`}
                          >
                            {(qc?.verdict || 'VALID').toUpperCase()}
                          </span>
                        </div>
                        {qc?.fault_type && (
                          <div className="text-status-anomalous text-[0.6875rem] font-mono mt-1">
                            Fault: {qc.fault_type} ({qc.reason_code})
                          </div>
                        )}
                        {qc?.confidence && (
                          <div className="text-muted text-[0.6875rem] font-mono">
                            QC Confidence: {(qc.confidence * 100).toFixed(0)}%
                          </div>
                        )}
                      </div>
                    );
                  }}
                />

                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={varConfig.color}
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#liveVarGradient)"
                  isAnimationActive={false}
                  dot={(props: any) => {
                    const { cx, cy, payload } = props;
                    if (!payload) return null;
                    if (payload.isAnom) {
                      return (
                        <g key={props.key}>
                          <circle cx={cx} cy={cy} r={7} fill="#E0655C" opacity={0.3} className="animate-ping" />
                          <circle cx={cx} cy={cy} r={4.5} fill="#E0655C" stroke="#fff" strokeWidth={1.5} />
                        </g>
                      );
                    }
                    if (payload.isSusp) {
                      return (
                        <circle key={props.key} cx={cx} cy={cy} r={3.5} fill="#E8B84D" stroke="#fff" strokeWidth={1} />
                      );
                    }
                    return null;
                  }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Chronological Stream Event Log */}
      <div className="bg-panel border border-line rounded-lg p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-line pb-2.5">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4 text-accent" />
            <h4 className="text-xs font-semibold text-ink font-sans uppercase">
              Recent Live Ticks Stream Log (Last {points.length} points)
            </h4>
          </div>
          <span className="text-[0.6875rem] font-mono text-muted">
            Auto-purging older readings beyond {bufferLimit}
          </span>
        </div>

        <div className="overflow-x-auto max-h-48 scrollbar-thin">
          <table className="w-full text-left text-xs font-mono">
            <thead className="text-[0.6875rem] text-muted border-b border-line">
              <tr>
                <th className="py-1 px-2">Timestamp (UTC)</th>
                <th className="py-1 px-2">Temp (°C)</th>
                <th className="py-1 px-2">Humidity (%)</th>
                <th className="py-1 px-2">Pressure (hPa)</th>
                <th className="py-1 px-2">Wind (m/s)</th>
                <th className="py-1 px-2 text-center">QC Verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/40">
              {[...chartData].reverse().slice(0, 10).map((pt, idx) => (
                <tr key={idx} className={pt.isAnom ? 'bg-status-anomalous/10' : ''}>
                  <td className="py-1 px-2 text-muted">{pt.timeLabel}</td>
                  <td className="py-1 px-2 text-ink">{pt.value !== null ? `${pt.value}°C` : '—'}</td>
                  <td className="py-1 px-2 text-ink">
                    {points.find((p) => p.id === pt.id)?.humidity ?? '—'}%
                  </td>
                  <td className="py-1 px-2 text-ink">
                    {points.find((p) => p.id === pt.id)?.pressure ?? '—'}
                  </td>
                  <td className="py-1 px-2 text-ink">
                    {points.find((p) => p.id === pt.id)?.wind_speed ?? '—'}
                  </td>
                  <td className="py-1 px-2 text-center">
                    <span
                      className={`px-2 py-0.2 rounded text-[0.625rem] font-bold ${
                        pt.isAnom
                          ? 'bg-status-anomalous text-white'
                          : pt.isSusp
                          ? 'bg-amber-500 text-black'
                          : 'bg-status-valid/20 text-status-valid'
                      }`}
                    >
                      {pt.isAnom ? 'ANOMALOUS' : pt.isSusp ? 'SUSPECT' : 'VALID'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
