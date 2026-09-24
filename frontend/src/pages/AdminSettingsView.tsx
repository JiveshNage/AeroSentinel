import React, { useEffect, useState } from 'react';
import { Sliders, Save, RefreshCw } from 'lucide-react';
import { fetchSystemSettings, updateSystemSetting, SystemSettingItem } from '../api/admin';

export const AdminSettingsView: React.FC = () => {
  const [settings, setSettings] = useState<SystemSettingItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSystemSettings();
      setSettings(data);
      const initialMap: Record<string, string> = {};
      data.forEach((s) => {
        initialMap[s.key] = s.value?.value !== undefined ? String(s.value.value) : JSON.stringify(s.value);
      });
      setEditValues(initialMap);
    } catch (e: any) {
      setError(e.message || 'Failed to load system settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleSave = async (key: string, originalItem: SystemSettingItem) => {
    setSavingKey(key);
    setError(null);
    try {
      const rawVal = editValues[key];
      let parsedVal: any = rawVal;

      if (rawVal === 'true') parsedVal = true;
      else if (rawVal === 'false') parsedVal = false;
      else if (!isNaN(Number(rawVal)) && rawVal.trim() !== '') parsedVal = Number(rawVal);

      await updateSystemSetting(
        key,
        { value: parsedVal, type: typeof parsedVal },
        originalItem.description || undefined
      );

      setStatusMessage(`Setting '${key}' updated successfully.`);
      loadSettings();
      setTimeout(() => setStatusMessage(null), 3500);
    } catch (e: any) {
      setError(e.message || 'Failed to save setting');
    } finally {
      setSavingKey(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-panel border border-line rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-accent/15 border border-accent/30 text-accent">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-ink">System Configuration & ML Hyperparameters</h2>
              <p className="text-xs text-muted mt-0.5">
                Runtime configuration flags, IsolationForest contamination, KDTree neighbor limits, and pipeline controls.
              </p>
            </div>
          </div>

          <button
            onClick={loadSettings}
            className="px-3 py-1.5 rounded bg-surface border border-line hover:border-muted text-ink text-xs font-mono flex items-center space-x-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-muted ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {statusMessage && (
          <div className="mt-3 p-2.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            {statusMessage}
          </div>
        )}

        {error && (
          <div className="mt-3 p-2.5 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono">
            {error}
          </div>
        )}
      </div>

      {/* Settings Grid */}
      <div className="bg-panel border border-line rounded-lg overflow-hidden">
        <div className="p-4 border-b border-line flex items-center justify-between">
          <span className="text-xs font-semibold text-ink font-mono uppercase tracking-wider">
            Operational Parameters ({settings.length})
          </span>
          <span className="text-[11px] font-mono text-muted">Protected System Domain</span>
        </div>

        <div className="divide-y divide-line">
          {settings.map((s) => (
            <div key={s.key} className="p-4 hover:bg-hover/20 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1 max-w-xl">
                <span className="font-mono text-xs font-bold text-accent">{s.key}</span>
                <p className="text-xs text-muted font-sans">{s.description}</p>
                <div className="text-[10px] font-mono text-muted">
                  Last updated by: <span className="text-ink">{s.updated_by || 'system'}</span> · {new Date(s.updated_at).toLocaleString()}
                </div>
              </div>

              <div className="flex items-center space-x-2 shrink-0">
                <input
                  type="text"
                  value={editValues[s.key] !== undefined ? editValues[s.key] : ''}
                  onChange={(e) =>
                    setEditValues({ ...editValues, [s.key]: e.target.value })
                  }
                  className="px-3 py-1.5 rounded bg-surface border border-line text-ink font-mono text-xs focus:border-accent outline-hidden w-44"
                />

                <button
                  onClick={() => handleSave(s.key, s)}
                  disabled={savingKey === s.key}
                  className="px-3 py-1.5 rounded bg-accent text-white font-medium text-xs flex items-center space-x-1.5 hover:opacity-90 disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{savingKey === s.key ? 'Saving...' : 'Save'}</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
