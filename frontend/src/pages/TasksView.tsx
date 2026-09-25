import React, { useState, useEffect, useCallback } from 'react';
import {
  CheckSquare,
  Shield,
  CheckCircle2,
  Play,
  RotateCcw,
  Plus,
  Search,
  User,
  MapPin,
  Calendar,
  Trash2,
} from 'lucide-react';
import { fetchTasks, createTask, updateTask, deleteTask, SystemTask } from '../api/tasks';
import { fetchStations } from '../api/stations';
import { AuthUser } from '../api/auth';

interface TasksViewProps {
  currentUser: AuthUser | null;
  onInspectStation: (stationCode: string) => void;
}

const ROLE_LABELS: Record<string, { title: string; color: string; desc: string }> = {
  admin: {
    title: 'Admin (System Governance)',
    color: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    desc: 'Fleet governance, model retraining, architecture integrity & access audits.',
  },
  data_quality_officer: {
    title: 'Data Quality Officer (QC)',
    color: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    desc: 'Sensor anomaly triage, false alarm validation, spatial cross-correlation & label corrections.',
  },
  field_technician: {
    title: 'Field Maintenance Technician',
    color: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    desc: 'Hardware recalibration, battery & solar array service, mast leveling & sensor swap dispatches.',
  },
  forecaster: {
    title: 'Regional Forecaster',
    color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    desc: 'Synoptic weather squall tracking, heatwave boundary monitoring & micro-climate bulletins.',
  },
};

const PRIORITY_BADGES: Record<string, { label: string; class: string }> = {
  critical: { label: 'CRITICAL', class: 'bg-status-anomalous text-white font-bold' },
  high: { label: 'HIGH', class: 'bg-amber-500/20 text-amber-400 border border-amber-500/40' },
  medium: { label: 'MEDIUM', class: 'bg-blue-500/20 text-blue-400 border border-blue-500/40' },
  low: { label: 'LOW', class: 'bg-surface text-muted border border-line' },
};

