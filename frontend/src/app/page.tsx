'use client';

import { useState, useEffect } from 'react';
import { api, type StatisticsResponse, type Death, type WatcherStatusResponse, type SettingsResponse } from '@/lib/api';
import { formatBytes, formatDate } from '@/lib/api';

export default function Dashboard() {
  const [stats, setStats] = useState<StatisticsResponse | null>(null);
  const [recentDeaths, setRecentDeaths] = useState<Death[]>([]);
  const [watcherStatus, setWatcherStatus] = useState<WatcherStatusResponse | null>(null);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAll() {
      try {
        setLoading(true);
        const [statsRes, deathsRes, watcherRes, settingsRes] = await Promise.all([
          api.statistics.get(),
          api.deaths.list({ limit: 5 }),
          api.watcher.status(),
          api.settings.get(),
        ]);
        setStats(statsRes);
        setRecentDeaths(deathsRes.items);
        setWatcherStatus(watcherRes);
        setSettings(settingsRes);
      } catch (e) {
        setError('Failed to load data from backend');
      } finally {
        setLoading(false);
      }
    }
    loadAll();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center p-8">
          <h1 className="text-2xl font-bold text-red-600 mb-4">Error</h1>
          <p className="text-gray-600 dark:text-gray-400">{error}</p>
          <p className="text-sm text-gray-500 mt-2">Make sure the backend is running at http://localhost:8000</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              🪦 Digital Cemetery
            </h1>
            <div className="flex items-center gap-4">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                watcherStatus?.running ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
              }`}>
                {watcherStatus?.running ? '🟢 Watching' : '🔴 Stopped'}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Deaths"
            value={stats?.total_deaths ?? 0}
            icon="💀"
            color="purple"
          />
          <StatCard
            title="Avg Lifespan"
            value={stats?.average_lifespan_seconds ? Math.round(stats.average_lifespan_seconds) + 's' : '0s'}
            icon="⏳"
            color="blue"
          />
          <StatCard
            title="By Extension"
            value={Object.keys(stats?.by_extension ?? {}).length}
            icon="📎"
            color="green"
          />
          <StatCard
            title="Watched Dirs"
            value={settings?.watched_directories.length ?? 0}
            icon="📁"
            color="orange"
          />
        </div>

        {/* Watcher Status & Settings */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <Card title="Watcher Status">
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Status</span>
                <span className={`font-medium ${watcherStatus?.running ? 'text-green-600' : 'text-red-600'}`}>
                  {watcherStatus?.running ? 'Running' : 'Stopped'}
                </span>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400">Watched Directories</span>
                <ul className="mt-1 text-sm text-gray-900 dark:text-white">
                  {watcherStatus?.watched_directories.length === 0 ? (
                    <li className="text-gray-500">None configured</li>
                  ) : (
                    watcherStatus?.watched_directories.map((dir, i) => (
                      <li key={i} className="font-mono text-xs">{dir}</li>
                    ))
                  )}
                </ul>
              </div>
            </div>
          </Card>

          <Card title="Settings">
            <div className="space-y-3">
              <div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={settings?.ai_epitaphs_enabled ?? false}
                    onChange={(e) => updateSetting('ai_epitaphs_enabled', e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">AI Epitaphs</span>
                </label>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400 text-sm">Watched: {settings?.watched_directories.length ?? 0}</span>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400 text-sm">Ignored: {settings?.ignored_directories.length ?? 0}</span>
              </div>
            </div>
          </Card>
        </div>

        {/* Recent Deaths */}
        <Card title="Recent Deaths">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                  <th className="pb-2">File</th>
                  <th className="pb-2">Extension</th>
                  <th className="pb-2">Size</th>
                  <th className="pb-2">Lifespan</th>
                  <th className="pb-2">Cause</th>
                  <th className="pb-2">Deleted</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {recentDeaths.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-gray-500">No deaths recorded yet</td>
                  </tr>
                ) : (
                  recentDeaths.map((death) => (
                    <tr key={death.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="py-3 font-mono text-sm">{death.filename}</td>
                      <td className="py-3">
                        <span className="px-2 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700">
                          {death.extension}
                        </span>
                      </td>
                      <td className="py-3 text-sm">{formatBytes(death.size_bytes)}</td>
                      <td className="py-3 text-sm">{death.lifespan_label}</td>
                      <td className="py-3">
                        <span className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">
                          {death.cause_label}
                        </span>
                      </td>
                      <td className="py-3 text-sm text-gray-500">{formatDate(death.deleted_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </main>
    </div>
  );
}

function StatCard({ title, value, icon, color }: { title: string; value: string | number; icon: string; color: string }) {
  const colorMap: Record<string, string> = {
    purple: 'bg-purple-500',
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    orange: 'bg-orange-500',
  };
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
        </div>
        <div className={`${colorMap[color]} text-white p-3 rounded-lg text-2xl`}>
          {icon}
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

async function updateSetting(key: string, value: boolean) {
  try {
    await api.settings.update({ [key]: value });
    window.location.reload();
  } catch (e) {
    console.error('Failed to update setting:', e);
  }
}

