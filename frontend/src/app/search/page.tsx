"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const limit = 20;

  useEffect(() => {
    if (query.trim()) {
      loadResults();
    } else {
      setData(null);
    }
  }, [query, page]);

  async function loadResults() {
    if (!query.trim()) return;
    try {
      setLoading(true);
      setError(null);
      const res = await api.search.get(query, { limit, offset: (page - 1) * limit });
      setData(res);
    } catch (e) {
      setError("Search failed");
    } finally {
      setLoading(false);
    }
  }

  const totalPages = data ? Math.ceil(data.total / limit) : 1;

  if (loading && query) {
    return <div className="flex items-center justify-center min-h-[400px]"><div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent" /></div>;
  }

  if (error) {
    return <div className="text-center p-8 text-red-600">{error}</div>;
  }

  function renderItems() {
    if (!data) return null;
    if (data.items.length === 0) {
      return (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg">No results for <span className="font-mono">"{query}"</span></p>
          <p className="text-sm mt-1">Try a different search term</p>
        </div>
      );
    }
    return (
      <div>
        {data.items.map((item: any) => (
          <div key={item.id} className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 mb-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-mono text-lg text-gray-900 dark:text-white">{item.filename}</p>
                <p className="text-sm text-gray-500 font-mono truncate max-w-md">{item.original_path}</p>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <span className="px-2 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700">{item.extension}</span>
                <span className="text-gray-500">{item.lifespan_label}</span>
                <span className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">
                  {item.cause_label}
                </span>
                <span className="text-gray-500">{item.deleted_at}</span>
              </div>
            </div>
          </div>
        ))}
        <div className="mt-6 flex items-center justify-between">
          <span className="text-sm text-gray-500">Page {page} of {totalPages} ({data.total} total)</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (loading && query) {
    return <div className="flex items-center justify-center min-h-[400px]"><div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent" /></div>;
  }

  if (error) {
    return <div className="text-center p-8 text-red-600">{error}</div>;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">Search Deaths</h1>

      <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700 mb-6">
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Search</label>
            <input
              type="text"
              placeholder="Search by filename or path..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 text-lg"
              autoFocus
            />
          </div>
        </div>
        {query && (
          <p className="mt-2 text-sm text-gray-500">
            Searching for <span className="font-mono text-gray-900 dark:text-white">"{query}"</span>
            {data && <span className="ml-2 text-gray-500">\u2014 {data.total} results</span>}
          </p>
        )}
      </div>

      {loading && query && <div className="flex items-center justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent" /></div>}

      {error && <div className="text-center p-8 text-red-600">{error}</div>}

      {data && !loading && <>{renderItems()}</>}
    </div>
  );
}