export const TasksView: React.FC<TasksViewProps> = ({ currentUser, onInspectStation }) => {
  const [tasks, setTasks] = useState<SystemTask[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedRoleTab, setSelectedRoleTab] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // New task modal
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newTaskTitle, setNewTaskTitle] = useState<string>('');
  const [newTaskDesc, setNewTaskDesc] = useState<string>('');
  const [newTaskRole, setNewTaskRole] = useState<string>(currentUser?.role || 'data_quality_officer');
  const [newTaskPriority, setNewTaskPriority] = useState<string>('medium');
  const [newTaskStation, setNewTaskStation] = useState<string>('NCR001');
  const [newTaskDueDate, setNewTaskDueDate] = useState<string>('');
  const [creating, setCreating] = useState<boolean>(false);

  useEffect(() => {
    fetchStations()
      .then((res) => {
        if (res && res.stations && res.stations.length > 0) {
          setNewTaskStation((prev) => {
            if (prev && res.stations.some((s) => s.station_code === prev)) return prev;
            return res.stations[0].station_code;
          });
        }
      })
      .catch(() => {});
  }, []);

  const activeRole = currentUser?.role || 'admin';
  const isAdmin = activeRole === 'admin';

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTasks({
        role: selectedRoleTab === 'all' ? undefined : selectedRoleTab,
        status: statusFilter === 'all' ? undefined : statusFilter,
        priority: priorityFilter === 'all' ? undefined : priorityFilter,
      });
      setTasks(data.tasks);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch tasks');
    } finally {
      setLoading(false);
    }
  }, [selectedRoleTab, statusFilter, priorityFilter]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const handleStatusChange = async (taskId: string, newStatus: 'pending' | 'in_progress' | 'completed') => {
    try {
      await updateTask(taskId, {
        status: newStatus,
        assigned_to_name: currentUser?.name || 'Operator',
      });
      loadTasks();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to update task');
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    if (!window.confirm('Are you sure you want to remove this operational task?')) return;
    try {
      await deleteTask(taskId);
      loadTasks();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete task');
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim() || !newTaskDesc.trim()) return;
    setCreating(true);
    try {
      await createTask({
        title: newTaskTitle.trim(),
        description: newTaskDesc.trim(),
        assigned_role: newTaskRole,
        priority: newTaskPriority,
        station_code: newTaskStation.trim().toUpperCase() || undefined,
        assigned_to_name: currentUser?.name,
        due_date: newTaskDueDate || undefined,
      });
      setShowCreateModal(false);
      setNewTaskTitle('');
      setNewTaskDesc('');
      loadTasks();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create task');
    } finally {
      setCreating(false);
    }
  };

  const filteredTasks = tasks.filter((t) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      t.title.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      (t.station_code && t.station_code.toLowerCase().includes(q))
    );
  });

  const pendingCount = tasks.filter((t) => t.status === 'pending').length;
  const inProgCount = tasks.filter((t) => t.status === 'in_progress').length;
  const compCount = tasks.filter((t) => t.status === 'completed').length;

  return (
    <div className="space-y-6">
      {/* RBAC Header & Role Clearance Banner */}
      <div className="bg-panel border border-line rounded-lg p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[0.75rem] font-mono uppercase tracking-wider text-accent font-semibold flex items-center space-x-1">
                <Shield className="w-3.5 h-3.5" />
                <span>Role-Based Access Control (RBAC)</span>
              </span>
              <span className="text-line">•</span>
              <span className="text-[0.75rem] font-mono text-muted">Operational Task Division</span>
            </div>
            <h2 className="text-[1.25rem] font-semibold text-ink mt-1 font-sans">
              Operational Task Queue & Workflow Board
            </h2>
            <p className="text-[0.8125rem] text-muted mt-1 max-w-3xl font-sans">
              Tasks are partitioned strictly by operational roles. Switch roles in the top navbar
              to experience role-gated action permissions.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-accent text-white text-xs font-semibold hover:bg-accent/90 shadow-sm transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Task</span>
            </button>
            <button
              onClick={loadTasks}
              className="px-3 py-1.5 rounded bg-surface border border-line text-ink text-xs font-medium hover:bg-panel transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Active Role Notice */}
        <div className="mt-4 pt-4 border-t border-line flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center space-x-2">
            <span className="text-muted font-mono">Current User:</span>
            <span className="font-semibold text-ink flex items-center space-x-1">
              <User className="w-3 h-3 text-accent" />
              <span>{currentUser?.name || 'Dr. R. Sharma'}</span>
            </span>
            <span className={`px-2 py-0.5 rounded font-mono text-[0.6875rem] border ${ROLE_LABELS[activeRole]?.color || 'bg-surface'}`}>
              {ROLE_LABELS[activeRole]?.title || activeRole}
            </span>
          </div>

          <div className="text-muted text-[0.75rem]">
            {ROLE_LABELS[activeRole]?.desc}
          </div>
        </div>
      </div>

      {/* Role Tabs & Filters Bar */}
      <div className="bg-panel border border-line rounded-lg p-3 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Department Tabs */}
          <div className="flex items-center space-x-1 overflow-x-auto py-1 scrollbar-none">
            <button
              onClick={() => setSelectedRoleTab('all')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                selectedRoleTab === 'all'
                  ? 'bg-accent text-white'
                  : 'text-muted hover:text-ink hover:bg-surface'
              }`}
            >
              All Roles ({tasks.length})
            </button>
            <button
              onClick={() => setSelectedRoleTab('admin')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                selectedRoleTab === 'admin'
                  ? 'bg-accent text-white'
                  : 'text-muted hover:text-ink hover:bg-surface'
              }`}
            >
              Admin Governance
            </button>
            <button
              onClick={() => setSelectedRoleTab('data_quality_officer')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                selectedRoleTab === 'data_quality_officer'
                  ? 'bg-accent text-white'
                  : 'text-muted hover:text-ink hover:bg-surface'
              }`}
            >
              QC Triage (DQO)
            </button>
            <button
              onClick={() => setSelectedRoleTab('field_technician')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                selectedRoleTab === 'field_technician'
                  ? 'bg-accent text-white'
                  : 'text-muted hover:text-ink hover:bg-surface'
              }`}
            >
              Field Maintenance
            </button>
            <button
              onClick={() => setSelectedRoleTab('forecaster')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                selectedRoleTab === 'forecaster'
                  ? 'bg-accent text-white'
                  : 'text-muted hover:text-ink hover:bg-surface'
              }`}
            >
              Forecaster
            </button>
          </div>

          {/* Quick Status KPIs */}
          <div className="flex items-center space-x-2 text-[0.75rem] font-mono">
            <span className="px-2 py-0.5 rounded bg-surface border border-line text-muted">
              Pending: <strong className="text-amber-400">{pendingCount}</strong>
            </span>
            <span className="px-2 py-0.5 rounded bg-surface border border-line text-muted">
              In Progress: <strong className="text-blue-400">{inProgCount}</strong>
            </span>
            <span className="px-2 py-0.5 rounded bg-surface border border-line text-muted">
              Done: <strong className="text-status-valid">{compCount}</strong>
            </span>
          </div>
        </div>

        {/* Filter & Search Controls */}
        <div className="pt-2 border-t border-line flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center space-x-2 flex-1 max-w-sm">
            <Search className="w-3.5 h-3.5 text-muted" />
            <input
              type="text"
              placeholder="Search tasks, descriptions, or stations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-surface border border-line rounded px-2.5 py-1 text-ink focus:outline-none focus:border-accent w-full text-xs"
            />
          </div>

          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1.5">
              <span className="text-muted font-mono">Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-surface border border-line rounded px-2 py-1 text-ink focus:outline-none cursor-pointer text-xs"
              >
                <option value="all">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
              </select>
            </div>

            <div className="flex items-center space-x-1.5">
              <span className="text-muted font-mono">Priority:</span>
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="bg-surface border border-line rounded px-2 py-1 text-ink focus:outline-none cursor-pointer text-xs"
              >
                <option value="all">All Priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Task Cards Grid */}
      {loading ? (
        <div className="p-12 text-center text-muted text-xs font-mono">
          Loading role-partitioned tasks...
        </div>
      ) : error ? (
        <div className="p-6 bg-status-anomalous/10 border border-status-anomalous text-status-anomalous rounded text-xs font-mono">
          {error}
        </div>
      ) : filteredTasks.length === 0 ? (
        <div className="bg-panel border border-line rounded-lg p-12 text-center">
          <CheckSquare className="w-8 h-8 text-muted mx-auto mb-2 opacity-50" />
          <h4 className="text-sm font-semibold text-ink">No tasks found</h4>
          <p className="text-xs text-muted mt-1">
            No operational tasks match the selected role or filter criteria.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTasks.map((t) => {
            const isAssignedToUserRole = isAdmin || t.assigned_role === activeRole;
            const priorityBadge = PRIORITY_BADGES[t.priority] || PRIORITY_BADGES.medium;
            const roleInfo = ROLE_LABELS[t.assigned_role] || {
              title: t.assigned_role,
              color: 'bg-surface text-muted border-line',
            };

            return (
              <div
                key={t.id}
                className={`bg-panel border rounded-lg p-4 flex flex-col justify-between transition-all duration-200 shadow-xs ${
                  t.status === 'completed'
                    ? 'border-line/60 opacity-80'
                    : t.priority === 'critical'
                    ? 'border-status-anomalous/40 hover:border-status-anomalous'
                    : 'border-line hover:border-accent/40'
                }`}
              >
                <div>
                  {/* Top Bar: Role & Priority */}
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className={`px-2 py-0.5 rounded text-[0.625rem] font-mono border ${roleInfo.color}`}>
                      {roleInfo.title.split(' ')[0]}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[0.625rem] font-mono ${priorityBadge.class}`}>
                      {priorityBadge.label}
                    </span>
                  </div>

                  {/* Title & Station Link */}
                  <h3 className="text-[0.9375rem] font-semibold text-ink font-sans leading-snug">
                    {t.title}
                  </h3>

                  {t.station_code && (
                    <button
                      onClick={() => onInspectStation(t.station_code!)}
                      className="mt-1.5 inline-flex items-center space-x-1 text-[0.6875rem] font-mono text-accent hover:underline bg-accent/10 px-2 py-0.5 rounded"
                    >
                      <MapPin className="w-3 h-3" />
                      <span>Station: {t.station_code}</span>
                    </button>
                  )}

                  {/* Description */}
                  <p className="text-[0.8125rem] text-muted mt-2 font-sans line-clamp-3">
                    {t.description}
                  </p>

                  {/* Notes if available */}
                  {t.notes && (
                    <div className="mt-2.5 p-2 rounded bg-surface border border-line text-[0.75rem] font-sans text-muted">
                      <span className="font-semibold text-ink block text-[0.6875rem] font-mono">
                        Operator Notes:
                      </span>
                      {t.notes}
                    </div>
                  )}
                </div>

                {/* Footer: Assignee, Due Date & Actions */}
                <div className="mt-4 pt-3 border-t border-line space-y-3">
                  <div className="flex items-center justify-between text-[0.6875rem] font-mono text-muted">
                    <span className="flex items-center space-x-1">
                      <User className="w-3 h-3" />
                      <span>{t.assigned_to_name || 'Unassigned'}</span>
                    </span>
                    {t.due_date && (
                      <span className="flex items-center space-x-1">
                        <Calendar className="w-3 h-3" />
                        <span>Due: {t.due_date}</span>
                      </span>
                    )}
                  </div>

                  {/* Action Buttons with RBAC Clearance Check */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center space-x-1.5">
                      {t.status === 'pending' ? (
                        <button
                          disabled={!isAssignedToUserRole}
                          onClick={() => handleStatusChange(t.id, 'in_progress')}
                          title={!isAssignedToUserRole ? `Requires ${roleInfo.title} role` : undefined}
                          className={`flex items-center space-x-1 px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                            isAssignedToUserRole
                              ? 'bg-blue-600 text-white hover:bg-blue-500'
                              : 'bg-surface border border-line text-muted cursor-not-allowed opacity-60'
                          }`}
                        >
                          <Play className="w-3 h-3" />
                          <span>Start Work</span>
                        </button>
                      ) : t.status === 'in_progress' ? (
                        <button
                          disabled={!isAssignedToUserRole}
                          onClick={() => handleStatusChange(t.id, 'completed')}
                          title={!isAssignedToUserRole ? `Requires ${roleInfo.title} role` : undefined}
                          className={`flex items-center space-x-1 px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                            isAssignedToUserRole
                              ? 'bg-status-valid text-white hover:bg-status-valid/90'
                              : 'bg-surface border border-line text-muted cursor-not-allowed opacity-60'
                          }`}
                        >
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Complete</span>
                        </button>
                      ) : (
                        <button
                          disabled={!isAssignedToUserRole}
                          onClick={() => handleStatusChange(t.id, 'in_progress')}
                          className="flex items-center space-x-1 px-2 py-1 rounded text-xs text-muted hover:text-ink bg-surface border border-line"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Reopen</span>
                        </button>
                      )}

                      {/* Status indicator pill */}
                      <span
                        className={`text-[0.625rem] font-mono px-2 py-0.5 rounded font-semibold ${
                          t.status === 'completed'
                            ? 'text-status-valid bg-status-valid/10'
                            : t.status === 'in_progress'
                            ? 'text-blue-400 bg-blue-500/10'
                            : 'text-amber-400 bg-amber-500/10'
                        }`}
                      >
                        {t.status.toUpperCase().replace('_', ' ')}
                      </span>
                    </div>

                    {isAdmin && (
                      <button
                        onClick={() => handleDeleteTask(t.id)}
                        className="p-1 rounded text-muted hover:text-status-anomalous hover:bg-status-anomalous/10 transition-colors"
                        title="Delete task (Admin only)"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Task Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-panel border border-line rounded-lg max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <h3 className="text-base font-semibold text-ink font-sans flex items-center space-x-2">
                <CheckSquare className="w-4 h-4 text-accent" />
                <span>Create Operational Task</span>
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-muted hover:text-ink text-sm font-mono"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-4 text-xs font-sans">
              <div>
                <label className="block text-muted font-medium mb-1">Task Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Inspect barometric pressure drift on Safdarjung"
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  className="w-full bg-surface border border-line rounded px-3 py-1.5 text-ink focus:outline-none focus:border-accent text-xs"
                />
              </div>

              <div>
                <label className="block text-muted font-medium mb-1">Description</label>
                <textarea
                  required
                  rows={3}
                  placeholder="Detailed instructions, anomaly threshold violation, or maintenance protocol..."
                  value={newTaskDesc}
                  onChange={(e) => setNewTaskDesc(e.target.value)}
                  className="w-full bg-surface border border-line rounded px-3 py-1.5 text-ink focus:outline-none focus:border-accent text-xs resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted font-medium mb-1">Assigned Role</label>
                  <select
                    value={newTaskRole}
                    onChange={(e) => setNewTaskRole(e.target.value)}
                    className="w-full bg-surface border border-line rounded px-2.5 py-1.5 text-ink focus:outline-none cursor-pointer text-xs"
                  >
                    <option value="data_quality_officer">Data Quality Officer (QC)</option>
                    <option value="field_technician">Field Maintenance Technician</option>
                    <option value="forecaster">Regional Forecaster</option>
                    <option value="admin">System Administrator</option>
                  </select>
                </div>

                <div>
                  <label className="block text-muted font-medium mb-1">Priority</label>
                  <select
                    value={newTaskPriority}
                    onChange={(e) => setNewTaskPriority(e.target.value)}
                    className="w-full bg-surface border border-line rounded px-2.5 py-1.5 text-ink focus:outline-none cursor-pointer text-xs"
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted font-medium mb-1">Station Code (Optional)</label>
                  <input
                    type="text"
                    placeholder="e.g. NCR001"
                    value={newTaskStation}
                    onChange={(e) => setNewTaskStation(e.target.value)}
                    className="w-full bg-surface border border-line rounded px-3 py-1.5 text-ink focus:outline-none focus:border-accent text-xs uppercase"
                  />
                </div>

                <div>
                  <label className="block text-muted font-medium mb-1">Due Date</label>
                  <input
                    type="date"
                    value={newTaskDueDate}
                    onChange={(e) => setNewTaskDueDate(e.target.value)}
                    className="w-full bg-surface border border-line rounded px-3 py-1.5 text-ink focus:outline-none focus:border-accent text-xs"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-line">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 rounded bg-surface border border-line text-ink hover:bg-panel transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-1.5 rounded bg-accent text-white font-semibold hover:bg-accent/90 transition-colors shadow-sm disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create Task'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
