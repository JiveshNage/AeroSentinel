import React from 'react';
import {
  LayoutDashboard,
  Map,
  Radio,
  Server,
  ShieldAlert,
  Activity,
  CheckSquare,
  UploadCloud,
  Wrench,
  Users,
  ShieldCheck,
  FileText,
  Sliders,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react';
import { AuthUser, PermissionCode, hasPermission } from '../api/auth';

export type AppNavTab =
  | 'dashboard'
  | 'map'
  | 'live'
  | 'stations'
  | 'detail'
  | 'alerts'
  | 'health'
  | 'tasks'
  | 'upload'
  | 'maintenance'
  | 'admin_users'
  | 'admin_roles'
  | 'admin_audit'
  | 'admin_settings';

interface SidebarItem {
  id: AppNavTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  permission?: PermissionCode;
  badge?: number;
  badgeVariant?: 'red' | 'amber' | 'cyan';
}

interface SidebarSection {
  title: string;
  items: SidebarItem[];
}

interface SidebarProps {
  activeTab: AppNavTab;
  onTabChange: (tab: AppNavTab) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
  currentUser: AuthUser | null;
  activeAlertsCount?: number;
  pendingTasksCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onMobileClose,
  currentUser,
  activeAlertsCount = 0,
  pendingTasksCount = 0,
}) => {
  // Navigation sections structure
  const rawSections: SidebarSection[] = [
    {
      title: 'Overview',
      items: [
        {
          id: 'dashboard',
          label: 'Dashboard',
          icon: LayoutDashboard,
          permission: 'dashboard.view',
        },
        {
          id: 'map',
          label: 'Fleet Map',
          icon: Map,
          permission: 'fleet.view',
        },
      ],
    },
    {
      title: 'Monitoring',
      items: [
        {
          id: 'live',
          label: 'Live Stream',
          icon: Radio,
          permission: 'telemetry.view',
        },
        {
          id: 'stations',
          label: 'Stations',
          icon: Server,
          permission: 'stations.view',
        },
        {
          id: 'alerts',
          label: 'Alerts',
          icon: ShieldAlert,
          permission: 'alerts.view',
          badge: activeAlertsCount,
          badgeVariant: 'red',
        },
        {
          id: 'health',
          label: 'Health',
          icon: Activity,
          permission: 'health.view',
        },
      ],
    },
    {
      title: 'Operations',
      items: [
        {
          id: 'tasks',
          label: 'Tasks',
          icon: CheckSquare,
          // Tasks are role-assigned operational workflows
          permission: 'fleet.view',
          badge: pendingTasksCount,
          badgeVariant: 'amber',
        },
        {
          id: 'upload',
          label: 'Upload Data',
          icon: UploadCloud,
          permission: 'data.upload',
        },
        {
          id: 'maintenance',
          label: 'Maintenance',
          icon: Wrench,
          permission: 'maintenance.view',
        },
      ],
    },
    {
      title: 'Administration',
      items: [
        {
          id: 'admin_users',
          label: 'Users',
          icon: Users,
          permission: 'users.view',
        },
        {
          id: 'admin_roles',
          label: 'Roles & Perms',
          icon: ShieldCheck,
          permission: 'roles.manage',
        },
        {
          id: 'admin_audit',
          label: 'Audit Log',
          icon: FileText,
          permission: 'audit.view',
        },
        {
          id: 'admin_settings',
          label: 'System Settings',
          icon: Sliders,
          permission: 'system.manage',
        },
      ],
    },
  ];

  // Strictly filter navigation items by authenticated user's permissions
  const filteredSections = rawSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => {
        if (!item.permission) return true;
        // Check explicit permission
        if (!hasPermission(currentUser, item.permission)) return false;
        // Special case: viewer does not have operations tasks
        if (currentUser?.role === 'viewer' && item.id === 'tasks') return false;
        return true;
      }),
    }))
    .filter((section) => section.items.length > 0);

  const sidebarContent = (
    <div className="flex flex-col h-full bg-panel select-none">
      {/* Sidebar Header / Brand */}
      <div className="h-14 border-b border-line px-3.5 flex items-center justify-between">
        <div className={`flex items-center space-x-2.5 overflow-hidden transition-all ${collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'}`}>
          <img src="/logo.png" alt="AeroSentinel" className="h-7 w-auto object-contain rounded" />
          <div className="flex flex-col min-w-0">
            <span className="font-semibold text-ink text-sm tracking-tight truncate">AeroSentinel</span>
            <span className="text-[10px] font-mono text-accent truncate">RBAC Operations</span>
          </div>
        </div>

        {/* Mobile close button or desktop collapse button */}
        <button
          onClick={mobileOpen ? onMobileClose : onToggleCollapse}
          className="p-1.5 rounded text-muted hover:text-ink hover:bg-hover transition-colors"
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          aria-label={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {mobileOpen ? (
            <X className="w-4 h-4 text-ink" />
          ) : collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Navigation Sections List */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-3 px-2 space-y-4">
        {filteredSections.map((section) => (
          <div key={section.title} className="space-y-1">
            {/* Section Header */}
            {!collapsed ? (
              <div className="px-2.5 py-1 text-[10px] font-mono font-semibold uppercase tracking-wider text-muted">
                {section.title}
              </div>
            ) : (
              <div className="h-px bg-line my-2 mx-1" />
            )}

            {/* Section Items */}
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id || (item.id === 'stations' && activeTab === 'detail');

              return (
                <div key={item.id} className="relative group">
                  <button
                    onClick={() => {
                      onTabChange(item.id);
                      if (mobileOpen) onMobileClose();
                    }}
                    className={`w-full flex items-center rounded text-left transition-all ${
                      collapsed ? 'justify-center p-2.5' : 'space-x-3 px-3 py-2'
                    } ${
                      isActive
                        ? 'bg-accent/10 text-accent font-medium border-l-2 border-accent shadow-xs'
                        : 'text-muted hover:text-ink hover:bg-hover'
                    }`}
                    title={collapsed ? item.label : undefined}
                    aria-label={item.label}
                  >
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-accent' : 'text-muted group-hover:text-ink'}`} />

                    {!collapsed && (
                      <span className="flex-1 text-xs truncate font-sans">
                        {item.label}
                      </span>
                    )}

                    {/* Badge Counter */}
                    {item.badge !== undefined && item.badge > 0 && (
                      <span
                        className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full font-bold leading-none ${
                          collapsed ? 'absolute top-1 right-1' : ''
                        } ${
                          item.badgeVariant === 'red'
                            ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                            : item.badgeVariant === 'amber'
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            : 'bg-accent/20 text-accent border border-accent/30'
                        }`}
                      >
                        {item.badge > 99 ? '99+' : item.badge}
                      </span>
                    )}
                  </button>

                  {/* Tooltip on hover when collapsed */}
                  {collapsed && (
                    <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 z-50 hidden group-hover:flex items-center space-x-1.5 bg-panel border border-line text-ink text-xs px-2.5 py-1.5 rounded shadow-lg whitespace-nowrap pointer-events-none font-sans">
                      <span>{item.label}</span>
                      {item.badge !== undefined && item.badge > 0 && (
                        <span className="font-mono text-[10px] text-accent font-semibold">({item.badge})</span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Sidebar Footer with Active Role Clearance */}
      <div className="p-3 border-t border-line bg-surface/50 text-[11px] font-mono">
        {!collapsed ? (
          <div className="flex items-center justify-between">
            <span className="text-muted truncate">Clearance:</span>
            <span className="px-1.5 py-0.5 rounded uppercase font-semibold text-[10px] bg-accent/15 text-accent border border-accent/30 truncate max-w-[120px]">
              {currentUser?.role || 'admin'}
            </span>
          </div>
        ) : (
          <div className="flex justify-center" title={`Role: ${currentUser?.role || 'admin'}`}>
            <span className="w-2.5 h-2.5 rounded-full bg-accent" />
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:block shrink-0 border-r border-line transition-all duration-200 z-30 sticky top-0 h-screen ${
          collapsed ? 'w-16' : 'w-60'
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Backdrop & Drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
            onClick={onMobileClose}
          />
          <div className="relative w-64 max-w-[80vw] h-full shadow-2xl z-10">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
};
