'use client';

import { useState, useEffect } from 'react';
import { api, type SettingsResponse, type SettingsUpdate, type WatcherStatusResponse } from '@/lib/api';

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [watcherStatus, setWatcherStatus] = useState<WatcherStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [watchedDirs, setWatchedDirs] = useState<string[]>([]);
  const [ignoredDirs, setIgnoredDirs] = useState<string[]>([]);
  const [newWatched, setNewWatched] = useState('');
  const [newIgnored, setNewIgnored] = useState('');
  const [aiEpitaphs, setAiEpitaphs] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    try {
      setLoading(true);
      const [settingsRes, watcherRes] = await Promise.all([
        api.settings.get(),
        api.watcher.status().catch(() => null),
      ]);
      setSettings(settingsRes);
      setWatchedDirs(settingsRes.watched_directories);
      setIgnoredDirs(settingsRes.ignored_directories);
      setAiEpitaphs(settingsRes.ai_epitaphs_enabled);
      if (watcherRes) {
        setWatcherStatus(watcherRes);
      }
    } catch (e) {
      console.error('Failed to load settings:', e);
      setMessage({ type: 'error', text: 'Could not connect to backend to load settings' });
    } finally {
      setLoading(false);
    }
  }

  async function persistSettings(dirsToWatch: string[], dirsToIgnore: string[], epitaphsVal: boolean) {
    try {
      setSaving(true);
      setMessage(null);
      const update: SettingsUpdate = {
        watched_directories: dirsToWatch,
        ignored_directories: dirsToIgnore,
        ai_epitaphs_enabled: epitaphsVal,
      };
      const res = await api.settings.update(update);
      setSettings(res);
      setWatchedDirs(res.watched_directories);
      setIgnoredDirs(res.ignored_directories);
      setAiEpitaphs(res.ai_epitaphs_enabled);

      // Refresh watcher status
      const updatedWatcher = await api.watcher.status().catch(() => null);
      if (updatedWatcher) {
        setWatcherStatus(updatedWatcher);
      }

      setMessage({
        type: 'success',
        text: 'Settings successfully saved and live filesystem watcher reconfigured!',
      });
    } catch (e: any) {
      const errMsg = e?.body?.detail || e?.message || 'Failed to save settings';
      setMessage({ type: 'error', text: String(errMsg) });
    } finally {
      setSaving(false);
    }
  }

  function handleAddWatched(pathToWatch?: string) {
    const target = (pathToWatch || newWatched).trim();
    if (!target) return;
    if (watchedDirs.includes(target)) {
      setMessage({ type: 'error', text: `Directory "${target}" is already being watched.` });
      return;
    }
    const updated = [...watchedDirs, target];
    setWatchedDirs(updated);
    setNewWatched('');
    // Auto-save so user doesn't have to manually click save
    persistSettings(updated, ignoredDirs, aiEpitaphs);
  }

  function handleRemoveWatched(dir: string) {
    const updated = watchedDirs.filter((d) => d !== dir);
    setWatchedDirs(updated);
    persistSettings(updated, ignoredDirs, aiEpitaphs);
  }

  function handleAddIgnored() {
    const target = newIgnored.trim();
    if (!target) return;
    if (ignoredDirs.includes(target)) {
      setMessage({ type: 'error', text: `Directory "${target}" is already in ignore list.` });
      return;
    }
    const updated = [...ignoredDirs, target];
    setIgnoredDirs(updated);
    setNewIgnored('');
    persistSettings(watchedDirs, updated, aiEpitaphs);
  }

  function handleRemoveIgnored(dir: string) {
    const updated = ignoredDirs.filter((d) => d !== dir);
    setIgnoredDirs(updated);
    persistSettings(watchedDirs, updated, aiEpitaphs);
  }

  function handleToggleAiEpitaphs(enabled: boolean) {
    setAiEpitaphs(enabled);
    persistSettings(watchedDirs, ignoredDirs, enabled);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[500px]">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-500 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
            <span>⚙️</span>
            <span>Filesystem & Cemetery Settings</span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Configure folders monitored by the Digital Cemetery. No .env edits required; all changes apply and persist instantly.
          </p>
        </div>

        <a
          href="/graveyard"
          className="self-start sm:self-auto inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-zinc-900 hover:bg-zinc-800 text-zinc-100 dark:bg-zinc-800 dark:hover:bg-zinc-700 border border-zinc-700 shadow-sm transition"
        >
          <span>🪦</span>
          <span>View Graveyard</span>
        </a>
      </div>

      {/* Live Watcher Status Banner */}
      <div className="mb-8 p-4 rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            {watcherStatus?.running && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            )}
            <span
              className={`relative inline-flex rounded-full h-3 w-3 ${
                watcherStatus?.running ? 'bg-emerald-500' : 'bg-red-500'
              }`}
            ></span>
          </span>
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
              {watcherStatus?.running ? 'Filesystem Watcher is Active' : 'Watcher is Inactive'}
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Monitoring {watcherStatus?.watched_directories?.length || 0} active directory tree(s) in real-time
            </p>
          </div>
        </div>

        {saving && (
          <div className="flex items-center gap-2 text-xs text-indigo-600 dark:text-indigo-400 font-medium">
            <div className="animate-spin h-3.5 w-3.5 border-2 border-indigo-500 border-t-transparent rounded-full" />
            <span>Updating configuration...</span>
          </div>
        )}
      </div>

      {/* Message Banner */}
      {message && (
        <div
          className={`mb-6 p-4 rounded-2xl text-sm border flex items-center justify-between gap-3 ${
            message.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200 border-emerald-300 dark:border-emerald-800'
              : 'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-200 border-red-300 dark:border-red-800'
          }`}
        >
          <div className="flex items-center gap-2">
            <span>{message.type === 'success' ? '✅' : '⚠️'}</span>
            <span>{message.text}</span>
          </div>
          <button
            onClick={() => setMessage(null)}
            className="text-xs opacity-70 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      )}

      <div className="space-y-8">
        {/* Watched Directories */}
        <Card title="📁 Watched Directories (Digital Cemetery Grounds)">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 leading-relaxed">
            Specify directories you want the Digital Cemetery to monitor. When files or folders inside these directories are deleted, a death is confirmed, metadata is recorded, and an eternal domestone is inscribed in the graveyard.
          </p>

          {/* Quick Presets */}
          <div className="mb-4">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 block mb-2 uppercase tracking-wider">
              Quick Suggestions:
            </span>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setNewWatched('/home/yadhukrishnatm/Desktop')}
                className="px-3 py-1.5 rounded-lg text-xs font-mono bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 border border-gray-300 dark:border-gray-600 transition"
              >
                🖥️ Desktop
              </button>
              <button
                type="button"
                onClick={() => setNewWatched('/home/yadhukrishnatm/Downloads')}
                className="px-3 py-1.5 rounded-lg text-xs font-mono bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 border border-gray-300 dark:border-gray-600 transition"
              >
                📥 Downloads
              </button>
              <button
                type="button"
                onClick={() => setNewWatched('/home/yadhukrishnatm/Documents')}
                className="px-3 py-1.5 rounded-lg text-xs font-mono bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 border border-gray-300 dark:border-gray-600 transition"
              >
                📄 Documents
              </button>
              <button
                type="button"
                onClick={() => setNewWatched('/home/yadhukrishnatm/Projects/Useless/useless_project_temp/cemetery_playground')}
                className="px-3 py-1.5 rounded-lg text-xs font-mono bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:hover:bg-indigo-900/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 transition"
              >
                🧪 Project Playground Folder
              </button>
            </div>
          </div>

          {/* Add Input Bar */}
          <div className="flex flex-col sm:flex-row gap-2 mb-6">
            <input
              type="text"
              value={newWatched}
              onChange={(e) => setNewWatched(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddWatched()}
              placeholder="Enter absolute directory path (e.g. /home/user/Desktop)..."
              className="flex-1 px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white font-mono text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
            <button
              onClick={() => handleAddWatched()}
              disabled={saving || !newWatched.trim()}
              className="px-6 py-2.5 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm shadow transition"
            >
              Add & Watch Directory
            </button>
          </div>

          {/* Watched Dirs List */}
          {watchedDirs.length === 0 ? (
            <div className="p-8 text-center bg-gray-50 dark:bg-gray-900/50 rounded-xl border border-dashed border-gray-300 dark:border-gray-700">
              <span className="text-3xl block mb-2">📁</span>
              <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                No directories are currently monitored
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Add a directory path above to begin watching for file creations and departures.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {watchedDirs.map((dir, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900/60 rounded-xl border border-gray-200 dark:border-gray-700"
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <span className="text-xl flex-shrink-0">📂</span>
                    <div className="overflow-hidden">
                      <span className="font-mono text-xs sm:text-sm font-semibold text-gray-900 dark:text-white block truncate" title={dir}>
                        {dir}
                      </span>
                      <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        Active & Monitored
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleRemoveWatched(dir)}
                    disabled={saving}
                    className="ml-4 px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-50 hover:bg-red-100 text-red-700 dark:bg-red-950/50 dark:hover:bg-red-900/60 dark:text-red-300 border border-red-200 dark:border-red-800 transition"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Ignored Directories */}
        <Card title="🚫 Ignored Directories">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 leading-relaxed">
            Directories to always exclude from tracking (e.g. caches, temp builds, or noisy folders). Files inside these paths will never create records in the cemetery.
          </p>

          <div className="flex flex-col sm:flex-row gap-2 mb-4">
            <input
              type="text"
              value={newIgnored}
              onChange={(e) => setNewIgnored(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddIgnored()}
              placeholder="/path/to/ignore..."
              className="flex-1 px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white font-mono text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
            <button
              onClick={() => handleAddIgnored()}
              disabled={saving || !newIgnored.trim()}
              className="px-6 py-2.5 bg-gray-800 dark:bg-gray-700 text-white font-semibold rounded-xl hover:bg-gray-700 dark:hover:bg-gray-600 disabled:opacity-50 text-sm shadow transition"
            >
              Add Ignored
            </button>
          </div>

          {ignoredDirs.length === 0 ? (
            <p className="text-xs text-gray-500">No directories currently ignored.</p>
          ) : (
            <div className="space-y-2">
              {ignoredDirs.map((dir, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900/60 rounded-xl border border-gray-200 dark:border-gray-700"
                >
                  <span className="font-mono text-xs text-gray-700 dark:text-gray-300 truncate" title={dir}>
                    {dir}
                  </span>
                  <button
                    onClick={() => handleRemoveIgnored(dir)}
                    disabled={saving}
                    className="text-red-600 hover:text-red-700 dark:text-red-400 text-xs font-semibold"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* AI Epitaphs */}
        <Card title="🪦 AI Epitaph Generation">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={aiEpitaphs}
              onChange={(e) => handleToggleAiEpitaphs(e.target.checked)}
              disabled={saving}
              className="h-5 w-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <div>
              <span className="font-semibold text-gray-900 dark:text-white text-sm block">
                Enable AI-generated epitaphs
              </span>
              <span className="text-xs text-gray-500 dark:text-gray-400">
                When enabled, deceased files receive a uniquely crafted eulogy inscribed onto their marble domestone.
              </span>
            </div>
          </label>
        </Card>
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">{title}</h2>
      {children}
    </div>
  );
}
