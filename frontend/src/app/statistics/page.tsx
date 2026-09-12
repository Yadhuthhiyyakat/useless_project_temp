'use client';

import { useState, useEffect } from 'react';
import { api, type StatisticsResponse } from '@/lib/api';

export default function StatisticsPage() {
  const [stats, setStats] = useState<StatisticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const res = await api.statistics.get();
        setStats(res);
      } catch (e) {
        setError('Failed to load statistics');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center min-h-[400px]"><div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div></div>;
  }

  if (error) {
    return <div className="text-center p-8 text-red-600">{error}</div>;
  }

  const s = stats!;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-8">Cemetery Statistics</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard title="Total Deaths" value={s.total_deaths} icon="💀" color="purple" />
        <StatCard
          title="Total Lifespan"
          value={formatDuration(s.total_lifespan_seconds)}
          icon="⏱️"
          color="blue"
        />
        <StatCard
          title="Average Lifespan"
          value={formatDuration(Math.round(s.average_lifespan_seconds))}
          icon="📊"
          color="green"
        />
        <StatCard title="Oldest Death" value={s.oldest_death ? formatDate(s.oldest_death) : '—'} icon="🕰️" color="orange" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <Card title="Deaths by Cause">
          <ul className="space-y-2">
            {Object.entries(s.by_cause).length === 0 ? (
              <li className="text-gray-500">No data</li>
            ) : (
              Object.entries(s.by_cause).map(([cause, count]) => (
                <li key={cause} className="flex justify-between py-2 border-b border-gray-100 dark:border-gray-700">
                  <span className="capitalize text-gray-700 dark:text-gray-300">{cause.replace(/_/g, ' ').toLowerCase()}</span>
                  <span className="font-semibold text-gray-900 dark:text-white">{count}</span>
                </li>
              ))
            )}
          </ul>
        </Card>

        <Card title="Deaths by Extension">
          <ul className="space-y-2">
            {Object.entries(s.by_extension).length === 0 ? (
              <li className="text-gray-500">No data</li>
            ) : (
              Object.entries(s.by_extension)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 10)
                .map(([ext, count]) => (
                  <li key={ext} className="flex justify-between py-2 border-b border-gray-100 dark:border-gray-700">
                    <span className="font-mono text-gray-700 dark:text-gray-300">{ext || '(none)'}</span>
                    <span className="font-semibold text-gray-900 dark:text-white">{count}</span>
                  </li>
                ))
            )}
          </ul>
        </Card>
      </div>

      <Card title="Time Range">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Oldest Death</p>
            <p className="font-mono text-lg text-gray-900 dark:text-white">{s.oldest_death ? formatDate(s.oldest_death) : '—'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Newest Death</p>
            <p className="font-mono text-lg text-gray-900 dark:text-white">{s.newest_death ? formatDate(s.newest_death) : '—'}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
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
        <div className={`bg-${color}-500 text-white p-3 rounded-lg text-2xl`}>{icon}</div>
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

