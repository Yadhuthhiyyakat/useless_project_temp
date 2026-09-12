'use client';

import { useState, useEffect } from 'react';
import { api, type SettingsResponse, type SettingsUpdate } from '@/lib/api';

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [watchedDirs, setWatchedDirs] = useState<string[]>([]);
  const [ignoredDirs, setIgnoredDirs] = useState<string[]>([]);
  const [newWatched, setNewWatched] = useState('');
  const [newIgnored, setNewIgnored] = useState('');
  const [aiEpitaphs, setAiEpitaphs] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      setLoading(true);
      const res = await api.settings.get();
      setSettings(res);
      setWatchedDirs(res.watched_directories);
      setIgnoredDirs(res.ignored_directories);
      setAiEpitaphs(res.ai_epitaphs_enabled);
    } catch (e) {
      console.error('Failed to load settings:', e);
    } finally {
      setLoading(false);
    }
  }

  async function saveSettings() {
    try {
      setSaving(true);
      setMessage(null);
      const update: SettingsUpdate = {
        watched_directories: watchedDirs,
        ignored_directories: ignoredDirs,
        ai_epitaphs_enabled: aiEpitaphs,
      };
      await api.settings.update(update);
      setMessage({ type: 'success', text: 'Settings saved successfully' });
      await loadSettings();
    } catch (e) {
      setMessage({ type: 'error', text: 'Failed to save settings' });
    } finally {
      setSaving(false);
    }
  }

  function addWatched() {
    if (newWatched.trim() && !watchedDirs.includes(newWatched.trim())) {
      setWatchedDirs([...watchedDirs, newWatched.trim()]);
      setNewWatched('');
    }
  }

  function addIgnored() {
    if (newIgnored.trim() && !ignoredDirs.includes(newIgnored.trim())) {
      setIgnoredDirs([...ignoredDirs, newIgnored.trim()]);
      setNewIgnored('');
    }
  }

  function removeWatched(dir: string) {
    setWatchedDirs(watchedDirs.filter(d => d !== dir));
  }

  function removeIgnored(dir: string) {
    setIgnoredDirs(ignoredDirs.filter(d => d !== dir));
  }

  if (loading) {
    return <div className="flex items-center justify-center min-h-[400px]"><div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div></div>;
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-8">Settings</h1>

      {message && (
        <div className={`mb-6 p-4 rounded-lg ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'} border border-green-200 dark:border-green-800`}>
          {message.text}
        </div>
      )}

      <div className="space-y-8">
        {/* AI Epitaphs */}
        <Card title="AI Epitaphs">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={aiEpitaphs}
              onChange={(e) => setAiEpitaphs(e.target.checked)}
              className="h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-gray-700 dark:text-gray-300">Enable AI-generated epitaphs</span>
          </label>
          <p className="text-sm text-gray-500 mt-2">When enabled, the backend will generate AI-powered epitaphs for deaths.</p>
        </Card>

        {/* Watched Directories */}
        <Card title="Watched Directories">
          <p className="text-sm text-gray-500 mb-4">
            Directories that the watcher monitors for file changes. The watcher must have read access.
          </p>
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={newWatched}
              onChange={(e) => setNewWatched(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addWatched()}
              placeholder="/path/to/watch"
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            />
            <button onClick={addWatched} className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm">
              Add
            </button>
          </div>
          {watchedDirs.length === 0 ? (
            <p className="text-sm text-gray-500">No directories being watched</p>
          ) : (
            <ul className="space-y-2">
              {watchedDirs.map((dir, i) => (
                <li key={i} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-md">
                  <span className="font-mono text-sm text-gray-900 dark:text-white">{dir}</span>
                  <button
                    onClick={() => removeWatched(dir)}
                    className="text-red-600 hover:text-red-800 text-sm"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Ignored Directories */}
        <Card title="Ignored Directories">
          <p className="text-sm text-gray-500 mb-4">
            Directories to skip during monitoring. Paths under these will never be tracked.
          </p>
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={newIgnored}
              onChange={(e) => setNewIgnored(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addIgnored()}
              placeholder="/path/to/ignore"
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            />
            <button onClick={addIgnored} className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm">
              Add
            </button>
          </div>
          {ignoredDirs.length === 0 ? (
            <p className="text-sm text-gray-500">No directories ignored</p>
          ) : (
            <ul className="space-y-2">
              {ignoredDirs.map((dir, i) => (
                <li key={i} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-md">
                  <span className="font-mono text-sm text-gray-900 dark:text-white">{dir}</span>
                  <button
                    onClick={() => removeIgnored(dir)}
                    className="text-red-600 hover:text-red-800 text-sm"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={saveSettings}
            disabled={saving}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">{title}</h2>
      {children}
    </div>
  );
}

