'use client';

import React from 'react';
import { formatBytes, formatDate } from '@/lib/api';

export interface GraveyardItem {
  id: number;
  file_id: number;
  filename: string;
  original_path: string;
  extension: string;
  size_bytes: number;
  born_at: string;
  last_modified_at: string | null;
  deleted_at: string;
  lifespan_seconds: number;
  lifespan_label: string;
  cause: string;
  cause_label: string;
  epitaph: string | null;
  cemetery_x: number;
  cemetery_y: number;
  created_at: string;
  is_directory?: boolean;
}

interface DomestoneProps {
  item: GraveyardItem;
  candles: number;
  flowers: number;
  onTributeCandle?: (id: number) => void;
  onTributeFlower?: (id: number) => void;
  onClick?: (item: GraveyardItem) => void;
  isSelected?: boolean;
  theme?: 'dark' | 'light';
}

export function isFolder(item: GraveyardItem): boolean {
  if (item.is_directory !== undefined) return item.is_directory;
  if (item.extension === '[dir]' || item.extension === 'folder' || item.extension === 'directory') return true;
  if (!item.extension && !item.filename.includes('.')) return true;
  return false;
}

export default function Domestone({
  item,
  candles,
  flowers,
  onTributeCandle,
  onTributeFlower,
  onClick,
  isSelected,
  theme = 'dark',
}: DomestoneProps) {
  const isDir = isFolder(item);
  const isDark = theme === 'dark';

  return (
    <div
      onClick={() => onClick && onClick(item)}
      className={`group relative flex flex-col items-center cursor-pointer transition-all duration-300 transform hover:-translate-y-2 hover:scale-[1.02] ${
        isSelected ? 'ring-2 ring-indigo-400 ring-offset-4 ring-offset-zinc-950 scale-[1.02]' : ''
      }`}
    >
      {/* Upper Dome Headstone */}
      <div
        className={`relative w-72 sm:w-80 transition-shadow duration-300 ${
          isDir ? 'domestone-folder-shape' : 'domestone-file-shape'
        } ${
          isDark
            ? 'bg-gradient-to-b from-zinc-700 via-zinc-800 to-zinc-900 border-2 border-zinc-600/70 shadow-2xl shadow-black/80'
            : 'bg-gradient-to-b from-stone-200 via-stone-300 to-stone-400 border-2 border-stone-400 shadow-xl'
        }`}
      >
        {/* Stone texture overlay and cracks */}
        <div className="absolute inset-0 opacity-10 pointer-events-none rounded-t-[90px] bg-[radial-gradient(#fff_1px,transparent_1px)] [background-size:12px_12px]" />

        {/* Moss / Aging accents */}
        <div className="absolute top-2 left-4 text-emerald-800/40 text-xs select-none pointer-events-none">
          🌿
        </div>
        <div className="absolute top-8 right-3 text-emerald-900/30 text-xs select-none pointer-events-none">
          🍃
        </div>

        {/* Dome Crown Inscription / Emblem */}
        <div className="pt-6 pb-2 text-center flex flex-col items-center">
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest bg-black/40 text-zinc-300 border border-zinc-600/40 shadow-inner">
            <span>{isDir ? '🏛️ Crypt' : '🪦 Tomb'}</span>
            <span className="text-zinc-500">•</span>
            <span>{isDir ? 'Directory' : item.extension || 'File'}</span>
          </div>

          <div className="mt-3 flex items-center justify-center gap-2">
            <span className="text-xl">{isDir ? '📂' : '📄'}</span>
            <span
              className={`text-xs font-bold tracking-[0.25em] uppercase ${
                isDark ? 'text-zinc-400' : 'text-stone-600'
              }`}
            >
              Rest in Peace
            </span>
            <span className="text-xl">{isDir ? '🗂️' : '💀'}</span>
          </div>
        </div>

        {/* The Marble Slab / Plaque displaying Metadata */}
        <div className="px-4 pb-4">
          <div
            className={`p-4 rounded-lg relative overflow-hidden transition-colors ${
              isDark ? 'marble-plate text-zinc-200' : 'marble-plate-light text-zinc-800'
            }`}
          >
            {/* Marble Veins visual polish */}
            <div className="absolute -top-10 -right-10 w-28 h-28 bg-white/5 rounded-full blur-xl pointer-events-none" />

            {/* Deceased Entity Name */}
            <div className="text-center pb-2.5 mb-2.5 border-b border-zinc-700/60">
              <h3
                className={`font-mono text-base font-bold truncate ${
                  isDark ? 'text-zinc-100 carved-text' : 'text-zinc-900 carved-text-light'
                }`}
                title={item.filename}
              >
                {item.filename}
              </h3>
              <p
                className="text-[11px] font-mono text-zinc-400 truncate opacity-80 mt-0.5"
                title={item.original_path}
              >
                {item.original_path}
              </p>
            </div>

            {/* Marble Carved Metadata Grid */}
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-zinc-400 font-medium">Born</span>
                <span className="font-mono text-[11px] text-zinc-300">
                  {formatDate(item.born_at)}
                </span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-zinc-400 font-medium">Departed</span>
                <span className="font-mono text-[11px] text-zinc-300">
                  {formatDate(item.deleted_at)}
                </span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-zinc-400 font-medium">Lifespan</span>
                <span className="font-semibold text-amber-400/90 text-xs">
                  ⏳ {item.lifespan_label}
                </span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-zinc-400 font-medium">Size</span>
                <span className="font-mono text-zinc-300 text-xs">
                  {isDir ? 'Directory tree' : formatBytes(item.size_bytes)}
                </span>
              </div>

              <div className="flex justify-between items-center pt-1 border-t border-zinc-700/50">
                <span className="text-zinc-400 font-medium">Cause</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-950/70 text-red-300 border border-red-800/40">
                  {item.cause_label || item.cause}
                </span>
              </div>

              <div className="flex justify-between items-center text-[10px] text-zinc-400 pt-0.5">
                <span>Plot Coordinates</span>
                <span className="font-mono text-indigo-300">
                  X: {item.cemetery_x.toFixed(1)} / Y: {item.cemetery_y.toFixed(1)}
                </span>
              </div>
            </div>

            {/* Marble Engraved Epitaph */}
            {item.epitaph ? (
              <div className="mt-3 pt-2.5 border-t border-zinc-700/60 text-center">
                <p className="italic text-xs font-serif text-amber-200/90 tracking-wide line-clamp-2 px-1">
                  &ldquo;{item.epitaph}&rdquo;
                </p>
              </div>
            ) : (
              <div className="mt-3 pt-2 border-t border-zinc-700/40 text-center text-[11px] italic text-zinc-400">
                &ldquo;Gone from the disk, remembered in the register.&rdquo;
              </div>
            )}
          </div>
        </div>

        {/* Tributes Display (Candles & Flowers resting on base) */}
        <div className="px-4 py-2 flex items-center justify-between bg-black/40 border-t border-zinc-700/60 text-xs">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onTributeCandle?.(item.id);
              }}
              title="Light a vigil candle"
              className="flex items-center gap-1 px-2 py-1 rounded bg-amber-950/40 hover:bg-amber-900/60 border border-amber-600/30 text-amber-200 text-xs transition"
            >
              <span className={candles > 0 ? 'animate-candle' : ''}>🕯️</span>
              <span className="font-mono">{candles}</span>
            </button>

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onTributeFlower?.(item.id);
              }}
              title="Leave a black rose"
              className="flex items-center gap-1 px-2 py-1 rounded bg-rose-950/40 hover:bg-rose-900/60 border border-rose-600/30 text-rose-200 text-xs transition"
            >
              <span>🥀</span>
              <span className="font-mono">{flowers}</span>
            </button>
          </div>

          <span className="text-[10px] uppercase tracking-wider text-zinc-400 group-hover:text-zinc-200 transition">
            View Monument →
          </span>
        </div>
      </div>

      {/* Stone Pedestal / Ground Base */}
      <div
        className={`w-80 sm:w-88 h-4 rounded-b-md ${
          isDark
            ? 'bg-gradient-to-r from-zinc-900 via-zinc-700 to-zinc-900 border-x-2 border-b-2 border-zinc-600/80 shadow-md'
            : 'bg-gradient-to-r from-stone-400 via-stone-300 to-stone-400 border-x-2 border-b-2 border-stone-500 shadow'
        }`}
      />
      {/* Soil / Cemetery Turf ground shadow */}
      <div className="w-72 h-2 bg-black/60 rounded-full blur-[3px] -mt-1" />
    </div>
  );
}
