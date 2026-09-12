'use client';

import { useState, useEffect } from 'react';
import { api, type Death, type DeathListResponse } from '@/lib/api';
import { formatBytes, formatDate } from '@/lib/api';

export default function DeathsPage() {
  const [data, setData] = useState<DeathListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<{
    cause: string;
    extension: string;
    q: string;
    page: number;
  }>({
    cause: '',
    extension: '',
    q: '',
    page: 1,
  });
  const limit = 20;

  useEffect(() => {
    loadDeaths();
  }, [filters]);

  async function loadDeaths() {
    try {
      setLoading(true);
      const res = await api.deaths.list({
        limit,
        offset: (filters.page - 1) * limit,
        cause: filters.cause || undefined,
        extension: filters.extension || undefined,
        q: filters.q || undefined,
      });
      setData(res);
    } catch (e) {
      setError('Failed to load deaths');
    } finally {
      setLoading(false);
    }
  }

  if (loading && !data) {
    return <div className="flex items-center justify-center min-h-[400px]"><div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div></div>;
  }

  if (error) {
    return <div className="text-center p-8 text-red-600">{error}</div>;
  }

  const totalPages = data ? Math.ceil(data.total / limit) : 1;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">All Deaths</h1>
        <span className="text-gray-500 dark:text-gray-400">{data?.total ?? 0} total</span>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700 mb-6 flex flex-wrap gap-4">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Search</label>
          <input
            type="text"
            placeholder="Search filename or path..."
            value={filters.q}
            onChange={(e) => setFilters({ ...filters, q: e.target.value, page: 1 })}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="min-w-[180px]">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Cause</label>
          <select
            value={filters.cause}
            onChange={(e) => setFilters({ ...filters, cause: e.target.value, page: 1 })}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Causes</option>
            <option value="DELETE_DETECTED">Deleted</option>
            <option value="UNKNOWN">Unknown</option>
            <option value="MISSING">Missing</option>
          </select>
        </div>
        <div className="min-w-[180px]">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Extension</label>
          <select
            value={filters.extension}
            onChange={(e) => setFilters({ ...filters, extension: e.target.value, page: 1 })}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Extensions</option>
            <option value=".txt">.txt</option>
            <option value=".pdf">.pdf</option>
            <option value=".jpg">.jpg</option>
            <option value=".png">.png</option>
            <option value=".log">.log</option>
            <option value=".py">.py</option>
            <option value=".js">.js</option>
            <option value=".ts">.ts</option>
          </select>
        </div>
      </div>

      {/* Deaths Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center"><div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent mx-auto"></div></div>
        ) : data?.items.length === 0 ? (
          <div className="p-12 text-center text-gray-500">No deaths found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                  <th className="pb-3 px-4">File</th>
                  <th className="pb-3 px-4">Ext</th>
                  <th className="pb-3 px-4">Size</th>
                  <th className="pb-3 px-4">Lifespan</th>
                  <th className="pb-3 px-4">Cause</th>
                  <th className="pb-3 px-4">Deleted</th>
                  <th className="pb-3 px-4">Epitaph</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {data?.items.map((death) => (
                  <tr key={death.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="py-4 px-4 font-mono text-sm">{death.filename}</td>
                    <td className="py-4 px-4">
                      <span className="px-2 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700">{death.extension}</span>
                    </td>
                    <td className="py-4 px-4 text-sm">{formatBytes(death.size_bytes)}</td>
                    <td className="py-4 px-4 text-sm">{death.lifespan_label}</td>
                    <td className="py-4 px-4">
                      <span className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">
                        {death.cause_label}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-sm text-gray-500">{formatDate(death.deleted_at)}</td>
                    <td className="py-4 px-4">
                      <span className="text-sm text-gray-500 line-clamp-1 max-w-xs block">{death.epitaph || '—'}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="px-4 py-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <span className="text-sm text-gray-500">
            Page {filters.page} of {totalPages} ({data?.total ?? 0} total)
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setFilters({ ...filters, page: Math.max(1, filters.page - 1) })}
              disabled={filters.page === 1}
              className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Previous
            </button>
            <button
              onClick={() => setFilters({ ...filters, page: Math.min(totalPages, filters.page + 1) })}
              disabled={filters.page === totalPages}
              className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}