import React, { useEffect, useState, useCallback } from 'react';
import { Header } from './components/Header';
import { Sidebar, AppNavTab } from './components/Sidebar';
import { HealthCard } from './components/HealthCard';
import { MapView } from './pages/MapView';
import { StationDetailView } from './pages/StationDetailView';
import { AlertsFeedView } from './pages/AlertsFeedView';
import { MaintenanceView } from './pages/MaintenanceView';
import { TasksView } from './pages/TasksView';
import { FileUploadView } from './pages/FileUploadView';
import { LiveChartView } from './pages/LiveChartView';
import { DashboardView } from './pages/DashboardView';
import { AdminUsersView } from './pages/AdminUsersView';
import { AdminRolesView } from './pages/AdminRolesView';
import { AdminAuditView } from './pages/AdminAuditView';
import { AdminSettingsView } from './pages/AdminSettingsView';
import { fetchHealth, HealthResponse } from './api/client';
import { fetchAlerts } from './api/alerts';
import { fetchTasks } from './api/tasks';
import { DEMO_USERS, getStoredUser, AuthUser, hasPermission, PermissionCode } from './api/auth';

const TAB_PERMISSION_MAP: Partial<Record<AppNavTab, PermissionCode>> = {
  dashboard: 'dashboard.view',
  map: 'fleet.view',
  live: 'telemetry.view',
  stations: 'stations.view',
  alerts: 'alerts.view',
  health: 'health.view',
  tasks: 'fleet.view',
  upload: 'data.upload',
  maintenance: 'maintenance.view',
  admin_users: 'users.view',
  admin_roles: 'roles.manage',
  admin_audit: 'audit.view',
  admin_settings: 'system.manage',
};

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(() => getStoredUser() || DEMO_USERS.admin);
  const [activeTab, setActiveTab] = useState<AppNavTab>(() => {
    return currentUser?.role === 'field_technician' ? 'map' : 'dashboard';
  });
  const [selectedStationCode, setSelectedStationCode] = useState<string>('NCR001');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeAlertsCount, setActiveAlertsCount] = useState<number>(0);
  const [pendingTasksCount, setPendingTasksCount] = useState<number>(0);

  // Sidebar collapsible state
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState<boolean>(false);

  // Enforce frontend route guard when role or active tab changes
  useEffect(() => {
    if (!currentUser) return;
    const requiredPerm = TAB_PERMISSION_MAP[activeTab];
    if (requiredPerm && !hasPermission(currentUser, requiredPerm)) {
      if (hasPermission(currentUser, 'dashboard.view')) {
        setActiveTab('dashboard');
      } else if (hasPermission(currentUser, 'fleet.view')) {
        setActiveTab('map');
      } else if (hasPermission(currentUser, 'stations.view')) {
        setActiveTab('stations');
      }
    }
  }, [currentUser, activeTab]);

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
    } catch {
      // Ignore
    }

    try {
      const taskRes = await fetchTasks({ status: 'pending' });
      setPendingTasksCount(taskRes.total);
    } catch {
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
    <div className="min-h-screen bg-surface flex flex-col font-sans text-ink">
      {/* Top Header */}
      <Header
        systemHealthy={error ? false : loading && !healthData ? null : isHealthy}
        onNavigateTab={setActiveTab}
        onToggleSidebarMobile={() => setSidebarMobileOpen(!sidebarMobileOpen)}
        activeAlertsCount={activeAlertsCount}
        currentUser={currentUser}
        onUserChange={(newUser) => {
          setCurrentUser(newUser);
          // Auto route if field tech or viewer
          if (newUser.role === 'field_technician') {
            setActiveTab('map');
          } else {
            setActiveTab('dashboard');
          }
        }}
      />

      {/* Main Body with Sidebar + Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Collapsible Left Sidebar */}
        <Sidebar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          mobileOpen={sidebarMobileOpen}
          onMobileClose={() => setSidebarMobileOpen(false)}
          currentUser={currentUser}
          activeAlertsCount={activeAlertsCount}
          pendingTasksCount={pendingTasksCount}
        />

        {/* Primary Main Content View Area */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 max-w-7xl w-full mx-auto space-y-6">
          {activeTab === 'dashboard' ? (
            <DashboardView
              currentUser={currentUser}
              onNavigateTab={setActiveTab}
              onInspectStation={(code) => {
                setSelectedStationCode(code);
                setActiveTab('detail');
              }}
            />
          ) : activeTab === 'map' || activeTab === 'stations' ? (
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
          ) : activeTab === 'health' ? (
            <div className="space-y-6">
              <HealthCard
                data={healthData}
                loading={loading}
                error={error}
                onRefresh={checkHealth}
              />
            </div>
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
          ) : activeTab === 'admin_users' ? (
            <AdminUsersView />
          ) : activeTab === 'admin_roles' ? (
            <AdminRolesView />
          ) : activeTab === 'admin_audit' ? (
            <AdminAuditView />
          ) : activeTab === 'admin_settings' ? (
            <AdminSettingsView />
          ) : (
            <div className="p-8 text-center text-muted font-mono">
              View not found. Select a module from the sidebar.
            </div>
          )}
        </main>
      </div>

      {/* Global Compact Operations Footer */}
      <footer className="w-full border-t border-line py-3 px-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-mono text-muted bg-panel shrink-0 select-none">
        <div className="flex items-center space-x-2">
          <img src="/logo.png" alt="AeroSentinel" className="h-4 w-auto object-contain rounded" />
          <span className="font-semibold text-ink">AeroSentinel</span>
          <span>· Automated Weather Station AI Quality Control (SIH26073)</span>
        </div>
        <div className="flex items-center space-x-3 text-[10px]">
          <span>Role Clearance: <strong className="text-accent uppercase">{currentUser?.role || 'admin'}</strong></span>
          <span>•</span>
          <span>Permissions Active: <strong className="text-ink">{currentUser?.permissions?.length || 21} / 21</strong></span>
          <span>•</span>
          <span>FastAPI + TimescaleDB + IsolationForest</span>
        </div>
      </footer>
    </div>
  );
};
