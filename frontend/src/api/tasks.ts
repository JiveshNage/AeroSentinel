/**
 * tasks.ts — Client API for Role-Based Task Management & RBAC Workflows
 */

export interface SystemTask {
  id: string;
  title: string;
  description: string;
  assigned_role: 'admin' | 'data_quality_officer' | 'field_technician' | 'forecaster' | string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  status: 'pending' | 'in_progress' | 'completed';
  category: string;
  station_code?: string | null;
  assigned_to_name?: string | null;
  due_date?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  total: number;
  pending_count: number;
  in_progress_count: number;
  completed_count: number;
  tasks: SystemTask[];
}

export interface TaskCreatePayload {
  title: string;
  description: string;
  assigned_role: string;
  priority?: string;
  status?: string;
  category?: string;
  station_code?: string;
  assigned_to_name?: string;
  due_date?: string;
  notes?: string;
}

export interface TaskUpdatePayload {
  title?: string;
  description?: string;
  assigned_role?: string;
  priority?: string;
  status?: string;
  category?: string;
  station_code?: string;
  assigned_to_name?: string;
  due_date?: string;
  notes?: string;
}

export async function fetchTasks(params?: {
  role?: string;
  status?: string;
  priority?: string;
  station_code?: string;
}): Promise<TaskListResponse> {
  const query = new URLSearchParams();
  if (params?.role && params.role !== 'all') query.set('role', params.role);
  if (params?.status && params.status !== 'all') query.set('status', params.status);
  if (params?.priority && params.priority !== 'all') query.set('priority', params.priority);
  if (params?.station_code && params.station_code !== 'all') query.set('station_code', params.station_code);

  const res = await fetch(`/api/tasks?${query.toString()}`);
  if (!res.ok) {
    throw new Error(`Failed to load tasks (${res.status})`);
  }
  return res.json();
}

export async function createTask(payload: TaskCreatePayload): Promise<SystemTask> {
  const res = await fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create task (${res.status})`);
  }
  return res.json();
}

export async function updateTask(id: string, payload: TaskUpdatePayload): Promise<SystemTask> {
  const res = await fetch(`/api/tasks/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update task (${res.status})`);
  }
  return res.json();
}

export async function deleteTask(id: string): Promise<void> {
  const res = await fetch(`/api/tasks/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete task (${res.status})`);
  }
}
