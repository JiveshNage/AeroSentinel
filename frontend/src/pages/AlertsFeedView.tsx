import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  Search,
  Radio,
  ExternalLink,
  MessageSquare,
  Check,
  ShieldAlert,
  History,
  Send,
  Database,
  Info,
  Cpu,
  RotateCcw,
  Sparkles,
  Layers,
} from 'lucide-react';
import {
  AlertItem,
  FeedbackItem,
  fetchAlerts,
  updateAlertStatus,
  submitAlertFeedback,
  fetchFeedbackList,
} from '../api/alerts';
import { subscribeToAlerts } from '../api/realtime';
import { wsUrl } from '../api/client';


import {
  fetchRetrainStats,
  triggerRetraining,
  fetchRegisteredModels,
  activateModelVersion,
  ModelRegistryItem,
  RetrainResponse,
  FeedbackPoolStats,
} from '../api/retrain';

interface AlertsFeedViewProps {
  onInspectStation?: (stationCode: string) => void;
}

export const AlertsFeedView: React.FC<AlertsFeedViewProps> = ({ onInspectStation }) => {
  // Main view tab: 'feed' or 'audit'
  const [activeSubTab, setActiveSubTab] = useState<'feed' | 'audit'>('feed');

  // Alerts data
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState<boolean>(true);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // WebSocket connection state
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [newAlertCount, setNewAlertCount] = useState<number>(0);

  // Feedback form state per alert ID
  const [feedbackDrafts, setFeedbackDrafts] = useState<
    Record<number, { label: 'confirmed_fault' | 'false_alarm' | 'unsure'; notes: string; email: string }>
  >({});
  const [submittingFeedbackId, setSubmittingFeedbackId] = useState<number | null>(null);
  const [feedbackSuccessMsg, setFeedbackSuccessMsg] = useState<{ alertId: number; text: string } | null>(null);

  // Retraining & Model Registry State
  const [feedbackList, setFeedbackList] = useState<FeedbackItem[]>([]);
  const [loadingFeedback, setLoadingFeedback] = useState<boolean>(false);
  const [feedbackFilterLabel, setFeedbackFilterLabel] = useState<string>('ALL');
  const [retrainStats, setRetrainStats] = useState<FeedbackPoolStats | null>(null);
  const [registeredModels, setRegisteredModels] = useState<ModelRegistryItem[]>([]);
  const [retrainingInProgress, setRetrainingInProgress] = useState<boolean>(false);
  const [latestRetrainResult, setLatestRetrainResult] = useState<RetrainResponse | null>(null);
  const [activatingModelId, setActivatingModelId] = useState<number | null>(null);

  // Load alerts from backend
  const loadAlerts = useCallback(async () => {
    setLoadingAlerts(true);
    setAlertsError(null);
    try {
      const data = await fetchAlerts({ limit: 100 });
      setAlerts(data.alerts);
      setNewAlertCount(0);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load operational alerts';
      setAlertsError(msg);
    } finally {
      setLoadingAlerts(false);
    }
  }, []);

  // Load retrain console data
  const loadRetrainConsole = useCallback(async () => {
    setLoadingFeedback(true);
    try {
      const [statsData, modelsData, feedbackData] = await Promise.all([
        fetchRetrainStats('temperature'),
        fetchRegisteredModels('temperature'),
        fetchFeedbackList({
          limit: 100,
          label: feedbackFilterLabel !== 'ALL' ? feedbackFilterLabel : undefined,
        }),
      ]);
      setRetrainStats(statsData);
      setRegisteredModels(modelsData.models);
      setFeedbackList(feedbackData.feedback);
    } catch (err: unknown) {
      console.error('Failed to load retrain console data:', err);
    } finally {
      setLoadingFeedback(false);
    }
  }, [feedbackFilterLabel]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  useEffect(() => {
    if (activeSubTab === 'audit') {
      loadRetrainConsole();
    }
  }, [activeSubTab, loadRetrainConsole]);

  // Handle triggering retraining
  const handleTriggerRetrain = async () => {
    setRetrainingInProgress(true);
    try {
      const result = await triggerRetraining({ variable: 'temperature' });
      setLatestRetrainResult(result);
      await loadRetrainConsole();
    } catch (err: unknown) {
      alert(`Retraining failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRetrainingInProgress(false);
    }
  };

  // Handle activating model version
  const handleActivateModel = async (modelId: number) => {
    setActivatingModelId(modelId);
    try {
      await activateModelVersion(modelId);
      await loadRetrainConsole();
    } catch (err: unknown) {
      alert(`Model activation failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setActivatingModelId(null);
    }
  };

  // Connect to live WebSocket stream
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      ws = new WebSocket(wsUrl('/api/alerts/ws'));

      ws.onopen = () => {

        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.event === 'new_alert' && payload.alert) {
            const incoming: AlertItem = {
              id: payload.alert.id,
              station_id: payload.alert.station_id,
              station_code: payload.alert.station_code,
              station_name: payload.alert.station_name,
              variable: payload.alert.variable,
              severity: payload.alert.severity,
              status: payload.alert.status,
              message: payload.alert.message,
              channel_sent: { websocket: true },
              created_at: payload.alert.created_at,
              feedback_label: null,
            };

            setAlerts((prev) => {
              // Deduplicate if already present
              const exists = prev.find((a) => a.id === incoming.id);
              if (exists) {
                return prev.map((a) => (a.id === incoming.id ? { ...a, ...incoming } : a));
              }
              return [incoming, ...prev];
            });
            setNewAlertCount((cnt) => cnt + 1);
          }
        } catch (e) {
          console.error('Error parsing live alert:', e);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        setWsConnected(false);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  // Supabase Realtime alerts subscription (database-level CDC synchronization)
  useEffect(() => {
    const unsubscribe = subscribeToAlerts({
      onInsert: (row) => {
        if (!row || !row.id) return;
        const incoming: AlertItem = {
          id: row.id,
          station_id: row.station_id || '',
          station_code: row.station_code || 'NCR001',
          station_name: row.station_name || 'Station',
          variable: row.variable || 'atmospheric',
          severity: row.severity || 'medium',
          status: row.status || (row.acknowledged ? 'acknowledged' : 'open'),
          message: row.message || row.title || 'Live Anomaly Alert',
          channel_sent: { supabase_realtime: true },
          created_at: row.created_at || new Date().toISOString(),
          feedback_label: null,
        };
        setAlerts((prev) => {
          const exists = prev.find((a) => a.id === incoming.id);
          if (exists) {
            return prev.map((a) => (a.id === incoming.id ? { ...a, ...incoming } : a));
          }
          return [incoming, ...prev];
        });
        setNewAlertCount((cnt) => cnt + 1);
      },
      onUpdate: (row) => {
        if (!row || !row.id) return;
        setAlerts((prev) =>
          prev.map((a) =>
            a.id === row.id
              ? {
                  ...a,
                  status: row.status || (row.acknowledged ? 'acknowledged' : a.status),
                  severity: row.severity || a.severity,
                }
              : a
          )
        );
      },
    });
    return () => {
      unsubscribe();
    };
  }, []);

  // Filtered alerts list
  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      if (severityFilter !== 'ALL' && alert.severity !== severityFilter.toLowerCase()) {
        return false;
      }
      if (statusFilter !== 'ALL' && alert.status !== statusFilter.toLowerCase()) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const matchesCode = alert.station_code.toLowerCase().includes(query);
        const matchesName = alert.station_name.toLowerCase().includes(query);
        const matchesVar = alert.variable.toLowerCase().includes(query);
        const matchesMsg = alert.message.toLowerCase().includes(query);
        if (!matchesCode && !matchesName && !matchesVar && !matchesMsg) {
          return false;
        }
      }
      return true;
    });
  }, [alerts, severityFilter, statusFilter, searchQuery]);

  // Counts for summary tiles
  const metrics = useMemo(() => {
    const total = alerts.length;
    const open = alerts.filter((a) => a.status === 'open').length;
    const critical = alerts.filter((a) => a.severity === 'critical').length;
    const feedbackGiven = alerts.filter((a) => a.feedback_label !== null && a.feedback_label !== undefined).length;
    return { total, open, critical, feedbackGiven };
  }, [alerts]);

  // Handle status update (Acknowledge / Resolve)
  const handleUpdateStatus = async (alertId: number, newStatus: 'acknowledged' | 'resolved') => {
    try {
      const updated = await updateAlertStatus(alertId, newStatus);
      setAlerts((prev) => prev.map((a) => (a.id === alertId ? { ...a, status: updated.status, resolved_at: updated.resolved_at } : a)));
    } catch (err: unknown) {
      alert(`Error updating alert status: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  // Handle Feedback Submission
  const handleSubmitFeedback = async (alertId: number) => {
    const draft = feedbackDrafts[alertId] || {
      label: 'confirmed_fault',
      notes: '',
      email: 'operator@aerosentinel.gov.in',
    };

    setSubmittingFeedbackId(alertId);
    try {
      const res = await submitAlertFeedback(alertId, {
        label: draft.label,
        notes: draft.notes.trim() || undefined,
        user_email: draft.email.trim() || 'operator@aerosentinel.gov.in',
      });

      // Update in alerts list
      setAlerts((prev) =>
        prev.map((a) => {
          if (a.id === alertId) {
            return {
              ...a,
              feedback_label: res.label,
              status: res.label === 'false_alarm' ? 'resolved' : a.status === 'open' ? 'acknowledged' : a.status,
            };
          }
          return a;
        })
      );

      setFeedbackSuccessMsg({
        alertId,
        text: `Feedback captured: ${res.label.replace('_', ' ').toUpperCase()} recorded for model retraining!`,
      });

      setTimeout(() => {
        setFeedbackSuccessMsg((curr) => (curr?.alertId === alertId ? null : curr));
      }, 4000);
    } catch (err: unknown) {
      alert(`Feedback submission failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSubmittingFeedbackId(null);
    }
  };

  // Helper for Severity Badge styling
  const renderSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded text-[0.6875rem] font-mono font-semibold uppercase tracking-wider bg-status-anomalous/15 text-status-anomalous border border-status-anomalous/30">
            <AlertOctagon className="w-3 h-3 mr-1" />
            CRITICAL
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded text-[0.6875rem] font-mono font-semibold uppercase tracking-wider bg-amber-500/15 text-amber-500 border border-amber-500/30">
            <AlertTriangle className="w-3 h-3 mr-1" />
            HIGH
          </span>
        );
      case 'medium':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded text-[0.6875rem] font-mono font-medium uppercase tracking-wider bg-yellow-500/15 text-yellow-600 dark:text-yellow-400 border border-yellow-500/30">
            MEDIUM
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded text-[0.6875rem] font-mono font-medium uppercase tracking-wider bg-blue-500/15 text-blue-500 border border-blue-500/30">
            LOW
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Metrics Bar */}
      <div className="bg-panel border border-line rounded p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[0.75rem] font-mono uppercase tracking-wider text-accent font-semibold">
                Phase 3 Operator Product
              </span>
              <span className="text-line">•</span>
              <span className="text-[0.75rem] font-mono text-muted">Feature F13 (Alerts Feed & Feedback)</span>
            </div>
            <h2 className="text-[1.25rem] font-semibold text-ink mt-1 font-sans flex items-center space-x-2">
              <ShieldAlert className="w-5 h-5 text-accent" />
              <span>Operational Alerts Feed & Operator Feedback</span>
            </h2>
            <p className="text-[0.875rem] text-muted mt-1 max-w-3xl font-sans">
              Real-time anomaly stream with operator-in-the-loop ground-truth labeling. Feedback dynamically resolves alerts and logs verified datasets for continuous model retraining.
            </p>
          </div>

          {/* Real-time Status Badge */}
          <div className="flex items-center space-x-3">
            <div
              className={`flex items-center space-x-2 px-3 py-1.5 rounded border text-[0.8125rem] font-mono ${
                wsConnected
                  ? 'border-status-valid/40 bg-status-valid/10 text-status-valid'
                  : 'border-status-anomalous/40 bg-status-anomalous/10 text-status-anomalous'
              }`}
            >
              <Radio className={`w-3.5 h-3.5 ${wsConnected ? 'animate-pulse' : ''}`} />
              <span>{wsConnected ? 'STREAM LIVE' : 'RECONNECTING'}</span>
            </div>

            <button
              onClick={activeSubTab === 'feed' ? loadAlerts : loadRetrainConsole}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded border border-line bg-surface hover:bg-panel text-ink text-[0.8125rem] font-sans transition-colors"
              title="Refresh dataset"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Operational Metrics Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5 pt-4 border-t border-line">
          <div className="p-3 bg-surface border border-line rounded">
            <span className="text-[0.75rem] font-mono text-muted uppercase">Total Alerts</span>
            <div className="text-[1.375rem] font-mono font-semibold text-ink mt-0.5">
              {metrics.total}
            </div>
          </div>
          <div className="p-3 bg-surface border border-line rounded">
            <span className="text-[0.75rem] font-mono text-status-anomalous uppercase">Active / Open</span>
            <div className="text-[1.375rem] font-mono font-semibold text-status-anomalous mt-0.5">
              {metrics.open}
            </div>
          </div>
          <div className="p-3 bg-surface border border-line rounded">
            <span className="text-[0.75rem] font-mono text-amber-500 uppercase">Critical Severity</span>
            <div className="text-[1.375rem] font-mono font-semibold text-amber-500 mt-0.5">
              {metrics.critical}
            </div>
          </div>
          <div className="p-3 bg-surface border border-line rounded">
            <span className="text-[0.75rem] font-mono text-status-valid uppercase">Ground Truth Captured</span>
            <div className="text-[1.375rem] font-mono font-semibold text-status-valid mt-0.5">
              {metrics.feedbackGiven}
            </div>
          </div>
        </div>
      </div>

      {/* Sub-tab Navigation */}
      <div className="flex items-center space-x-2 border-b border-line pb-2">
        <button
          onClick={() => setActiveSubTab('feed')}
          className={`flex items-center space-x-2 px-4 py-2 rounded text-[0.875rem] font-medium transition-colors ${
            activeSubTab === 'feed'
              ? 'bg-accent text-white shadow-sm'
              : 'text-muted hover:text-ink hover:bg-panel'
          }`}
        >
          <ShieldAlert className="w-4 h-4" />
          <span>Operational Feed</span>
          {newAlertCount > 0 && (
            <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-[0.6875rem] font-mono bg-status-anomalous text-white">
              +{newAlertCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveSubTab('audit')}
          className={`flex items-center space-x-2 px-4 py-2 rounded text-[0.875rem] font-medium transition-colors ${
            activeSubTab === 'audit'
              ? 'bg-accent text-white shadow-sm'
              : 'text-muted hover:text-ink hover:bg-panel'
          }`}
        >
          <History className="w-4 h-4" />
          <span>Retraining Feedback Audit Log</span>
          <span className="text-[0.75rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded ml-1">
            F14 Ready
          </span>
        </button>
      </div>

      {/* SUBTAB 1: OPERATIONAL FEED */}
      {activeSubTab === 'feed' && (
        <div className="space-y-4">
          {/* Filter Controls */}
          <div className="bg-panel border border-line rounded p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[0.75rem] font-mono text-muted uppercase mr-1">Severity:</span>
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
                <button
                  key={s}
                  onClick={() => setSeverityFilter(s)}
                  className={`px-2.5 py-1 rounded text-[0.75rem] font-mono font-medium transition-colors ${
                    severityFilter === s
                      ? 'bg-ink text-surface'
                      : 'bg-surface text-muted hover:text-ink border border-line'
                  }`}
                >
                  {s}
                </button>
              ))}

              <div className="h-4 w-px bg-line mx-2 hidden sm:block" />

              <span className="text-[0.75rem] font-mono text-muted uppercase mr-1">Status:</span>
              {['ALL', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-2.5 py-1 rounded text-[0.75rem] font-mono font-medium transition-colors ${
                    statusFilter === st
                      ? 'bg-ink text-surface'
                      : 'bg-surface text-muted hover:text-ink border border-line'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div className="relative min-w-[240px]">
              <Search className="w-4 h-4 text-muted absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search station, variable..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-[0.8125rem] bg-surface border border-line rounded text-ink focus:outline-none focus:border-accent"
              />
            </div>
          </div>

          {/* Alerts Feed List */}
          {loadingAlerts ? (
            <div className="bg-panel border border-line rounded p-12 text-center text-muted font-mono text-[0.875rem]">
              Loading operational alerts stream...
            </div>
          ) : alertsError ? (
            <div className="bg-status-anomalous/10 border border-status-anomalous/30 rounded p-6 text-status-anomalous font-mono text-[0.875rem]">
              {alertsError}
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="bg-panel border border-line rounded p-12 text-center space-y-2">
              <CheckCircle2 className="w-8 h-8 text-status-valid mx-auto" />
              <h3 className="text-[1rem] font-semibold text-ink">No Active Alerts Match Criteria</h3>
              <p className="text-[0.8125rem] text-muted max-w-md mx-auto">
                All AWS sensors within the filtered parameters are operating within standard physical bounds and spatial consistency thresholds.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredAlerts.map((alert) => {
                const currentDraft = feedbackDrafts[alert.id] || {
                  label: 'confirmed_fault',
                  notes: '',
                  email: 'operator@aerosentinel.gov.in',
                };
                const hasFeedback = alert.feedback_label !== null && alert.feedback_label !== undefined;
                const isSubmitting = submittingFeedbackId === alert.id;
                const isSuccess = feedbackSuccessMsg?.alertId === alert.id;

                const borderColor =
                  alert.severity === 'critical'
                    ? 'border-l-status-anomalous'
                    : alert.severity === 'high'
                    ? 'border-l-amber-500'
                    : alert.severity === 'medium'
                    ? 'border-l-yellow-500'
                    : 'border-l-blue-400';

                return (
                  <div
                    key={alert.id}
                    className={`bg-panel border border-line border-l-4 ${borderColor} rounded p-5 transition-shadow hover:shadow-sm`}
                  >
                    {/* Card Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-line">
                      <div className="flex flex-wrap items-center gap-2">
                        {renderSeverityBadge(alert.severity)}

                        <span className="text-[0.75rem] font-mono px-2 py-0.5 rounded border border-line bg-surface text-ink font-semibold">
                          {alert.station_code}
                        </span>

                        <span className="text-[0.875rem] font-semibold text-ink font-sans">
                          {alert.station_name}
                        </span>

                        <span className="text-line">•</span>

                        <span className="text-[0.75rem] font-mono uppercase text-accent bg-accent/10 px-2 py-0.5 rounded">
                          {alert.variable}
                        </span>
                      </div>

                      <div className="flex items-center space-x-2 text-[0.75rem] font-mono text-muted">
                        <span
                          className={`px-2 py-0.5 rounded uppercase font-semibold ${
                            alert.status === 'open'
                              ? 'bg-status-anomalous/15 text-status-anomalous'
                              : alert.status === 'acknowledged'
                              ? 'bg-amber-500/15 text-amber-500'
                              : 'bg-status-valid/15 text-status-valid'
                          }`}
                        >
                          {alert.status}
                        </span>
                        <span>{new Date(alert.created_at).toLocaleString()}</span>
                      </div>
                    </div>

                    {/* Card Body: Failure Message */}
                    <div className="py-3">
                      <p className="text-[0.875rem] text-ink font-mono bg-surface border border-line p-3 rounded leading-relaxed">
                        {alert.message}
                      </p>
                    </div>

                    {/* Ground-Truth Feedback Section */}
                    <div className="mt-3 pt-3 border-t border-line">
                      {isSuccess ? (
                        <div className="p-3 bg-status-valid/10 border border-status-valid/30 rounded flex items-center space-x-2 text-status-valid font-mono text-[0.8125rem]">
                          <Check className="w-4 h-4" />
                          <span>{feedbackSuccessMsg.text}</span>
                        </div>
                      ) : hasFeedback ? (
                        <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-surface border border-line rounded">
                          <div className="flex items-center space-x-2">
                            {alert.feedback_label === 'confirmed_fault' ? (
                              <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-status-valid/15 text-status-valid border border-status-valid/30 font-mono text-[0.75rem] font-semibold">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>CONFIRMED SENSOR FAULT (GROUND TRUTH RECORDED)</span>
                              </span>
                            ) : alert.feedback_label === 'false_alarm' ? (
                              <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-amber-500/15 text-amber-500 border border-amber-500/30 font-mono text-[0.75rem] font-semibold">
                                <AlertTriangle className="w-3.5 h-3.5" />
                                <span>FLAGGED AS FALSE ALARM (MICROCLIMATE / NATURAL EVENT)</span>
                              </span>
                            ) : (
                              <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-blue-500/15 text-blue-500 border border-blue-500/30 font-mono text-[0.75rem] font-semibold">
                                <HelpCircle className="w-3.5 h-3.5" />
                                <span>MARKED AS UNSURE (PENDING TECHNICIAN AUDIT)</span>
                              </span>
                            )}
                            <span className="text-[0.75rem] text-muted font-sans">
                              Indexed for Phase 4 Continuous Retraining
                            </span>
                          </div>

                          {onInspectStation && (
                            <button
                              onClick={() => onInspectStation(alert.station_code)}
                              className="flex items-center space-x-1 text-[0.75rem] font-sans font-medium text-accent hover:underline"
                            >
                              <span>Inspect Time Series</span>
                              <ExternalLink className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      ) : (
                        <div className="p-4 bg-surface border border-line rounded space-y-3">
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div className="flex items-center space-x-1.5 text-[0.8125rem] font-semibold text-ink font-sans">
                              <MessageSquare className="w-4 h-4 text-accent" />
                              <span>Operator Ground-Truth Feedback</span>
                            </div>
                            <span className="text-[0.6875rem] font-mono text-muted">
                              Human-in-the-loop validation for ML Retraining (SIH26073)
                            </span>
                          </div>

                          {/* Action Choice Pills */}
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                            <button
                              type="button"
                              onClick={() =>
                                setFeedbackDrafts((prev) => ({
                                  ...prev,
                                  [alert.id]: { ...currentDraft, label: 'confirmed_fault' },
                                }))
                              }
                              className={`flex items-center justify-center space-x-1.5 p-2 rounded text-[0.75rem] font-mono font-medium border transition-colors ${
                                currentDraft.label === 'confirmed_fault'
                                  ? 'bg-status-valid/15 border-status-valid text-status-valid shadow-sm'
                                  : 'bg-panel border-line text-muted hover:text-ink'
                              }`}
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Confirmed Fault</span>
                            </button>

                            <button
                              type="button"
                              onClick={() =>
                                setFeedbackDrafts((prev) => ({
                                  ...prev,
                                  [alert.id]: { ...currentDraft, label: 'false_alarm' },
                                }))
                              }
                              className={`flex items-center justify-center space-x-1.5 p-2 rounded text-[0.75rem] font-mono font-medium border transition-colors ${
                                currentDraft.label === 'false_alarm'
                                  ? 'bg-amber-500/15 border-amber-500 text-amber-500 shadow-sm'
                                  : 'bg-panel border-line text-muted hover:text-ink'
                              }`}
                            >
                              <AlertTriangle className="w-3.5 h-3.5" />
                              <span>False Alarm</span>
                            </button>

                            <button
                              type="button"
                              onClick={() =>
                                setFeedbackDrafts((prev) => ({
                                  ...prev,
                                  [alert.id]: { ...currentDraft, label: 'unsure' },
                                }))
                              }
                              className={`flex items-center justify-center space-x-1.5 p-2 rounded text-[0.75rem] font-mono font-medium border transition-colors ${
                                currentDraft.label === 'unsure'
                                  ? 'bg-blue-500/15 border-blue-500 text-blue-500 shadow-sm'
                                  : 'bg-panel border-line text-muted hover:text-ink'
                              }`}
                            >
                              <HelpCircle className="w-3.5 h-3.5" />
                              <span>Unsure / Audit</span>
                            </button>
                          </div>

                          {/* Notes and Submit Row */}
                          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                            <input
                              type="text"
                              placeholder="Optional domain notes (e.g. thermistor failure, microclimate inversion)..."
                              value={currentDraft.notes}
                              onChange={(e) =>
                                setFeedbackDrafts((prev) => ({
                                  ...prev,
                                  [alert.id]: { ...currentDraft, notes: e.target.value },
                                }))
                              }
                              className="flex-1 px-3 py-1.5 text-[0.8125rem] bg-panel border border-line rounded text-ink focus:outline-none focus:border-accent"
                            />

                            <button
                              disabled={isSubmitting}
                              onClick={() => handleSubmitFeedback(alert.id)}
                              className="flex items-center justify-center space-x-1.5 px-4 py-1.5 bg-accent hover:bg-accent/90 disabled:opacity-50 text-white rounded text-[0.8125rem] font-sans font-medium transition-colors"
                            >
                              <Send className="w-3.5 h-3.5" />
                              <span>{isSubmitting ? 'Recording...' : 'Submit Feedback'}</span>
                            </button>
                          </div>

                          {/* Quick Lifecycle Buttons */}
                          <div className="flex items-center justify-between pt-2 border-t border-line/60 text-[0.75rem]">
                            <div className="flex items-center space-x-2">
                              {alert.status === 'open' && (
                                <button
                                  onClick={() => handleUpdateStatus(alert.id, 'acknowledged')}
                                  className="px-2.5 py-1 rounded bg-panel border border-line text-ink hover:bg-line/30 transition-colors"
                                >
                                  Mark Acknowledged
                                </button>
                              )}
                              {alert.status !== 'resolved' && (
                                <button
                                  onClick={() => handleUpdateStatus(alert.id, 'resolved')}
                                  className="px-2.5 py-1 rounded bg-panel border border-line text-status-valid hover:bg-line/30 transition-colors"
                                >
                                  Resolve Alert
                                </button>
                              )}
                            </div>

                            {onInspectStation && (
                              <button
                                onClick={() => onInspectStation(alert.station_code)}
                                className="flex items-center space-x-1 text-accent hover:underline font-medium"
                              >
                                <span>Inspect Station Telemetry</span>
                                <ExternalLink className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* SUBTAB 2: MODEL RETRAINING & GOVERNANCE CONSOLE (PHASE 4) */}
      {activeSubTab === 'audit' && (
        <div className="space-y-6">
          {/* Top Governance Control Bar */}
          <div className="bg-panel border border-line rounded p-5 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-[0.75rem] font-mono uppercase tracking-wider text-accent font-semibold">
                    Phase 4 Learning Loop
                  </span>
                  <span className="text-line">•</span>
                  <span className="text-[0.75rem] font-mono text-muted">Feature F14 (Model Retraining Job)</span>
                </div>
                <h3 className="text-[1.25rem] font-semibold text-ink mt-1 font-sans flex items-center space-x-2">
                  <Cpu className="w-5 h-5 text-accent" />
                  <span>Model Retraining & Governance Console</span>
                </h3>
                <p className="text-[0.875rem] text-muted font-sans mt-0.5 max-w-3xl">
                  Automated semi-supervised continuous learning loop. Incorporates operator ground-truth decisions into the training baseline, calibrates anomaly decision boundaries, and eliminates verified false alarms.
                </p>
              </div>

              {/* Retrain Action Button */}
              <div className="flex items-center space-x-3">
                <button
                  disabled={retrainingInProgress}
                  onClick={handleTriggerRetrain}
                  className="flex items-center space-x-2 px-4 py-2 bg-accent hover:bg-accent/90 disabled:opacity-50 text-white rounded text-[0.8125rem] font-sans font-medium transition-colors shadow-sm"
                >
                  <Sparkles className={`w-4 h-4 ${retrainingInProgress ? 'animate-spin' : ''}`} />
                  <span>{retrainingInProgress ? 'Retraining Models...' : 'Trigger Continuous Retrain'}</span>
                </button>
              </div>
            </div>

            {/* Metric Status Tiles */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-3 border-t border-line">
              <div className="p-3 bg-surface border border-line rounded">
                <span className="text-[0.75rem] font-mono text-muted uppercase">Active Production Version</span>
                <div className="text-[1.25rem] font-mono font-semibold text-ink mt-0.5 flex items-center space-x-2">
                  <span>{retrainStats?.active_model_version || 'v1.0.0'}</span>
                  <span className="w-2 h-2 rounded-full bg-status-valid inline-block" />
                </div>
              </div>

              <div className="p-3 bg-surface border border-line rounded">
                <span className="text-[0.75rem] font-mono text-amber-500 uppercase">False Alarms to Eliminate</span>
                <div className="text-[1.25rem] font-mono font-semibold text-amber-500 mt-0.5">
                  {retrainStats?.false_alarms_count ?? 0}
                </div>
              </div>

              <div className="p-3 bg-surface border border-line rounded">
                <span className="text-[0.75rem] font-mono text-status-valid uppercase">Confirmed Faults to Retain</span>
                <div className="text-[1.25rem] font-mono font-semibold text-status-valid mt-0.5">
                  {retrainStats?.confirmed_faults_count ?? 0}
                </div>
              </div>

              <div className="p-3 bg-surface border border-line rounded">
                <span className="text-[0.75rem] font-mono text-muted uppercase">Total Ground-Truth Labels</span>
                <div className="text-[1.25rem] font-mono font-semibold text-ink mt-0.5">
                  {retrainStats?.total_feedback_count ?? 0}
                </div>
              </div>
            </div>
          </div>

          {/* Retrain Result Success Banner */}
          {latestRetrainResult && (
            <div className="bg-status-valid/10 border border-status-valid/40 rounded p-4 space-y-2">
              <div className="flex items-center space-x-2 text-status-valid font-sans font-semibold text-[0.9375rem]">
                <CheckCircle2 className="w-5 h-5" />
                <span>Model Retraining Succeeded & Activated in Production!</span>
              </div>
              <p className="text-[0.8125rem] text-ink font-mono">
                {latestRetrainResult.message}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-[0.75rem] font-mono">
                <div className="p-2 bg-panel rounded border border-status-valid/30">
                  <span className="text-muted block">Activated Model</span>
                  <span className="text-ink font-bold">{latestRetrainResult.new_version}</span>
                </div>
                <div className="p-2 bg-panel rounded border border-status-valid/30">
                  <span className="text-muted block">False Alarm Reduction</span>
                  <span className="text-status-valid font-bold">
                    {latestRetrainResult.metrics.false_alarm_reduction_pct}%
                  </span>
                </div>
                <div className="p-2 bg-panel rounded border border-status-valid/30">
                  <span className="text-muted block">Calibrated Threshold</span>
                  <span className="text-ink font-bold">
                    {latestRetrainResult.metrics.previous_threshold} → {latestRetrainResult.metrics.new_threshold}
                  </span>
                </div>
                <div className="p-2 bg-panel rounded border border-status-valid/30">
                  <span className="text-muted block">Training Samples</span>
                  <span className="text-ink font-bold">
                    {latestRetrainResult.metrics.total_training_samples} rows
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Section 1: Model Registry Audit History */}
          <div className="bg-panel border border-line rounded p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-[1rem] font-semibold text-ink font-sans flex items-center space-x-2">
                  <Layers className="w-4 h-4 text-accent" />
                  <span>Model Registry Versions & Rollback</span>
                </h4>
                <p className="text-[0.8125rem] text-muted font-sans mt-0.5">
                  Audit log of trained Isolation Forest bundles. Active model is highlighted; previous models can be reactivated instantly.
                </p>
              </div>

              <span className="text-[0.75rem] font-mono text-muted">
                {registeredModels.length} Versions Recorded
              </span>
            </div>

            <div className="overflow-x-auto border border-line rounded">
              <table className="w-full text-left text-[0.8125rem] font-sans">
                <thead className="bg-surface border-b border-line text-muted font-mono text-[0.6875rem] uppercase">
                  <tr>
                    <th className="py-2.5 px-3">Registry ID</th>
                    <th className="py-2.5 px-3">Model Type</th>
                    <th className="py-2.5 px-3">Variable</th>
                    <th className="py-2.5 px-3">Version</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">False Alarm Reduction</th>
                    <th className="py-2.5 px-3">Trained At</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line text-ink">
                  {registeredModels.map((m) => {
                    const reduction = m.metrics?.false_alarm_reduction_pct;
                    const isActivating = activatingModelId === m.id;

                    return (
                      <tr key={m.id} className={m.is_active ? 'bg-accent/5' : 'hover:bg-surface/50'}>
                        <td className="py-2 px-3 font-mono text-muted">#{m.id}</td>
                        <td className="py-2 px-3 font-mono capitalize">{m.model_type.replace('_', ' ')}</td>
                        <td className="py-2 px-3 font-mono uppercase text-accent font-semibold">{m.variable}</td>
                        <td className="py-2 px-3 font-mono font-semibold">{m.version}</td>
                        <td className="py-2 px-3">
                          {m.is_active ? (
                            <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[0.6875rem] font-mono bg-status-valid/15 text-status-valid border border-status-valid/30 font-semibold">
                              <span className="w-1.5 h-1.5 rounded-full bg-status-valid" />
                              <span>ACTIVE</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[0.6875rem] font-mono bg-surface text-muted border border-line">
                              STANDBY
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3 font-mono">
                          {reduction !== undefined ? (
                            <span className="text-status-valid font-semibold">{reduction}%</span>
                          ) : (
                            <span className="text-muted">Baseline</span>
                          )}
                        </td>
                        <td className="py-2 px-3 font-mono text-muted text-[0.75rem]">
                          {new Date(m.trained_at).toLocaleString()}
                        </td>
                        <td className="py-2 px-3 text-right">
                          {!m.is_active ? (
                            <button
                              disabled={isActivating}
                              onClick={() => handleActivateModel(m.id)}
                              className="inline-flex items-center space-x-1 px-2.5 py-1 text-[0.75rem] font-sans font-medium text-ink bg-surface hover:bg-panel border border-line rounded transition-colors"
                            >
                              <RotateCcw className="w-3 h-3" />
                              <span>{isActivating ? 'Activating...' : 'Rollback / Activate'}</span>
                            </button>
                          ) : (
                            <span className="text-[0.75rem] font-mono text-muted">Serving Live</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 2: Operator Feedback Ground-Truth Registry */}
          <div className="bg-panel border border-line rounded p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h4 className="text-[1rem] font-semibold text-ink font-sans flex items-center space-x-2">
                  <Database className="w-4 h-4 text-accent" />
                  <span>Ground-Truth Feedback Log (Retraining Training Set)</span>
                </h4>
                <p className="text-[0.8125rem] text-muted font-sans mt-0.5">
                  Raw operator decisions from operational alerts used as ground truth for model retraining.
                </p>
              </div>

              {/* Label filter */}
              <div className="flex items-center space-x-2">
                <span className="text-[0.75rem] font-mono text-muted uppercase">Filter:</span>
                {['ALL', 'confirmed_fault', 'false_alarm', 'unsure'].map((lbl) => (
                  <button
                    key={lbl}
                    onClick={() => setFeedbackFilterLabel(lbl)}
                    className={`px-2.5 py-1 rounded text-[0.6875rem] font-mono uppercase transition-colors ${
                      feedbackFilterLabel === lbl
                        ? 'bg-ink text-surface'
                        : 'bg-surface text-muted border border-line hover:text-ink'
                    }`}
                  >
                    {lbl.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {loadingFeedback ? (
              <div className="p-8 text-center text-muted font-mono text-[0.875rem]">
                Loading feedback records...
              </div>
            ) : feedbackList.length === 0 ? (
              <div className="p-8 text-center text-muted font-sans space-y-1">
                <Info className="w-6 h-6 text-muted mx-auto mb-2" />
                <p className="font-semibold text-ink">No Feedback Logged Yet</p>
                <p className="text-[0.8125rem]">
                  Submit ground-truth labels on active alerts in the Operational Feed to populate this retraining pool.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto border border-line rounded">
                <table className="w-full text-left text-[0.8125rem] font-sans">
                  <thead className="bg-surface border-b border-line text-muted font-mono text-[0.6875rem] uppercase">
                    <tr>
                      <th className="py-2.5 px-3">Feedback ID</th>
                      <th className="py-2.5 px-3">QC Result ID</th>
                      <th className="py-2.5 px-3">Station</th>
                      <th className="py-2.5 px-3">Variable</th>
                      <th className="py-2.5 px-3">Operator Decision</th>
                      <th className="py-2.5 px-3">Notes</th>
                      <th className="py-2.5 px-3">Auditor</th>
                      <th className="py-2.5 px-3">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line text-ink">
                    {feedbackList.map((item) => (
                      <tr key={item.id} className="hover:bg-surface/50">
                        <td className="py-2 px-3 font-mono text-muted">#{item.id}</td>
                        <td className="py-2 px-3 font-mono text-accent">qc_{item.qc_result_id}</td>
                        <td className="py-2 px-3 font-medium">
                          {item.station_code || 'N/A'}
                          {item.station_name ? ` · ${item.station_name}` : ''}
                        </td>
                        <td className="py-2 px-3 font-mono uppercase text-muted">
                          {item.variable || 'N/A'}
                        </td>
                        <td className="py-2 px-3 font-mono">
                          {item.label === 'confirmed_fault' ? (
                            <span className="inline-flex items-center space-x-1 text-status-valid font-semibold">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>CONFIRMED FAULT</span>
                            </span>
                          ) : item.label === 'false_alarm' ? (
                            <span className="inline-flex items-center space-x-1 text-amber-500 font-semibold">
                              <AlertTriangle className="w-3 h-3" />
                              <span>FALSE ALARM</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center space-x-1 text-blue-500 font-semibold">
                              <HelpCircle className="w-3 h-3" />
                              <span>UNSURE</span>
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-muted max-w-xs truncate" title={item.notes || ''}>
                          {item.notes || '—'}
                        </td>
                        <td className="py-2 px-3 text-muted font-mono text-[0.75rem]">
                          {item.user_email || 'operator@aerosentinel.gov.in'}
                        </td>
                        <td className="py-2 px-3 font-mono text-muted text-[0.75rem]">
                          {new Date(item.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
