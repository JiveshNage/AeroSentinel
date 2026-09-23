import React, { useEffect, useState, useCallback } from 'react';
import { Header } from './components/Header';
import { HealthCard } from './components/HealthCard';
import { MapView } from './pages/MapView';
import { StationDetailView } from './pages/StationDetailView';
import { AlertsFeedView } from './pages/AlertsFeedView';
import { fetchHealth, HealthResponse } from './api/client';
import { fetchAlerts } from './api/alerts';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'map' | 'detail' | 'alerts' | 'system'>('map');
  const [selectedStationCode, setSelectedStationCode] = useState<string>('NCR001');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeAlertsCount, setActiveAlertsCount] = useState<number>(0);

  const checkHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHealth();
      setHealthData(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown communication error';
      setError(message);
      setHealthData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshAlertCount = useCallback(async () => {
    try {
      const res = await fetchAlerts({ status: 'open', limit: 1 });
      setActiveAlertsCount(res.total);
    } catch (e) {
      // Ignore count fetch errors
    }
  }, []);

  useEffect(() => {
    checkHealth();
    refreshAlertCount();
    const interval = setInterval(() => {
      checkHealth();
      refreshAlertCount();
    }, 30000);
    return () => clearInterval(interval);
  }, [checkHealth, refreshAlertCount]);

  const isHealthy = healthData?.status === 'healthy';

  return (
    <div className="min-h-screen bg-surface flex flex-col font-sans">
      <Header
        systemHealthy={error ? false : loading && !healthData ? null : isHealthy}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        activeAlertsCount={activeAlertsCount}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {activeTab === 'map' ? (
          <MapView
            onInspectStation={(code) => {
              setSelectedStationCode(code);
              setActiveTab('detail');
            }}
          />
        ) : activeTab === 'detail' ? (
          <StationDetailView
            initialStationCode={selectedStationCode}
            onBackToMap={() => setActiveTab('map')}
          />
        ) : activeTab === 'alerts' ? (
          <AlertsFeedView
            onInspectStation={(code) => {
              setSelectedStationCode(code);
              setActiveTab('detail');
            }}
          />
        ) : (
          <div className="space-y-6">
            {/* Intro banner */}
            <div className="bg-panel border border-line rounded p-5">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-[0.75rem] font-mono uppercase tracking-wider text-accent font-semibold">
                      Phase 3 Operator Product
                    </span>
                    <span className="text-line">•</span>
                    <span className="text-[0.75rem] font-mono text-muted">Feature F11 (Map View)</span>
                  </div>
                  <h2 className="text-[1.25rem] font-semibold text-ink mt-1 font-sans">
                    Automatic Weather Station (AWS) Quality Control Architecture
                  </h2>
                  <p className="text-[0.875rem] text-muted mt-1 max-w-3xl font-sans">
                    Integrated FastAPI ingestion, TimescaleDB sensor hypertable, rule engine (range/step/persistence),
                    IsolationForest anomaly scorer, 3D KDTree spatial consistency checker, and real-time alerts.
                  </p>
                </div>
                <div className="flex items-center space-x-3 text-[0.8125rem] font-mono">
                  <span className="px-2.5 py-1 rounded bg-surface border border-line text-ink">
                    FastAPI: :8000
                  </span>
                  <span className="px-2.5 py-1 rounded bg-surface border border-line text-ink">
                    Vite: :5173
                  </span>
                </div>
              </div>
            </div>

            {/* Health status component */}
            <HealthCard
              data={healthData}
              loading={loading}
              error={error}
              onRefresh={checkHealth}
            />

            {/* Architecture Modules Grid */}
            <div className="bg-panel border border-line rounded p-6">
              <h3 className="text-[1.125rem] font-semibold text-ink font-sans mb-1">
                System Module Boundaries
              </h3>
              <p className="text-[0.8125rem] text-muted font-sans mb-4">
                Pre-scaffolded decoupled layers adhering strictly to architecture.md.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 border border-line rounded bg-surface">
                  <span className="text-[0.75rem] font-mono text-accent font-semibold block">01 / INGESTION</span>
                  <h4 className="text-[0.9375rem] font-medium text-ink mt-1">Telemetry Ingestion</h4>
                  <p className="text-[0.8125rem] text-muted mt-1 font-sans">
                    REST & simulator stream receiver; validates payload shape, deduplicates readings, writes raw records.
                  </p>
                  <span className="inline-block mt-3 text-[0.6875rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded">
                    backend/ingestion
                  </span>
                </div>

                <div className="p-4 border border-line rounded bg-surface">
                  <span className="text-[0.75rem] font-mono text-accent font-semibold block">02 / QC ENGINE</span>
                  <h4 className="text-[0.9375rem] font-medium text-ink mt-1">Multi-Layer QC Pipeline</h4>
                  <p className="text-[0.8125rem] text-muted mt-1 font-sans">
                    Rule engine (range/step/flatline), ML anomaly scoring (IsolationForest), and 3D KDTree spatial check.
                  </p>
                  <span className="inline-block mt-3 text-[0.6875rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded">
                    backend/qc
                  </span>
                </div>

                <div className="p-4 border border-line rounded bg-surface">
                  <span className="text-[0.75rem] font-mono text-accent font-semibold block">03 / ALERTS & OPS</span>
                  <h4 className="text-[0.9375rem] font-medium text-ink mt-1">Alerting & Feedback Loop</h4>
                  <p className="text-[0.8125rem] text-muted mt-1 font-sans">
                    Severity thresholding, WebSocket real-time dispatch, operator feedback capture, and retrain pipeline.
                  </p>
                  <span className="inline-block mt-3 text-[0.6875rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded">
                    backend/alerts & retrain
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="w-full border-t border-line py-4 px-6 text-center text-[0.75rem] font-mono text-muted bg-panel">
        AeroSentinel · MoES / IMD Disaster Management · Smart India Hackathon (SIH26073)
      </footer>
    </div>
  );
};
