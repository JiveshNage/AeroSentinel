import React, { useEffect, useState, useCallback } from 'react';
import { Header, AppTab } from './components/Header';
import { HealthCard } from './components/HealthCard';
import { MapView } from './pages/MapView';
import { StationDetailView } from './pages/StationDetailView';
import { AlertsFeedView } from './pages/AlertsFeedView';
import { MaintenanceView } from './pages/MaintenanceView';
import { TasksView } from './pages/TasksView';
import { FileUploadView } from './pages/FileUploadView';
import { LiveChartView } from './pages/LiveChartView';
import { fetchHealth, HealthResponse } from './api/client';
import { fetchAlerts } from './api/alerts';
import { fetchTasks } from './api/tasks';
import { DEMO_USERS, getStoredUser, AuthUser } from './api/auth';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AppTab>('map');
  const [selectedStationCode, setSelectedStationCode] = useState<string>('NCR001');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeAlertsCount, setActiveAlertsCount] = useState<number>(0);
  const [pendingTasksCount, setPendingTasksCount] = useState<number>(0);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(() => getStoredUser() || DEMO_USERS.admin);

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

  const refreshCounts = useCallback(async () => {
    try {
      const alertRes = await fetchAlerts({ status: 'open', limit: 1 });
      setActiveAlertsCount(alertRes.total);
    } catch (e) {
      // Ignore
    }

    try {
      const taskRes = await fetchTasks({ status: 'pending' });
      setPendingTasksCount(taskRes.total);
    } catch (e) {
      // Ignore
    }
  }, []);

  useEffect(() => {
    checkHealth();
    refreshCounts();
    const interval = setInterval(() => {
      checkHealth();
      refreshCounts();
    }, 30000);
    return () => clearInterval(interval);
  }, [checkHealth, refreshCounts]);

  const isHealthy = healthData?.status === 'healthy';

  return (
    <div className="min-h-screen bg-surface flex flex-col font-sans">
      <Header
        systemHealthy={error ? false : loading && !healthData ? null : isHealthy}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        activeAlertsCount={activeAlertsCount}
        pendingTasksCount={pendingTasksCount}
        currentUser={currentUser}
        onUserChange={setCurrentUser}
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
        ) : activeTab === 'live' ? (
          <LiveChartView
            initialStationCode={selectedStationCode}
            onInspectStation={(code) => {
              setSelectedStationCode(code);
              setActiveTab('detail');
            }}
          />
        ) : activeTab === 'alerts' ? (
          <AlertsFeedView
            onInspectStation={(code) => {
              setSelectedStationCode(code);
              setActiveTab('detail');
            }}
          />
        ) : activeTab === 'tasks' ? (
          <TasksView
            currentUser={currentUser}
            onInspectStation={(code) => {
              setSelectedStationCode(code);
              setActiveTab('detail');
            }}
          />
        ) : activeTab === 'upload' ? (
          <FileUploadView
            currentUser={currentUser}
            onInspectStation={(code) => {
              setSelectedStationCode(code);
              setActiveTab('detail');
            }}
          />
        ) : activeTab === 'maintenance' ? (
          <MaintenanceView
            onInspectStation={(code) => {
              setSelectedStationCode(code);
              setActiveTab('detail');
            }}
          />
        ) : (
          <div className="space-y-6">
            {/* Intro banner */}
            <div className="bg-panel border border-line rounded-lg p-5">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start space-x-4">
                  <img
                    src="/logo.png"
                    alt="AeroSentinel Logo"
                    className="h-12 w-auto object-contain rounded-lg p-1 bg-surface border border-line hidden sm:block shadow-xs"
                  />
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-[0.75rem] font-mono uppercase tracking-wider text-accent font-semibold">
                        System Architecture & Status
                      </span>
                      <span className="text-line">•</span>
                      <span className="text-[0.75rem] font-mono text-muted">Feature F1-F16 Complete</span>
                    </div>
                    <h2 className="text-[1.25rem] font-semibold text-ink mt-1 font-sans">
                      AeroSentinel — AI/ML Weather Station Quality Control
                    </h2>
                    <p className="text-[0.875rem] text-muted mt-1 max-w-3xl font-sans">
                      Integrated FastAPI ingestion, TimescaleDB sensor hypertable, rule engine
                      (range/step/persistence), IsolationForest anomaly scorer, 3D KDTree spatial consistency,
                      RBAC task workflow board, and live telemetry streaming.
                    </p>
                  </div>
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
            <div className="bg-panel border border-line rounded-lg p-6">
              <h3 className="text-[1.125rem] font-semibold text-ink font-sans mb-1">
                System Module Boundaries & RBAC Infrastructure
              </h3>
              <p className="text-[0.8125rem] text-muted font-sans mb-4">
                Decoupled layers adhering strictly to architecture.md.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 border border-line rounded-lg bg-surface">
                  <span className="text-[0.75rem] font-mono text-accent font-semibold block">01 / INGESTION & DATA</span>
                  <h4 className="text-[0.9375rem] font-medium text-ink mt-1">Telemetry Ingestion & File Upload</h4>
                  <p className="text-[0.8125rem] text-muted mt-1 font-sans">
                    REST, simulator stream receiver & CSV/JSON file upload gateway with auto-station resolution.
                  </p>
                  <span className="inline-block mt-3 text-[0.6875rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded">
                    backend/ingestion
                  </span>
                </div>

                <div className="p-4 border border-line rounded-lg bg-surface">
                  <span className="text-[0.75rem] font-mono text-accent font-semibold block">02 / QC ENGINE</span>
                  <h4 className="text-[0.9375rem] font-medium text-ink mt-1">Multi-Layer QC Pipeline</h4>
                  <p className="text-[0.8125rem] text-muted mt-1 font-sans">
                    Rule engine (range/step/flatline), ML anomaly scoring (IsolationForest), and 3D KDTree spatial check.
                  </p>
                  <span className="inline-block mt-3 text-[0.6875rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded">
                    backend/qc
                  </span>
                </div>

                <div className="p-4 border border-line rounded-lg bg-surface">
                  <span className="text-[0.75rem] font-mono text-accent font-semibold block">03 / RBAC & LIVE OPS</span>
                  <h4 className="text-[0.9375rem] font-medium text-ink mt-1">Role Workflows & Live Streaming</h4>
                  <p className="text-[0.8125rem] text-muted mt-1 font-sans">
                    Role-based operational task division, real-time waveform streaming, and predictive maintenance dispatch.
                  </p>
                  <span className="inline-block mt-3 text-[0.6875rem] font-mono text-muted border border-line px-1.5 py-0.5 rounded">
                    backend/tasks & live
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="w-full border-t border-line py-4 px-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-[0.75rem] font-mono text-muted bg-panel">
        <div className="flex items-center space-x-2">
          <img src="/logo.png" alt="AeroSentinel" className="h-5 w-auto object-contain rounded" />
          <span className="font-semibold text-ink">AeroSentinel</span>
          <span>· MoES / IMD Disaster Management (SIH26073)</span>
        </div>
        <div className="flex items-center space-x-3 text-[0.6875rem]">
          <span>Role Clearance: <strong className="text-ink">{currentUser?.role || 'admin'}</strong></span>
          <span>•</span>
          <span>FastAPI + TimescaleDB + IsolationForest</span>
        </div>
      </footer>
    </div>
  );
};
