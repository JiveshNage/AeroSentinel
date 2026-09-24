import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Wrench,
  AlertTriangle,
  ShieldAlert,
  CheckCircle2,
  RefreshCw,
  Search,
  ExternalLink,
  ClipboardList,
  Sparkles,
  Activity,
  Filter,
  Check,
  X,
  Gauge,
  Cpu,
} from 'lucide-react';
import {
  fetchMaintenancePredictions,
  recomputeMaintenancePredictions,
  FleetMaintenanceSummary,
  MaintenancePredictionResponse,
} from '../api/maintenance';

interface MaintenanceViewProps {
  onInspectStation?: (stationCode: string) => void;
}

export const MaintenanceView: React.FC<MaintenanceViewProps> = ({ onInspectStation }) => {
  const [summary, setSummary] = useState<FleetMaintenanceSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [recomputing, setRecomputing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Work order modal state
  const [selectedStationForDispatch, setSelectedStationForDispatch] = useState<MaintenancePredictionResponse | null>(null);
  const [dispatchedTicket, setDispatchedTicket] = useState<{ id: string; stationCode: string } | null>(null);

  const loadData = useCallback(async (filter?: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchMaintenancePredictions(filter || riskFilter);
      setSummary(data);
    } catch (err: any) {
      console.error('Error fetching maintenance predictions:', err);
      setError(err.message || 'Failed to load predictive maintenance rankings.');
    } finally {
      setLoading(false);
    }
  }, [riskFilter]);

  useEffect(() => {
    loadData(riskFilter);
  }, [riskFilter, loadData]);

  const handleRecompute = async () => {
    try {
      setRecomputing(true);
      setError(null);
      const data = await recomputeMaintenancePredictions();
      setSummary(data);
    } catch (err: any) {
      console.error('Error recomputing predictions:', err);
      setError(err.message || 'Failed to recompute fleet maintenance predictions.');
    } finally {
      setRecomputing(false);
    }
  };

  const filteredPredictions = useMemo(() => {
    if (!summary?.ranked_predictions) return [];
    let list = summary.ranked_predictions;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (p) =>
          p.station_code.toLowerCase().includes(q) ||
          p.station_name.toLowerCase().includes(q) ||
          p.district.toLowerCase().includes(q) ||
          p.state.toLowerCase().includes(q) ||
          p.top_driver.toLowerCase().includes(q)
      );
    }

    return list;
  }, [summary, searchQuery]);

  const getRiskBadge = (level: string) => {
    switch (level.toLowerCase()) {
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
            CRITICAL RISK
          </span>
        );
      case 'elevated':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            ELEVATED RISK
          </span>
        );
      case 'moderate':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/40">
            <Activity className="w-3.5 h-3.5 text-blue-400" />
            MODERATE RISK
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            NOMINAL
          </span>
        );
    }
  };

  const getProgressColor = (prob: number) => {
    if (prob >= 0.70) return 'bg-rose-500 shadow-rose-500/50';
    if (prob >= 0.40) return 'bg-amber-500 shadow-amber-500/50';
    if (prob >= 0.20) return 'bg-blue-500 shadow-blue-500/50';
    return 'bg-emerald-500 shadow-emerald-500/50';
  };

  return (
    <div className="space-y-6">
      {/* Header & Recompute Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/80 p-6 rounded-2xl border border-slate-800 shadow-xl backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-500/20 rounded-lg border border-indigo-500/30">
              <Wrench className="w-6 h-6 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                Predictive Maintenance & Fleet Risk Queue
                <span className="px-2 py-0.5 text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded-md">
                  30-Day Failure Horizon
                </span>
              </h1>
              <p className="text-sm text-slate-400 mt-0.5">
                Machine-learning failure probability ranking, component degradation attribution, and proactive field maintenance scheduling.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={handleRecompute}
          disabled={recomputing}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-medium text-sm text-white bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 transition-all duration-200 shadow-lg shadow-indigo-600/25 border border-indigo-400/20 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${recomputing ? 'animate-spin' : ''}`} />
          {recomputing ? 'Evaluating Fleet Manifolds...' : 'Run Fleet Risk Assessment'}
        </button>
      </div>

      {/* Error Alert Banner */}
      {error && (
        <div className="bg-rose-950/80 border border-rose-500/50 p-4 rounded-xl flex items-center justify-between text-rose-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
            <span className="text-sm">{error}</span>
          </div>
          <button onClick={() => setError(null)} className="p-1 hover:bg-rose-800/40 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Dispatched Work Order Toast Banner */}
      {dispatchedTicket && (
        <div className="bg-emerald-950/80 border border-emerald-500/50 p-4 rounded-xl flex items-center justify-between shadow-lg text-emerald-200 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <ClipboardList className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">
                IMD Maintenance Work Order Dispatched: #{dispatchedTicket.id}
              </p>
              <p className="text-xs text-emerald-300">
                Technician dispatched for Station {dispatchedTicket.stationCode}. Status logged to Fleet Maintenance Queue.
              </p>
            </div>
          </div>
          <button
            onClick={() => setDispatchedTicket(null)}
            className="p-1 hover:bg-emerald-800/40 rounded-lg transition-colors text-emerald-300 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Executive Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Stations */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Stations Monitored</span>
            <div className="p-2 rounded-lg bg-slate-800 text-slate-300">
              <Cpu className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold text-white mt-3 font-mono">
            {summary ? summary.total_stations : '—'}
          </p>
          <p className="text-xs text-slate-400 mt-1">Full operational AWS telemetry fleet</p>
        </div>

        {/* Critical Risk */}
        <div className="bg-slate-900/60 border border-rose-500/20 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-300 uppercase tracking-wider">Critical Risk (Dispatch)</span>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold text-rose-400 mt-3 font-mono">
            {summary ? summary.critical_risk_count : '—'}
          </p>
          <p className="text-xs text-rose-300/70 mt-1">P(failure) ≥ 70% in next 30 days</p>
        </div>

        {/* Elevated Risk */}
        <div className="bg-slate-900/60 border border-amber-500/20 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-300 uppercase tracking-wider">Elevated Risk</span>
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold text-amber-400 mt-3 font-mono">
            {summary ? summary.elevated_risk_count : '—'}
          </p>
          <p className="text-xs text-amber-300/70 mt-1">40% ≤ P(failure) &lt; 70%</p>
        </div>

        {/* Mean Risk */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Fleet Mean Failure Probability</span>
            <div className="p-2 rounded-lg bg-slate-800 text-cyan-400">
              <Gauge className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold text-cyan-300 mt-3 font-mono">
            {summary ? `${(summary.mean_failure_probability * 100).toFixed(1)}%` : '—'}
          </p>
          <p className="text-xs text-slate-400 mt-1">Fleet aggregate degradation index</p>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 bg-slate-900/40 p-4 rounded-xl border border-slate-800/60">
        {/* Risk Level Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-2 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> Risk Level:
          </span>
          {[
            { id: 'all', label: 'All Stations' },
            { id: 'critical', label: 'Critical' },
            { id: 'elevated', label: 'Elevated' },
            { id: 'moderate', label: 'Moderate' },
            { id: 'nominal', label: 'Nominal' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setRiskFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                riskFilter === tab.id
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'bg-slate-800/60 text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative min-w-[260px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search station, district, driver..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/60 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>
      </div>

      {/* Ranked Prediction List */}
      <div className="space-y-3">
        {loading ? (
          <div className="p-12 text-center text-slate-400 bg-slate-900/30 rounded-xl border border-slate-800/50">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto text-indigo-400 mb-3" />
            <p className="text-sm">Evaluating station degradation manifolds...</p>
          </div>
        ) : filteredPredictions.length === 0 ? (
          <div className="p-12 text-center text-slate-400 bg-slate-900/30 rounded-xl border border-slate-800/50">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
            <p className="text-sm font-medium text-white">No stations match the selected risk criteria.</p>
            <p className="text-xs text-slate-500 mt-1">Try selecting 'All Stations' or clearing search filters.</p>
          </div>
        ) : (
          filteredPredictions.map((pred, idx) => {
            const probPct = (pred.failure_probability_30d * 100).toFixed(1);
            return (
              <div
                key={pred.station_id}
                className="bg-slate-900/70 border border-slate-800/80 hover:border-slate-700/80 rounded-xl p-5 transition-all duration-200 shadow-md backdrop-blur-sm"
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  {/* Station Profile & Rank */}
                  <div className="flex items-start gap-3 min-w-[280px]">
                    <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-800 text-slate-300 font-mono text-xs font-bold border border-slate-700">
                      #{idx + 1}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-bold text-white tracking-wider">
                          {pred.station_code}
                        </span>
                        <span className="text-xs text-slate-400">•</span>
                        <span className="text-xs font-medium text-slate-300">{pred.station_name}</span>
                        {getRiskBadge(pred.risk_level)}
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {pred.district}, {pred.state}
                      </p>
                    </div>
                  </div>

                  {/* Failure Probability Progress Meter */}
                  <div className="flex-1 max-w-xs">
                    <div className="flex justify-between items-baseline mb-1">
                      <span className="text-xs font-medium text-slate-400">30-Day Failure Risk</span>
                      <span className="font-mono text-sm font-bold text-white">{probPct}%</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
                      <div
                        className={`h-2.5 rounded-full transition-all duration-500 shadow-sm ${getProgressColor(
                          pred.failure_probability_30d
                        )}`}
                        style={{ width: `${Math.max(5, pred.failure_probability_30d * 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* Top Contributing Factor */}
                  <div className="min-w-[240px]">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                      Primary Risk Driver
                    </span>
                    <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-300 bg-indigo-500/10 px-2.5 py-1 rounded-md border border-indigo-500/20">
                      <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                      {pred.top_driver}
                    </div>
                  </div>

                  {/* Technician Actions */}
                  <div className="flex items-center gap-2 justify-end">
                    {onInspectStation && (
                      <button
                        onClick={() => onInspectStation(pred.station_code)}
                        className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700"
                        title="Inspect Station Telemetry Stream"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => setSelectedStationForDispatch(pred)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-slate-800 hover:bg-indigo-600 transition-colors border border-slate-700 hover:border-indigo-500 shadow-sm"
                    >
                      <ClipboardList className="w-3.5 h-3.5" />
                      Dispatch Ticket
                    </button>
                  </div>
                </div>

                {/* Prescribed Action Footer */}
                <div className="mt-3 pt-3 border-t border-slate-800/60 flex flex-col sm:flex-row sm:items-center justify-between text-xs text-slate-400 gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-slate-300">Prescribed Maintenance:</span>
                    <span className="text-slate-300">{pred.recommended_action}</span>
                  </div>
                  <span className="text-slate-500 text-[11px] font-mono">
                    Evaluated: {new Date(pred.predicted_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Work Order Modal */}
      {selectedStationForDispatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center gap-2 text-white font-bold text-lg">
                <Wrench className="w-5 h-5 text-indigo-400" />
                Dispatch IMD Maintenance Ticket
              </div>
              <button
                onClick={() => setSelectedStationForDispatch(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800 space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">Target AWS Station:</span>
                  <span className="font-mono font-bold text-white">
                    {selectedStationForDispatch.station_code} ({selectedStationForDispatch.station_name})
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Location:</span>
                  <span className="text-slate-200">
                    {selectedStationForDispatch.district}, {selectedStationForDispatch.state}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Failure Risk Assessment:</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono font-bold text-rose-400">
                      {(selectedStationForDispatch.failure_probability_30d * 100).toFixed(1)}%
                    </span>
                    {getRiskBadge(selectedStationForDispatch.risk_level)}
                  </div>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Attributed Risk Driver:</span>
                  <span className="font-semibold text-indigo-300">
                    {selectedStationForDispatch.top_driver}
                  </span>
                </div>
              </div>

              <div>
                <span className="block font-semibold text-slate-300 mb-1">
                  Prescribed Field Technician Action:
                </span>
                <p className="bg-slate-950/80 p-3 rounded-lg border border-slate-800/80 text-slate-200 leading-relaxed">
                  {selectedStationForDispatch.recommended_action}
                </p>
              </div>

              <div>
                <span className="block font-semibold text-slate-300 mb-1">Technician Team:</span>
                <input
                  type="text"
                  defaultValue="Northern Region IMD Sensor Field Unit 04"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-white"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                onClick={() => setSelectedStationForDispatch(null)}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  const ticketId = `IMD-WO-${Math.floor(100000 + Math.random() * 900000)}`;
                  setDispatchedTicket({
                    id: ticketId,
                    stationCode: selectedStationForDispatch.station_code,
                  });
                  setSelectedStationForDispatch(null);
                }}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 transition-all shadow-md shadow-indigo-600/25"
              >
                <Check className="w-4 h-4" />
                Confirm & Dispatch Technician
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
