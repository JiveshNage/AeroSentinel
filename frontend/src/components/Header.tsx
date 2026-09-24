import React, { useEffect, useState } from 'react';
import { Map, Server, Activity, ShieldAlert, Wrench } from 'lucide-react';

interface HeaderProps {
  systemHealthy: boolean | null;
  activeTab: 'map' | 'detail' | 'alerts' | 'maintenance' | 'system';
  onTabChange: (tab: 'map' | 'detail' | 'alerts' | 'maintenance' | 'system') => void;
  activeAlertsCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  systemHealthy,
  activeTab,
  onTabChange,
  activeAlertsCount,
}) => {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('aerosentinel-theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('aerosentinel-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev: 'light' | 'dark') => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <header className="w-full bg-panel border-b border-line px-6 py-3 flex items-center justify-between">
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-3">
          <div className="w-2.5 h-2.5 rounded-full bg-accent" />
          <h1 className="text-[1.25rem] font-semibold tracking-tight text-ink font-sans">
            AeroSentinel
          </h1>
          <span className="text-[0.75rem] text-muted font-mono px-2 py-0.5 border border-line rounded">
            SIH26073 / MoES-IMD
          </span>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center space-x-1 border-l border-line pl-6">
          <button
            onClick={() => onTabChange('map')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded text-[0.8125rem] font-medium transition-colors ${
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
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded text-[0.8125rem] font-medium transition-colors ${
              activeTab === 'detail'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Station Detail</span>
          </button>
          <button
            onClick={() => onTabChange('alerts')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded text-[0.8125rem] font-medium transition-colors ${
              activeTab === 'alerts'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Alerts Feed</span>
            {activeAlertsCount !== undefined && activeAlertsCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[0.6875rem] font-mono bg-status-anomalous text-white font-bold">
                {activeAlertsCount}
              </span>
            )}
          </button>
          <button
            onClick={() => onTabChange('maintenance')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded text-[0.8125rem] font-medium transition-colors ${
              activeTab === 'maintenance'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <Wrench className="w-3.5 h-3.5" />
            <span>Maintenance Queue</span>
          </button>
          <button
            onClick={() => onTabChange('system')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded text-[0.8125rem] font-medium transition-colors ${
              activeTab === 'system'
                ? 'bg-accent text-white shadow-sm'
                : 'text-muted hover:text-ink hover:bg-surface'
            }`}
          >
            <Server className="w-3.5 h-3.5" />
            <span>Architecture & Health</span>
          </button>
        </nav>

        <div className="hidden lg:flex items-center space-x-2 text-[0.8125rem] text-muted font-sans border-l border-line pl-6">
          <span>System Status:</span>
          {systemHealthy === null ? (
            <span className="text-muted font-mono">CONNECTING</span>
          ) : systemHealthy ? (
            <span className="text-status-valid font-mono font-medium flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-status-valid inline-block" />
              <span>ONLINE</span>
            </span>
          ) : (
            <span className="text-status-anomalous font-mono font-medium flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-status-anomalous inline-block" />
              <span>DEGRADED</span>
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center space-x-4">
        <button
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          className="px-3 py-1.5 text-[0.8125rem] font-sans border border-line rounded hover:bg-surface text-ink transition-colors flex items-center space-x-2"
        >
          <span>{theme === 'light' ? '☾ Dark' : '☀ Light'}</span>
        </button>
      </div>
    </header>
  );
};
