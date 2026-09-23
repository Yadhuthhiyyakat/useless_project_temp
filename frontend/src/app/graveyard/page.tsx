'use client';

import React, { useState, useEffect, useMemo, useId } from 'react';
import { api, type Death, formatBytes, formatDate } from '@/lib/api';
import Domestone, { GraveyardItem, isFolder } from './Domestone';

export default function GraveyardPage() {
  const [deaths, setDeaths] = useState<GraveyardItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'gallery' | 'map'>('map');
  const [selectedSoul, setSelectedSoul] = useState<GraveyardItem | null>(null);
  const [filterType, setFilterType] = useState<'all' | 'files' | 'folders'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [causeFilter, setCauseFilter] = useState('');
  const [fogActive, setFogActive] = useState(true);
  const [tributes, setTributes] = useState<Record<number, { candles: number; flowers: number }>>({});
  const [bellTollActive, setBellTollActive] = useState(false);
  const searchInputId = useId();
  const filterTypeId = useId();
  const causeFilterId = useId();

  // Load deaths strictly from live backend API
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        const res = await api.deaths.list({ limit: 100 });
        if (res && Array.isArray(res.items)) {
          setDeaths(res.items);
        } else {
          setDeaths([]);
        }
      } catch (e) {
        console.error('Failed to load deaths from backend API:', e);
        setError('Unable to reach the digital cemetery registry. Ensure the backend server is running.');
        setDeaths([]);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Web Audio Synthesized Cathedral / Funeral Bell Chime
  const tollBell = () => {
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      setBellTollActive(true);
      setTimeout(() => setBellTollActive(false), 2400);

      // Deep bell fundamental
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const osc3 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(220, ctx.currentTime); // A3
      osc1.frequency.exponentialRampToValueAtTime(110, ctx.currentTime + 3.0);

      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(440, ctx.currentTime); // octave
      osc2.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 2.5);

      osc3.type = 'triangle';
      osc3.frequency.setValueAtTime(330, ctx.currentTime); // fifth
      osc3.frequency.exponentialRampToValueAtTime(165, ctx.currentTime + 2.0);

      gain.gain.setValueAtTime(0.01, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.4, ctx.currentTime + 0.05);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 3.2);

      osc1.connect(gain);
      osc2.connect(gain);
      osc3.connect(gain);
      gain.connect(ctx.destination);

      osc1.start();
      osc2.start();
      osc3.start();
      osc1.stop(ctx.currentTime + 3.3);
      osc2.stop(ctx.currentTime + 3.3);
      osc3.stop(ctx.currentTime + 3.3);
    } catch {
      // Audio not permitted without user gesture or unsupported
    }
  };

  const handleTributeCandle = (id: number) => {
    setTributes((prev) => ({
      ...prev,
      [id]: {
        candles: (prev[id]?.candles || 0) + 1,
        flowers: prev[id]?.flowers || 0,
      },
    }));
  };

  const handleTributeFlower = (id: number) => {
    setTributes((prev) => ({
      ...prev,
      [id]: {
        candles: prev[id]?.candles || 0,
        flowers: (prev[id]?.flowers || 0) + 1,
      },
    }));
  };

  const handleLightAllCandles = () => {
    const updated: Record<number, { candles: number; flowers: number }> = {};
    deaths.forEach((d) => {
      updated[d.id] = {
        candles: (tributes[d.id]?.candles || 0) + 1,
        flowers: tributes[d.id]?.flowers || 0,
      };
    });
    setTributes(updated);
  };

  // Filter items
  const filteredItems = useMemo(() => {
    return deaths.filter((item) => {
      // Type filter
      const isDir = isFolder(item);
      if (filterType === 'files' && isDir) return false;
      if (filterType === 'folders' && !isDir) return false;

      // Cause filter
      if (causeFilter && item.cause !== causeFilter && item.cause_label !== causeFilter) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = item.filename.toLowerCase().includes(q);
        const matchesPath = item.original_path.toLowerCase().includes(q);
        const matchesExt = item.extension.toLowerCase().includes(q);
        const matchesEpitaph = item.epitaph ? item.epitaph.toLowerCase().includes(q) : false;
        if (!matchesName && !matchesPath && !matchesExt && !matchesEpitaph) return false;
      }

      return true;
    });
  }, [deaths, filterType, causeFilter, searchQuery]);

  const uniqueCauses = useMemo(() => {
    const causes = new Set<string>();
    deaths.forEach((d) => {
      if (d.cause_label) causes.add(d.cause_label);
      else if (d.cause) causes.add(d.cause);
    });
    return Array.from(causes);
  }, [deaths]);

  return (
    <div className="min-h-screen bg-[#07090e] text-zinc-100 relative overflow-hidden selection:bg-indigo-900 selection:text-indigo-200">
      {/* Cemetery Ambient Fog Effect */}
      {fogActive && (
        <div className="fixed inset-0 pointer-events-none z-10 overflow-hidden opacity-60">
          <div
            className="absolute -top-40 -left-1/4 w-[150%] h-[150%] animate-fog-1 pointer-events-none"
            style={{
              background:
                'radial-gradient(ellipse at 50% 50%, rgba(148, 163, 184, 0.08) 0%, rgba(99, 102, 241, 0.04) 40%, transparent 75%)',
            }}
          />
          <div
            className="absolute -bottom-20 -right-1/4 w-[140%] h-[120%] animate-fog-2 pointer-events-none"
            style={{
              background:
                'radial-gradient(ellipse at 50% 50%, rgba(148, 163, 184, 0.06) 0%, rgba(168, 85, 247, 0.03) 45%, transparent 75%)',
            }}
          />
        </div>
      )}

      {/* Spooky Cemetery Gate Header */}
      <section className="relative pt-12 pb-8 border-b border-zinc-800/80 bg-gradient-to-b from-zinc-950 via-[#0c0f17] to-[#07090e]">
        {/* Wrought Iron Gate Filigree */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-20">
          <div className="inline-flex items-center justify-center gap-3 mb-2 text-zinc-400">
            <span className="text-xl">⚔️</span>
            <span className="text-xs uppercase tracking-[0.4em] font-serif text-zinc-400">
              The Digital Cemetery
            </span>
            <span className="text-xl">⚔️</span>
          </div>

          <h1 className="text-4xl sm:text-5xl md:text-6xl font-black font-serif tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-zinc-200 via-zinc-100 to-zinc-400 drop-shadow-md">
            The Graveyard of Lost Files
          </h1>

          <p className="mt-3 text-sm sm:text-base text-zinc-400 max-w-2xl mx-auto font-serif italic">
            Where deceased files and departed folders rest in eternal silence. Each domestone bears
            the carved marble record of their brief existence on disk.
          </p>

          {/* Quick Stats and Status Badges */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-xs">
            <div className="px-3 py-1.5 rounded-full bg-zinc-900/80 border border-zinc-700/60 text-zinc-300 flex items-center gap-2">
              <span>🪦 Interred Souls:</span>
              <span className="font-bold text-amber-300 font-mono">{deaths.length}</span>
            </div>

            <div className="px-3 py-1.5 rounded-full bg-zinc-900/80 border border-zinc-700/60 text-zinc-300 flex items-center gap-2">
              <span>🏛️ Folders in Crypts:</span>
              <span className="font-bold text-indigo-300 font-mono">
                {deaths.filter(isFolder).length}
              </span>
            </div>

            <div className="px-3 py-1.5 rounded-full bg-zinc-900/80 border border-zinc-700/60 text-zinc-300 flex items-center gap-2">
              <span>📄 Files in Graves:</span>
              <span className="font-bold text-emerald-300 font-mono">
                {deaths.filter((d) => !isFolder(d)).length}
              </span>
            </div>
          </div>

          {/* Atmosphere and Sound Action Bar */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={tollBell}
              className={`px-4 py-2 rounded-lg font-serif text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition duration-300 ${
                bellTollActive
                  ? 'bg-amber-500 text-zinc-950 shadow-lg shadow-amber-500/50 scale-105'
                  : 'bg-zinc-800/90 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 shadow'
              }`}
            >
              <span>🔔</span>
              <span>{bellTollActive ? 'Tolling Death Knell...' : 'Toll Cathedral Bell'}</span>
            </button>

            <button
              onClick={handleLightAllCandles}
              className="px-4 py-2 rounded-lg font-serif text-xs font-semibold uppercase tracking-wider flex items-center gap-2 bg-zinc-800/90 hover:bg-amber-950/60 text-amber-200 border border-amber-900/40 hover:border-amber-600/50 transition duration-300"
            >
              <span className="animate-candle">🕯️</span>
              <span>Light All Candles</span>
            </button>

            <button
              onClick={() => setFogActive(!fogActive)}
              className={`px-3 py-2 rounded-lg text-xs font-medium flex items-center gap-2 border transition ${
                fogActive
                  ? 'bg-indigo-950/50 text-indigo-300 border-indigo-700/60'
                  : 'bg-zinc-900 text-zinc-500 border-zinc-800'
              }`}
            >
              <span>🌫️</span>
              <span>{fogActive ? 'Cemetery Mist: On' : 'Cemetery Mist: Off'}</span>
            </button>
          </div>
        </div>
      </section>

      {/* Main Cemetery Grounds */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 relative z-20">
        {/* Controls Bar: View Modes, Search & Filters */}
        <div className="bg-zinc-900/90 backdrop-blur-md rounded-2xl p-4 sm:p-5 border border-zinc-800/90 shadow-xl mb-8">
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
            {/* View Mode Toggle Buttons */}
            <div className="flex items-center gap-2 p-1 bg-zinc-950 rounded-xl border border-zinc-800 self-start">
              <button
                type="button"
                onClick={() => setViewMode('gallery')}
                className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition ${
                  viewMode === 'gallery'
                    ? 'bg-gradient-to-r from-zinc-700 to-zinc-800 text-white shadow'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <span>🏛️</span>
                <span>Monument Gallery</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('map')}
                className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition ${
                  viewMode === 'map'
                    ? 'bg-gradient-to-r from-zinc-700 to-zinc-800 text-white shadow'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <span>🗺️</span>
                <span>Cemetery Plot Map</span>
              </button>
            </div>

            {/* Filter Tabs (All / Files / Folders) */}
            <div className="flex items-center gap-1.5 p-1 bg-zinc-950/80 rounded-xl border border-zinc-800">
              <button
                type="button"
                onClick={() => setFilterType('all')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  filterType === 'all'
                    ? 'bg-zinc-800 text-white shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                All Deceased ({deaths.length})
              </button>
              <button
                type="button"
                onClick={() => setFilterType('files')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  filterType === 'files'
                    ? 'bg-zinc-800 text-white shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                📄 Files ({deaths.filter((d) => !isFolder(d)).length})
              </button>
              <button
                type="button"
                onClick={() => setFilterType('folders')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  filterType === 'folders'
                    ? 'bg-zinc-800 text-white shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                📁 Folders ({deaths.filter(isFolder).length})
              </button>
            </div>

            {/* Search and Cause Filter */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative min-w-[200px] flex-1 sm:flex-initial">
                <span className="absolute left-3 top-2.5 text-zinc-500 text-sm">🔍</span>
                <input
                  id={searchInputId}
                  aria-label="Search cemetery records"
                  type="text"
                  placeholder="Search file or path..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl text-xs bg-zinc-950 border border-zinc-800 text-zinc-200 focus:outline-none focus:border-indigo-500 transition"
                />
              </div>

              {uniqueCauses.length > 0 && (
                <div className="min-w-[140px]">
                  <label htmlFor={causeFilterId} className="sr-only">Filter by cause of demise</label>
                  <select
                    id={causeFilterId}
                    value={causeFilter}
                    onChange={(e) => setCauseFilter(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl text-xs bg-zinc-950 border border-zinc-800 text-zinc-300 focus:outline-none focus:border-indigo-500 transition"
                  >
                    <option value="">All Causes</option>
                    {uniqueCauses.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="mb-8 p-4 rounded-2xl bg-red-950/70 border border-red-800/80 text-red-200 text-center text-sm flex items-center justify-center gap-3">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Loading Spinner */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 text-zinc-400">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-500 border-t-transparent mb-4" />
            <p className="font-serif italic text-sm">Awakening the cemetery archives...</p>
          </div>
        )}

        {/* Empty Cemetery (No deaths recorded in DB yet) */}
        {!loading && deaths.length === 0 && !error && (
          <div className="text-center py-20 bg-zinc-900/50 backdrop-blur-md rounded-3xl border-2 border-zinc-800 p-8 shadow-2xl">
            <span className="text-6xl select-none block mb-3">🪦</span>
            <h3 className="text-2xl font-serif font-bold text-zinc-100">
              The Cemetery is Silent
            </h3>
            <p className="mt-2 text-sm text-zinc-400 max-w-lg mx-auto font-serif italic leading-relaxed">
              No departed files or folders have been interred yet.
              When monitored files in your watched directories are deleted, their domestones and carved marble inscriptions will rise here.
            </p>
            <div className="mt-6 flex flex-wrap justify-center items-center gap-3">
              <a
                href="/settings"
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition"
              >
                ⚙️ Configure Watched Directories
              </a>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-950/80 hover:bg-indigo-900 border border-indigo-700/60 text-indigo-200 transition"
              >
                🔄 Refresh Cemetery Grounds
              </button>
            </div>
          </div>
        )}

        {/* Empty Search / Filter Result (when deaths exist but filter matches 0) */}
        {!loading && deaths.length > 0 && filteredItems.length === 0 && (
          <div className="text-center py-20 bg-zinc-900/40 rounded-2xl border border-zinc-800/80">
            <span className="text-4xl">🕯️</span>
            <h3 className="mt-3 text-lg font-serif font-semibold text-zinc-200">
              No spirits match your search
            </h3>
            <p className="text-xs text-zinc-400 mt-1">
              Adjust your filters or clear the search query to reveal other resting places.
            </p>
            <button
              onClick={() => {
                setSearchQuery('');
                setFilterType('all');
                setCauseFilter('');
              }}
              className="mt-4 px-4 py-2 rounded-lg text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
            >
              Reset Filters
            </button>
          </div>
        )}

        {/* VIEW 1: MONUMENT GALLERY (Catacomb Grid) */}
        {!loading && viewMode === 'gallery' && filteredItems.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 gap-8 justify-items-center">
            {filteredItems.map((item) => (
              <Domestone
                key={item.id}
                item={item}
                candles={tributes[item.id]?.candles || 0}
                flowers={tributes[item.id]?.flowers || 0}
                onTributeCandle={handleTributeCandle}
                onTributeFlower={handleTributeFlower}
                onClick={(selected) => setSelectedSoul(selected)}
                isSelected={selectedSoul?.id === item.id}
              />
            ))}
          </div>
        )}

        {/* VIEW 2: CEMETERY PLOT MAP (2D Deterministic Coordinates) */}
        {!loading && viewMode === 'map' && filteredItems.length > 0 && (
          <div className="bg-zinc-950 rounded-2xl border-2 border-zinc-800 overflow-hidden shadow-2xl relative">
            {/* Map Header Instructions */}
            <div className="px-6 py-4 bg-zinc-900/80 border-b border-zinc-800 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-serif font-bold text-zinc-200 uppercase tracking-widest flex items-center gap-2">
                  <span>🗺️</span>
                  <span>Cemetery Field Layout [0, 100]</span>
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Plots are assigned deterministically via file SHA-256 hash. Hover or click any
                  headstone to view its marble plaque.
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
                  <span className="text-zinc-400">File Graves</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
                  <span className="text-zinc-400">Folder Crypts</span>
                </div>
              </div>
            </div>

            {/* The 2D Interactive Cemetery Ground */}
            <div
              className="relative w-full h-[650px] bg-[#090d14] overflow-hidden select-none"
              style={{
                backgroundImage: `
                  radial-gradient(circle at 50% 50%, #111827 0%, #06090e 100%),
                  linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px)
                `,
                backgroundSize: '100% 100%, 50px 50px, 50px 50px',
              }}
            >
              {/* Cemetery Cobblestone Pathway cross */}
              <div className="absolute top-1/2 left-0 right-0 h-8 -translate-y-1/2 bg-zinc-900/40 border-y border-zinc-800/40 pointer-events-none" />
              <div className="absolute top-0 bottom-0 left-1/2 w-8 -translate-x-1/2 bg-zinc-900/40 border-x border-zinc-800/40 pointer-events-none" />

              {/* Central Memorial Mausoleum Marker */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 rounded-full bg-zinc-800/80 border-2 border-zinc-600/60 flex items-center justify-center text-xl shadow-lg z-0 pointer-events-none">
                <span>⛲</span>
              </div>

              {/* Cemetery plots plotted with cemetery_x and cemetery_y */}
              {filteredItems.map((item) => {
                const isDir = isFolder(item);
                const hasCandles = (tributes[item.id]?.candles || 0) > 0;
                // keep slightly within bounds so domestones don't clip at 0 or 100
                const leftPercent = Math.min(Math.max(item.cemetery_x, 4), 94);
                const topPercent = Math.min(Math.max(item.cemetery_y, 6), 92);

                return (
                  <div
                    key={item.id}
                    onClick={() => setSelectedSoul(item)}
                    style={{ left: `${leftPercent}%`, top: `${topPercent}%` }}
                    className="absolute -translate-x-1/2 -translate-y-1/2 group cursor-pointer z-10 transition-transform duration-200 hover:scale-125 hover:z-30"
                  >
                    {/* Miniature Headstone Silhouette */}
                    <div
                      className={`relative flex flex-col items-center px-2 py-1 rounded-t-lg transition-all ${
                        isDir
                          ? 'bg-amber-950/80 border border-amber-600/60 shadow-lg shadow-amber-950/50'
                          : 'bg-zinc-800/90 border border-zinc-500/60 shadow-lg shadow-black/80'
                      }`}
                    >
                      {/* Active candle or spectral light */}
                      {hasCandles && (
                        <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 text-xs animate-candle">
                          🕯️
                        </span>
                      )}

                      <span className="text-sm select-none">{isDir ? '🏛️' : '🪦'}</span>
                      <span className="text-[9px] font-mono font-bold max-w-[70px] truncate text-zinc-200">
                        {item.filename}
                      </span>
                    </div>

                    {/* Popover Marble Plaque Tooltip on Hover */}
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 rounded-lg marble-plate text-zinc-100 shadow-2xl opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-all duration-200 z-50">
                      <div className="text-center border-b border-zinc-700/60 pb-1.5 mb-1.5">
                        <span className="text-[10px] uppercase tracking-wider text-amber-300 font-bold block">
                          {isDir ? '🏛️ Crypt / Directory' : '🪦 Tomb / File'}
                        </span>
                        <h4 className="font-mono text-xs font-bold text-white truncate">
                          {item.filename}
                        </h4>
                      </div>

                      <div className="space-y-1 text-[11px] text-zinc-300">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Lifespan:</span>
                          <span className="text-amber-300 font-medium">{item.lifespan_label}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Departed:</span>
                          <span>{formatDate(item.deleted_at)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Cause:</span>
                          <span className="text-red-300 font-semibold">{item.cause_label}</span>
                        </div>
                        <div className="flex justify-between text-[10px] text-zinc-400 pt-1 border-t border-zinc-700/50">
                          <span>Plot:</span>
                          <span className="font-mono text-indigo-300">
                            X: {item.cemetery_x.toFixed(1)}, Y: {item.cemetery_y.toFixed(1)}
                          </span>
                        </div>
                      </div>

                      {item.epitaph && (
                        <p className="mt-2 pt-1 border-t border-zinc-700/60 text-[10px] italic text-amber-200/90 line-clamp-2 text-center">
                          &ldquo;{item.epitaph}&rdquo;
                        </p>
                      )}

                      <div className="mt-2 text-center text-[9px] uppercase tracking-wider text-indigo-400">
                        Click to view full monument →
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>

      {/* DETAILED MARBLE MONUMENT MODAL (Inspector) */}
      {selectedSoul && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="monument-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fade-in"
          onClick={() => setSelectedSoul(null)}
        >
          <div
            className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-3xl p-6 sm:p-8 bg-zinc-900 border-2 border-zinc-700 shadow-2xl shadow-black text-zinc-100"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              onClick={() => setSelectedSoul(null)}
              className="absolute top-4 right-4 w-9 h-9 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-300 flex items-center justify-center text-sm font-bold border border-zinc-600 transition"
              title="Close monument"
            >
              ✕
            </button>

            {/* Monument Top Heraldry */}
            <div className="text-center pt-2 pb-6 border-b border-zinc-800">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest bg-zinc-950 border border-zinc-700 text-zinc-300 mb-3">
                <span>{isFolder(selectedSoul) ? '🏛️ Family Crypt' : '🪦 Holy Tomb'}</span>
                <span>•</span>
                <span>
                  {isFolder(selectedSoul)
                    ? 'Directory Archive'
                    : selectedSoul.extension || 'Standard File'}
                </span>
              </div>

              <h2
                id="monument-title"
                className="text-2xl sm:text-3xl font-mono font-bold text-white break-all carved-text"
              >
                {selectedSoul.filename}
              </h2>

              <p className="mt-1 font-mono text-xs text-zinc-400 break-all px-4">
                {selectedSoul.original_path}
              </p>
            </div>

            {/* Inscribed Marble Plaque in Modal */}
            <div className="my-6 p-6 rounded-2xl marble-plate border border-zinc-600/60 shadow-inner">
              <div className="text-center mb-4">
                <span className="text-xs uppercase tracking-[0.3em] font-serif font-bold text-zinc-300">
                  † In Memoriam †
                </span>
              </div>

              {/* Detailed Metadata Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div className="p-3 rounded-xl bg-black/30 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">Time of Creation (Born)</span>
                  <span className="font-mono text-sm font-semibold text-zinc-200">
                    {formatDate(selectedSoul.born_at)}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-black/30 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">Time of Deletion (Departed)</span>
                  <span className="font-mono text-sm font-semibold text-zinc-200">
                    {formatDate(selectedSoul.deleted_at)}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-black/30 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">Total Lifespan</span>
                  <span className="text-sm font-bold text-amber-300 flex items-center gap-1.5">
                    <span>⏳</span>
                    <span>{selectedSoul.lifespan_label}</span>
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-black/30 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">Size on Disk</span>
                  <span className="font-mono text-sm font-semibold text-zinc-200">
                    {isFolder(selectedSoul)
                      ? 'Directory Container'
                      : formatBytes(selectedSoul.size_bytes)}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-black/30 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">Cause of Death</span>
                  <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-950 text-red-300 border border-red-800/60 inline-block">
                    {selectedSoul.cause_label || selectedSoul.cause}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-black/30 border border-zinc-800">
                  <span className="text-zinc-400 block mb-1">Cemetery Plot Coordinates</span>
                  <span className="font-mono text-sm font-bold text-indigo-300">
                    Plot ({selectedSoul.cemetery_x.toFixed(2)}, {selectedSoul.cemetery_y.toFixed(2)})
                  </span>
                </div>
              </div>

              {/* Large Engraved Epitaph */}
              <div className="mt-5 p-4 rounded-xl bg-black/40 border border-zinc-800 text-center">
                <span className="text-[10px] uppercase tracking-widest text-zinc-400 block mb-1 font-serif">
                  Engraved Epitaph
                </span>
                <p className="font-serif italic text-sm sm:text-base text-amber-200 tracking-wide px-2 leading-relaxed">
                  &ldquo;
                  {selectedSoul.epitaph ||
                    'Here lies a silent soul, struck down from the filesystem but immortalized in stone.'}
                  &rdquo;
                </p>
              </div>
            </div>

            {/* Interactive Tribute Buttons */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => handleTributeCandle(selectedSoul.id)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-amber-950/70 hover:bg-amber-900 border border-amber-600/40 text-amber-200 flex items-center gap-2 transition"
                >
                  <span className="text-base animate-candle">🕯️</span>
                  <span>Light Vigil Candle ({tributes[selectedSoul.id]?.candles || 0})</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleTributeFlower(selectedSoul.id)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-950/70 hover:bg-rose-900 border border-rose-600/40 text-rose-200 flex items-center gap-2 transition"
                >
                  <span className="text-base">🥀</span>
                  <span>Lay Black Rose ({tributes[selectedSoul.id]?.flowers || 0})</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => {
                  tollBell();
                }}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 text-zinc-200 flex items-center gap-2 transition"
              >
                <span>🔔</span>
                <span>Toll Death Knell</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
