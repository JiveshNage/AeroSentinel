import React, { useEffect, useState } from 'react';
import {
  Map,
  Server,
  Activity,
  ShieldAlert,
  Wrench,
  Shield,
  Radio,
  CheckSquare,
  UploadCloud,
} from 'lucide-react';
import { DEMO_USERS, getStoredUser, loginWithCredentials, AuthUser } from '../api/auth';

export type AppTab =
  | 'map'
  | 'detail'
  | 'live'
  | 'alerts'
  | 'tasks'
  | 'upload'
  | 'maintenance'
  | 'system';

interface HeaderProps {
  systemHealthy: boolean | null;
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  activeAlertsCount?: number;
  pendingTasksCount?: number;
  currentUser: AuthUser | null;
  onUserChange: (user: AuthUser) => void;
}

export const Header: React.FC<HeaderProps> = ({
  systemHealthy,
  activeTab,
  onTabChange,
  activeAlertsCount,
  pendingTasksCount,
  currentUser,
  onUserChange,
}) => {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('aerosentinel-theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  const [switchingRole, setSwitchingRole] = useState<boolean>(false);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('aerosentinel-theme', theme);
  }, [theme]);

  // Initial silent login to ensure valid token in localStorage
  useEffect(() => {
    if (!getStoredUser()) {
      loginWithCredentials(DEMO_USERS.admin.email, DEMO_USERS.admin.pass)
        .then((res) => onUserChange(res.user))
        .catch(() => {});
    }
  }, [onUserChange]);

  const toggleTheme = () => {
    setTheme((prev: 'light' | 'dark') => (prev === 'light' ? 'dark' : 'light'));
  };

  const handleRoleSwitch = async (roleKey: string) => {
    const target = DEMO_USERS[roleKey];
    if (!target) return;
    try {
      setSwitchingRole(true);
      const res = await loginWithCredentials(target.email, target.pass);
      onUserChange(res.user);
    } catch (err) {
      console.error('Failed to switch role:', err);
    } finally {
      setSwitchingRole(false);
    }
  };

  const currentRoleKey = currentUser
    ? Object.keys(DEMO_USERS).find((k) => DEMO_USERS[k].role === currentUser.role) || 'admin'
    : 'admin';

  return (
    <header className="w-full bg-panel border-b border-line px-4 sm:px-6 py-2.5 flex items-center justify-between sticky top-0 z-40 backdrop-blur-md bg-opacity-95 shadow-sm">
      <div className="flex items-center space-x-4 lg:space-x-6">
        {/* Brand with asset/Logo.png */}
        <div
          onClick={() => onTabChange('map')}
          className="flex items-center space-x-3 cursor-pointer group"
        >
          <img
            src="/logo.png"
            alt="AeroSentinel Logo"
            className="h-9 w-auto max-w-[42px] object-contain rounded drop-shadow-sm group-hover:scale-105 transition-transform"
          />
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-[1.125rem] font-bold tracking-tight text-ink font-sans leading-none">
                AeroSentinel
              </h1>
              <span className="text-[0.625rem] text-accent font-mono font-semibold px-1.5 py-0.2 border border-accent/30 rounded bg-accent/10">
                v0.1.0
              </span>
            </div>
            <p className="text-[0.6875rem] text-muted font-sans font-medium hidden sm:block mt-0.5">
              MoES · IMD AWS Quality Control
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center space-x-1 border-l border-line pl-3 lg:pl-5 overflow-x-auto py-1 scrollbar-none">
          <button
            onClick={() => onTabChange('map')}
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded text-[0.8125rem] font-medium transition-colors whitespace-nowrap ${
              activeTab === 'map'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <Map className="w-3.5 h-3.5" />
            <span>Fleet Map</span>
          </button>

          <button
            onClick={() => onTabChange('detail')}
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded text-[0.8125rem] font-medium transition-colors whitespace-nowrap ${
              activeTab === 'detail'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Station Detail</span>
          </button>

          <button
            onClick={() => onTabChange('live')}
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded text-[0.8125rem] font-medium transition-colors whitespace-nowrap ${
              activeTab === 'live'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <Radio className="w-3.5 h-3.5 text-status-valid animate-pulse" />
            <span>Live Stream</span>
          </button>

          <button
            onClick={() => onTabChange('alerts')}
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded text-[0.8125rem] font-medium transition-colors whitespace-nowrap ${
              activeTab === 'alerts'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Alerts</span>
            {activeAlertsCount !== undefined && activeAlertsCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[0.625rem] font-mono bg-status-anomalous text-white font-bold">
                {activeAlertsCount}
              </span>
            )}
          </button>

          <button
            onClick={() => onTabChange('tasks')}
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded text-[0.8125rem] font-medium transition-colors whitespace-nowrap ${
              activeTab === 'tasks'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <CheckSquare className="w-3.5 h-3.5" />
            <span>Role Tasks</span>
            {pendingTasksCount !== undefined && pendingTasksCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[0.625rem] font-mono bg-accent text-white font-bold">
                {pendingTasksCount}
              </span>
            )}
          </button>

          <button
            onClick={() => onTabChange('upload')}
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded text-[0.8125rem] font-medium transition-colors whitespace-nowrap ${
              activeTab === 'upload'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>Upload Data</span>
          </button>

          <button
            onClick={() => onTabChange('maintenance')}
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded text-[0.8125rem] font-medium transition-colors whitespace-nowrap ${
              activeTab === 'maintenance'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <Wrench className="w-3.5 h-3.5" />
            <span>Maintenance</span>
          </button>

          <button
            onClick={() => onTabChange('system')}
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded text-[0.8125rem] font-medium transition-colors whitespace-nowrap ${
              activeTab === 'system'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <Server className="w-3.5 h-3.5" />
            <span>Health</span>
          </button>
        </nav>
      </div>

      <div className="flex items-center space-x-3">
        {/* RBAC Role Switcher */}
        <div className="flex items-center space-x-1.5 bg-surface border border-line rounded px-2.5 py-1 text-xs shadow-xs">
          <Shield className="w-3.5 h-3.5 text-accent" />
          <span className="text-muted font-mono hidden md:inline text-[0.75rem]">Role:</span>
          <select
            value={currentRoleKey}
            onChange={(e) => handleRoleSwitch(e.target.value)}
            disabled={switchingRole}
            className="bg-transparent text-ink font-semibold focus:outline-none cursor-pointer text-xs"
            aria-label="Switch RBAC user role"
          >
            <option value="admin">Admin (Full Access)</option>
            <option value="operator">DQO (QC Triage)</option>
            <option value="tech">Field Tech (Hardware)</option>
            <option value="forecaster">Forecaster (Observer)</option>
          </select>
        </div>

        {/* System Health Pulse */}
        <div className="hidden 2xl:flex items-center space-x-2 text-[0.75rem] font-mono border-l border-line pl-3">
          {systemHealthy === null ? (
            <span className="text-muted">CONNECTING</span>
          ) : systemHealthy ? (
            <span className="text-status-valid flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-status-valid inline-block animate-ping" />
              <span>ONLINE</span>
            </span>
          ) : (
            <span className="text-status-anomalous flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-status-anomalous inline-block" />
              <span>DEGRADED</span>
            </span>
          )}
        </div>

        {/* Dark/Light Theme Toggle */}
        <button
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          className="px-2.5 py-1 text-[0.75rem] font-sans border border-line rounded hover:bg-surface text-ink transition-colors flex items-center space-x-1.5"
        >
          <span>{theme === 'light' ? '☾ Dark' : '☀ Light'}</span>
        </button>
      </div>
    </header>
  );
};
