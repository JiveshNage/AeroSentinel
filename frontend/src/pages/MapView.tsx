import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Search,
  Wifi,
  WifiOff,
  Radio,
  SlidersHorizontal,
} from 'lucide-react';
import { StationSummary, fetchStations, StationHealthStatus } from '../api/stations';
import { StationMap } from '../components/StationMap';

interface MapViewProps {
  onInspectStation?: (stationId: string) => void;
}

export const MapView: React.FC<MapViewProps> = ({ onInspectStation }) => {
  const [stations, setStations] = useState<StationSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedState, setSelectedState] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [healthFilter, setHealthFilter] = useState<string>('ALL');
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null);

  // WebSocket Live Streaming State
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [latestAlertToast, setLatestAlertToast] = useState<{
    station_code: string;
    variable: string;
    message: string;
    time: string;
  } | null>(null);

  // Load stations from backend
  const loadStations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchStations();
      setStations(data.stations);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to connect to station registry';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStations();
  }, [loadStations]);

  // Connect to live alerts WebSocket (/api/alerts/ws)
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout>;

    const connectWs = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/alerts/ws`;

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.event === 'new_alert' && payload.alert) {
            const alertData = payload.alert;
            setLatestAlertToast({
              station_code: alertData.station_code,
              variable: alertData.variable,
              message: alertData.message,
              time: new Date().toLocaleTimeString(),
            });

            // Dynamically mark affected station as anomalous in real-time
            setStations((prev) =>
              prev.map((s) => {
                if (s.station_code === alertData.station_code || s.id === alertData.station_id) {
                  return {
                    ...s,
                    health_status: 'anomalous' as StationHealthStatus,
                    active_alerts_count: s.active_alerts_count + 1,
                    latest_fault_type: alertData.fault_type || s.latest_fault_type,
                  };
                }
                return s;
              })
            );

            // Auto-hide alert toast after 8 seconds
            setTimeout(() => {
              setLatestAlertToast(null);
            }, 8000);
          }
        } catch {
          // Non-JSON message (e.g. heartbeat ping/pong)
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        // Attempt reconnect after 5s
        reconnectTimeout = setTimeout(connectWs, 5000);
      };

      ws.onerror = () => {
        setWsConnected(false);
      };
    };

    connectWs();

    return () => {
      clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  // Compute states present in station data for filter dropdown
  const uniqueStates = useMemo(() => {
    const states = new Set(stations.map((s) => s.state));
    return Array.from(states).sort();
  }, [stations]);

  // Aggregate health status counters
  const stats = useMemo(() => {
    let healthy = 0;
    let suspect = 0;
    let anomalous = 0;
    let offline = 0;

    stations.forEach((s) => {
      if (s.health_status === 'healthy') healthy++;
      else if (s.health_status === 'suspect') suspect++;
      else if (s.health_status === 'anomalous') anomalous++;
      else offline++;
    });

    return { total: stations.length, healthy, suspect, anomalous, offline };
  }, [stations]);

  // Filter stations based on state, health filter, and text query
  const filteredStations = useMemo(() => {
    return stations.filter((st) => {
      const matchState = selectedState === 'ALL' || st.state === selectedState;
      const matchHealth = healthFilter === 'ALL' || st.health_status === healthFilter;
      const matchQuery =
        !searchQuery ||
        st.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        st.station_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        st.district.toLowerCase().includes(searchQuery.toLowerCase());

      return matchState && matchHealth && matchQuery;
    });
  }, [stations, selectedState, healthFilter, searchQuery]);

  return (
    <div className="space-y-5">
      {/* Top Health Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* Total Stations */}
        <div
          onClick={() => setHealthFilter('ALL')}
          className={`p-3.5 rounded border transition-all cursor-pointer ${
            healthFilter === 'ALL'
              ? 'bg-panel-raised border-accent shadow-sm'
              : 'bg-panel border-line hover:border-line/80'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[0.6875rem] font-mono text-muted uppercase tracking-wider">
              Total AWS
            </span>
            <Activity className="w-3.5 h-3.5 text-accent" />
          </div>
          <div className="mt-1 flex items-baseline space-x-2">
            <span className="text-[1.375rem] font-mono font-semibold text-ink font-mono-tabular">
              {stats.total}
            </span>
            <span className="text-[0.6875rem] text-muted font-mono">stations</span>
          </div>
        </div>

        {/* Healthy Stations */}
        <div
          onClick={() => setHealthFilter('healthy')}
          className={`p-3.5 rounded border transition-all cursor-pointer ${
            healthFilter === 'healthy'
              ? 'bg-panel-raised border-[#3FB876] shadow-sm'
              : 'bg-panel border-line hover:border-[#3FB876]/40'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[0.6875rem] font-mono text-muted uppercase tracking-wider">
              Healthy
            </span>
            <CheckCircle2 className="w-3.5 h-3.5 text-[#3FB876]" />
          </div>
          <div className="mt-1 flex items-baseline space-x-2">
            <span className="text-[1.375rem] font-mono font-semibold text-[#3FB876] font-mono-tabular">
              {stats.healthy}
            </span>
            <span className="text-[0.6875rem] text-muted font-mono">
              {stats.total ? `${Math.round((stats.healthy / stats.total) * 100)}%` : '0%'}
            </span>
          </div>
        </div>

        {/* Suspect Stations */}
        <div
          onClick={() => setHealthFilter('suspect')}
          className={`p-3.5 rounded border transition-all cursor-pointer ${
            healthFilter === 'suspect'
              ? 'bg-panel-raised border-[#E8B84D] shadow-sm'
              : 'bg-panel border-line hover:border-[#E8B84D]/40'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[0.6875rem] font-mono text-muted uppercase tracking-wider">
              Suspect
            </span>
            <AlertTriangle className="w-3.5 h-3.5 text-[#E8B84D]" />
          </div>
          <div className="mt-1 flex items-baseline space-x-2">
            <span className="text-[1.375rem] font-mono font-semibold text-[#E8B84D] font-mono-tabular">
              {stats.suspect}
            </span>
            <span className="text-[0.6875rem] text-muted font-mono">review</span>
          </div>
        </div>

        {/* Anomalous Stations */}
        <div
          onClick={() => setHealthFilter('anomalous')}
          className={`p-3.5 rounded border transition-all cursor-pointer ${
            healthFilter === 'anomalous'
              ? 'bg-panel-raised border-[#E0655C] shadow-sm'
              : 'bg-panel border-line hover:border-[#E0655C]/40'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[0.6875rem] font-mono text-muted uppercase tracking-wider">
              Anomalous
            </span>
            <Radio className="w-3.5 h-3.5 text-[#E0655C] animate-pulse" />
          </div>
          <div className="mt-1 flex items-baseline space-x-2">
            <span className="text-[1.375rem] font-mono font-semibold text-[#E0655C] font-mono-tabular">
              {stats.anomalous}
            </span>
            {stats.anomalous > 0 && (
              <span className="px-1.5 py-0.2 rounded text-[0.625rem] font-mono bg-[#E0655C]/20 text-[#E0655C] font-semibold">
                ALERT
              </span>
            )}
          </div>
        </div>

        {/* Offline Stations */}
        <div
          onClick={() => setHealthFilter('offline')}
          className={`p-3.5 rounded border transition-all cursor-pointer ${
            healthFilter === 'offline'
              ? 'bg-panel-raised border-[#6B747C] shadow-sm'
              : 'bg-panel border-line hover:border-[#6B747C]/40'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[0.6875rem] font-mono text-muted uppercase tracking-wider">
              Offline
            </span>
            <span className="w-2.5 h-2.5 rounded-full bg-[#6B747C]" />
          </div>
          <div className="mt-1 flex items-baseline space-x-2">
            <span className="text-[1.375rem] font-mono font-semibold text-muted font-mono-tabular">
              {stats.offline}
            </span>
            <span className="text-[0.6875rem] text-muted font-mono">no signal</span>
          </div>
        </div>
      </div>

      {/* Live Toast Notification Banner */}
      {latestAlertToast && (
        <div className="bg-[#E0655C]/15 border border-[#E0655C] rounded p-3 flex items-center justify-between animate-fadeIn shadow-lg">
          <div className="flex items-center space-x-3">
            <div className="w-2.5 h-2.5 rounded-full bg-[#E0655C] pulse-anomalous" />
            <div className="text-[0.8125rem]">
              <span className="font-mono font-semibold text-[#E0655C]">
                LIVE QC ANOMALY [{latestAlertToast.station_code} · {latestAlertToast.variable.toUpperCase()}]:
              </span>{' '}
              <span className="text-ink">{latestAlertToast.message}</span>
            </div>
          </div>
          <span className="text-[0.6875rem] font-mono text-muted">
            {latestAlertToast.time}
          </span>
        </div>
      )}

      {/* Filter & Action Toolbar */}
      <div className="bg-panel border border-line rounded p-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* State Filter */}
          <div className="flex items-center space-x-1.5 bg-surface border border-line rounded px-2.5 py-1.5 text-[0.8125rem]">
            <SlidersHorizontal className="w-3.5 h-3.5 text-muted" />
            <select
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              className="bg-transparent border-none text-ink text-[0.8125rem] focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Regions ({stations.length})</option>
              {uniqueStates.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>

          {/* Search Box */}
          <div className="relative flex items-center bg-surface border border-line rounded px-2.5 py-1.5 text-[0.8125rem] min-w-[220px]">
            <Search className="w-3.5 h-3.5 text-muted mr-1.5" />
            <input
              type="text"
              placeholder="Search station or code..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent border-none text-ink text-[0.8125rem] focus:outline-none w-full placeholder:text-muted/60"
            />
          </div>

          {healthFilter !== 'ALL' && (
            <button
              onClick={() => setHealthFilter('ALL')}
              className="px-2 py-1 rounded bg-surface border border-line text-[0.6875rem] font-mono text-muted hover:text-ink"
            >
              Clear filter: {healthFilter} ✕
            </button>
          )}
        </div>

        <div className="flex items-center space-x-3 text-[0.75rem] font-mono">
          {/* WebSocket Status Indicator */}
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-surface border border-line">
            {wsConnected ? (
              <>
                <Wifi className="w-3 h-3 text-[#3FB876]" />
                <span className="text-[#3FB876]">WS LIVE</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3 h-3 text-muted" />
                <span className="text-muted">CONNECTING</span>
              </>
            )}
          </div>

          {/* Refresh Button */}
          <button
            onClick={loadStations}
            disabled={loading}
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-surface border border-line text-ink hover:bg-panel-raised transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            <span>Reload</span>
          </button>
        </div>
      </div>

      {/* Main Geospatial Map Display */}
      {error ? (
        <div className="p-6 rounded border border-line bg-panel text-center space-y-3">
          <AlertTriangle className="w-8 h-8 text-[#E0655C] mx-auto" />
          <h4 className="text-ink font-medium">Failed to load station map</h4>
          <p className="text-[0.8125rem] text-muted max-w-md mx-auto">{error}</p>
          <button
            onClick={loadStations}
            className="px-3 py-1.5 rounded bg-accent text-white text-[0.8125rem]"
          >
            Retry Connection
          </button>
        </div>
      ) : (
        <StationMap
          stations={filteredStations}
          selectedStationId={selectedStationId}
          onSelectStation={(st) => setSelectedStationId(st.station_code)}
          onInspectStation={onInspectStation}
        />
      )}

      {/* Station List Table / Roster */}
      <div className="bg-panel border border-line rounded p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-[0.9375rem] font-semibold text-ink">
              Weather Station Fleet ({filteredStations.length})
            </h3>
            <p className="text-[0.75rem] text-muted">
              Live status from rule engine, IsolationForest scorer, and cross-station spatial consensus
            </p>
          </div>
          <span className="text-[0.6875rem] font-mono text-muted">
            Showing {filteredStations.length} of {stations.length}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[0.8125rem] font-sans">
            <thead className="text-[0.6875rem] font-mono uppercase text-muted border-b border-line bg-surface/50">
              <tr>
                <th className="py-2 px-3">Station</th>
                <th className="py-2 px-3">Region</th>
                <th className="py-2 px-3">Status</th>
                <th className="py-2 px-3">Temperature</th>
                <th className="py-2 px-3">Humidity</th>
                <th className="py-2 px-3">Pressure</th>
                <th className="py-2 px-3">QC Verdict</th>
                <th className="py-2 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line font-mono text-[0.75rem]">
              {filteredStations.map((st) => {
                const r = st.latest_reading;
                const isAnom = st.health_status === 'anomalous';
                const isHlth = st.health_status === 'healthy';
                const isSusp = st.health_status === 'suspect';

                return (
                  <tr
                    key={st.id}
                    className={`hover:bg-surface/60 transition-colors ${
                      isAnom ? 'bg-[#E0655C]/5' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-ink font-sans">{st.name}</div>
                      <div className="text-[0.6875rem] font-mono text-accent">{st.station_code}</div>
                    </td>
                    <td className="py-2.5 px-3 text-muted font-sans">
                      {st.district}, {st.state}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[0.6875rem] font-semibold ${
                          isHlth
                            ? 'bg-[#3FB876]/15 text-[#3FB876] border border-[#3FB876]/40'
                            : isSusp
                            ? 'bg-[#E8B84D]/15 text-[#E8B84D] border border-[#E8B84D]/40'
                            : isAnom
                            ? 'bg-[#E0655C]/20 text-[#E0655C] border border-[#E0655C]/60 pulse-anomalous'
                            : 'bg-muted/15 text-muted border border-line'
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        <span>{st.health_status.toUpperCase()}</span>
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-ink font-mono-tabular">
                      {r?.temperature != null ? `${r.temperature.toFixed(1)} °C` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-ink font-mono-tabular">
                      {r?.humidity != null ? `${r.humidity.toFixed(1)} %` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-ink font-mono-tabular">
                      {r?.pressure != null ? `${r.pressure.toFixed(1)} hPa` : '—'}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="text-muted">
                        {st.latest_verdict ? st.latest_verdict.toUpperCase() : 'NO DATA'}
                      </span>
                      {st.latest_fault_type && (
                        <span className="ml-1 text-[0.625rem] text-[#E0655C] font-semibold">
                          ({st.latest_fault_type})
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => onInspectStation?.(st.station_code)}
                        className="px-2 py-1 rounded bg-surface border border-line text-ink hover:bg-panel-raised text-[0.6875rem] transition-colors"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
