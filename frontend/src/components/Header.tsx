import React, { useEffect, useState } from 'react';
import {
  Menu,
  Bell,
  Sun,
  Moon,
  Shield,
  Activity,
  ChevronDown,
} from 'lucide-react';
import { DEMO_USERS, getStoredUser, loginWithCredentials, AuthUser } from '../api/auth';
import { AppNavTab } from './Sidebar';

interface HeaderProps {
  systemHealthy: boolean | null;
  onNavigateTab: (tab: AppNavTab) => void;
  onToggleSidebarMobile: () => void;
  activeAlertsCount?: number;
  currentUser: AuthUser | null;
  onUserChange: (user: AuthUser) => void;
}

export const Header: React.FC<HeaderProps> = ({
  systemHealthy,
  onNavigateTab,
  onToggleSidebarMobile,
  activeAlertsCount = 0,
  currentUser,
  onUserChange,
}) => {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('aerosentinel-theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  const [roleMenuOpen, setRoleMenuOpen] = useState<boolean>(false);
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
      setRoleMenuOpen(false);
    } catch (err) {
      console.error('Failed to switch role:', err);
    } finally {
      setSwitchingRole(false);
    }
  };

  const getRoleBadgeColor = (role?: string) => {
    switch (role) {
      case 'admin':
        return 'bg-purple-500/15 text-purple-400 border-purple-500/30';
      case 'forecaster':
        return 'bg-sky-500/15 text-sky-400 border-sky-500/30';
      case 'qc_analyst':
      case 'data_quality_officer':
        return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
      case 'field_technician':
        return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
      case 'viewer':
      default:
        return 'bg-slate-500/15 text-slate-400 border-slate-500/30';
    }
  };

  return (
    <header className="h-14 w-full bg-panel border-b border-line px-3 sm:px-5 flex items-center justify-between sticky top-0 z-40 backdrop-blur-md bg-opacity-95 shadow-xs select-none">
      {/* Left: Mobile Toggle & Brand Details */}
      <div className="flex items-center space-x-3">
        {/* Mobile menu button */}
        <button
          onClick={onToggleSidebarMobile}
          className="md:hidden p-2 rounded text-muted hover:text-ink hover:bg-hover transition-colors"
          aria-label="Toggle Navigation Drawer"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Logo and Version Badge */}
        <div
          onClick={() => onNavigateTab('dashboard')}
          className="flex items-center space-x-2.5 cursor-pointer group"
        >
          <img
            src="/logo.png"
            alt="AeroSentinel Logo"
            className="h-8 w-auto object-contain rounded group-hover:scale-105 transition-transform"
          />
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-ink text-sm sm:text-base tracking-tight font-sans">
              AeroSentinel
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface border border-line text-muted hidden sm:inline-block">
              v2.4-PROD
            </span>
          </div>
        </div>
      </div>

      {/* Right: Operational Status, Alerts Notification, Role Switcher, Profile, Theme */}
      <div className="flex items-center space-x-2 sm:space-x-3 text-xs">
        {/* System Operational Status Indicator */}
        <div
          onClick={() => onNavigateTab('health')}
          className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded bg-surface border border-line cursor-pointer hover:border-muted transition-colors"
          title="Click to view detailed system health"
        >
          {systemHealthy === true ? (
            <>
              <span className="w-2 h-2 rounded-full bg-[#3FB876] inline-block animate-pulse" />
              <span className="font-mono text-[11px] text-[#3FB876] font-semibold tracking-wider">
                OPERATIONAL
              </span>
            </>
          ) : systemHealthy === false ? (
            <>
              <span className="w-2 h-2 rounded-full bg-[#E0655C] inline-block animate-pulse" />
              <span className="font-mono text-[11px] text-[#E0655C] font-semibold tracking-wider">
                DEGRADED
              </span>
            </>
          ) : (
            <>
              <Activity className="w-3.5 h-3.5 text-muted animate-spin" />
              <span className="font-mono text-[11px] text-muted">CHECKING</span>
            </>
          )}
        </div>

        {/* Notification Bell with Badge */}
        <button
          onClick={() => onNavigateTab('alerts')}
          className="relative p-2 rounded text-muted hover:text-ink hover:bg-hover transition-colors"
          title={`Active Alerts (${activeAlertsCount})`}
          aria-label="View Alerts Feed"
        >
          <Bell className="w-4 h-4" />
          {activeAlertsCount > 0 && (
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[#E0655C] ring-2 ring-panel" />
          )}
        </button>

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded text-muted hover:text-ink hover:bg-hover transition-colors"
          title={theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme'}
          aria-label="Toggle Color Theme"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        <div className="h-5 w-px bg-line hidden sm:block" />

        {/* Role Switcher & Authenticated Profile Dropdown */}
        <div className="relative">
          <button
            onClick={() => setRoleMenuOpen(!roleMenuOpen)}
            disabled={switchingRole}
            className="flex items-center space-x-2 pl-2 pr-2.5 py-1 rounded bg-surface border border-line hover:border-muted text-ink transition-colors"
            title="Switch authenticated demonstration role"
          >
            <div className="w-6 h-6 rounded bg-accent/20 border border-accent/40 flex items-center justify-center text-accent font-mono text-[11px] font-bold">
              {currentUser?.name?.charAt(0) || 'U'}
            </div>
            <div className="text-left hidden md:block">
              <div className="font-medium text-ink text-[11px] truncate max-w-[110px] leading-tight">
                {currentUser?.name?.split(' ')[0] || 'Operator'}
              </div>
              <span
                className={`text-[9px] font-mono px-1 py-0.2 rounded border font-semibold uppercase ${getRoleBadgeColor(
                  currentUser?.role
                )}`}
              >
                {currentUser?.role || 'admin'}
              </span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-muted ml-0.5" />
          </button>

          {/* Role Switcher Menu */}
          {roleMenuOpen && (
            <div className="absolute right-0 top-full mt-1.5 w-60 bg-panel border border-line rounded-lg shadow-xl py-1.5 z-50 font-sans">
              <div className="px-3 py-1.5 border-b border-line text-[10px] font-mono text-muted uppercase tracking-wider">
                Select Active Operator Role
              </div>

              {Object.entries(DEMO_USERS).map(([key, u]) => {
                const isSelected = currentUser?.role === u.role;
                return (
                  <button
                    key={key}
                    onClick={() => handleRoleSwitch(key)}
                    className={`w-full px-3 py-2 text-left flex items-start space-x-2.5 hover:bg-hover transition-colors ${
                      isSelected ? 'bg-accent/10 border-l-2 border-accent' : ''
                    }`}
                  >
                    <Shield className={`w-4 h-4 mt-0.5 shrink-0 ${isSelected ? 'text-accent' : 'text-muted'}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className={`text-xs font-medium truncate ${isSelected ? 'text-accent' : 'text-ink'}`}>
                          {u.name}
                        </span>
                        {isSelected && (
                          <span className="text-[10px] font-mono text-accent font-bold">ACTIVE</span>
                        )}
                      </div>
                      <div className="text-[11px] text-muted truncate">{u.title}</div>
                      <span
                        className={`inline-block mt-1 text-[9px] font-mono px-1 py-0.2 rounded border uppercase ${getRoleBadgeColor(
                          u.role
                        )}`}
                      >
                        {u.role}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
