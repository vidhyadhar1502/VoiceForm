/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import {
  Volume2,
  VolumeX,
  Play,
  Square,
  ShieldCheck,
  ShieldAlert,
  Radio,
  Zap,
  RotateCcw,
  Sparkles,
  Layers,
  Activity
} from 'lucide-react';
import { SpeechProviderInfo, SpeechMetrics, SpeechStatus } from '../types';

interface SpeechStatusPanelProps {
  status: SpeechStatus;
  activeVersion: number;
  currentPlayingVersion: number | null;
  lastBlockedVersion: number | null;
  interruptionLatencyMs: number | null;
  providerInfo: SpeechProviderInfo;
  metrics: SpeechMetrics;
  onPlayTestResponse: () => void;
  onStopAudio: () => void;
  onSwitchProvider: (provider: string, delay?: number) => void;
  onRunRaceTest: (mode: 'MODE_A' | 'MODE_B' | 'MODE_C') => void;
  isTesting: boolean;
}

export const SpeechStatusPanel: React.FC<SpeechStatusPanelProps> = ({
  status,
  activeVersion,
  currentPlayingVersion,
  lastBlockedVersion,
  interruptionLatencyMs,
  providerInfo,
  metrics,
  onPlayTestResponse,
  onStopAudio,
  onSwitchProvider,
  onRunRaceTest,
  isTesting,
}) => {
  const [selectedDelay, setSelectedDelay] = useState<number>(2.0);

  const getStatusBadge = () => {
    switch (status) {
      case 'PLAYING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 animate-pulse">
            <Radio className="w-3.5 h-3.5 animate-spin" /> PLAYING
          </span>
        );
      case 'GENERATING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 animate-pulse">
            <Zap className="w-3.5 h-3.5 animate-bounce" /> GENERATING
          </span>
        );
      case 'QUEUED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <Layers className="w-3.5 h-3.5" /> QUEUED
          </span>
        );
      case 'INTERRUPTED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
            <VolumeX className="w-3.5 h-3.5" /> INTERRUPTED
          </span>
        );
      case 'BLOCKED_STALE':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <ShieldAlert className="w-3.5 h-3.5" /> BLOCKED STALE
          </span>
        );
      case 'IDLE':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20">
            <Volume2 className="w-3.5 h-3.5" /> IDLE
          </span>
        );
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm space-y-5">
      {/* Header & Status */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 rounded-lg">
            <Volume2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center gap-2">
              Rime Speech Engine & Version-Tagged Pipeline
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Guarantees obsolete speech never enters playback queue or browser speaker
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {getStatusBadge()}
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
            Provider: <strong className="text-indigo-600 dark:text-indigo-400">{providerInfo.provider_name}</strong>
            {providerInfo.is_fallback && <span className="text-[10px] text-amber-500 font-mono">(Fallback)</span>}
          </span>
        </div>
      </div>

      {/* Stale Audio Blocked Alert */}
      {lastBlockedVersion !== null && (
        <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 rounded-lg flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 text-rose-800 dark:text-rose-200 font-medium">
            <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0" />
            <span>
              <strong>Version {lastBlockedVersion} Audio BLOCKED AS STALE</strong> (Active: v{activeVersion}). Obsolete response was rejected before browser speaker playback.
            </span>
          </div>
          <span className="px-2 py-0.5 bg-rose-200/60 dark:bg-rose-900/60 text-rose-900 dark:text-rose-100 rounded text-[11px] font-mono">
            Fence Checkpoint Passed
          </span>
        </div>
      )}

      {/* Version Status Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[11px] text-slate-500 dark:text-slate-400">Active Interaction</div>
          <div className="text-lg font-bold text-slate-900 dark:text-slate-100 font-mono">
            v{activeVersion}
          </div>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[11px] text-slate-500 dark:text-slate-400">Playing Audio Version</div>
          <div className="text-lg font-bold text-indigo-600 dark:text-indigo-400 font-mono">
            {currentPlayingVersion ? `v${currentPlayingVersion}` : 'None'}
          </div>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[11px] text-slate-500 dark:text-slate-400">Stale Audio Blocked</div>
          <div className="text-lg font-bold text-rose-600 dark:text-rose-400 font-mono">
            {metrics.stale_tts_results_blocked}
          </div>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div className="text-[11px] text-slate-500 dark:text-slate-400">Interruption Stop Latency</div>
          <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400 font-mono">
            {interruptionLatencyMs !== null ? `${interruptionLatencyMs}ms` : '—'}
          </div>
        </div>
      </div>

      {/* Audio Controls & Provider Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <div className="flex items-center gap-2">
          <button
            id="play-test-response-btn"
            onClick={onPlayTestResponse}
            disabled={isTesting}
            className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
          >
            <Play className="w-3.5 h-3.5 fill-current" /> Play Test Response (v{activeVersion})
          </button>

          <button
            id="stop-audio-btn"
            onClick={onStopAudio}
            className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
          >
            <Square className="w-3.5 h-3.5 fill-current" /> Stop Audio
          </button>
        </div>

        {/* Provider Toggle */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500 dark:text-slate-400">Speech Provider:</span>
          <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 p-0.5 bg-slate-100 dark:bg-slate-800">
            <button
              onClick={() => onSwitchProvider('rime')}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
                providerInfo.provider_name === 'Rime'
                  ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-300 shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              Rime (Primary)
            </button>
            <button
              onClick={() => onSwitchProvider('mock', selectedDelay)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
                providerInfo.provider_name.includes('Mock')
                  ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-300 shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              Mock (Deterministic)
            </button>
          </div>
        </div>
      </div>

      {/* Race Condition Simulation Modes */}
      <div className="pt-3 border-t border-slate-100 dark:border-slate-800">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" /> Audio Pipeline Correctness Test Modes
          </span>
          <span className="text-[11px] text-slate-400">
            Verifies 5 Stale Checkpoints & Immediate Interruption Invalidation
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          <button
            onClick={() => onRunRaceTest('MODE_A')}
            disabled={isTesting}
            className="p-2.5 text-left border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-indigo-500 rounded-lg bg-slate-50/50 dark:bg-slate-800/30 transition text-xs"
          >
            <div className="font-semibold text-slate-800 dark:text-slate-200">Mode A: Stale TTS Generation</div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Fires slow v40 TTS (2s), interrupts with v41 → Asserts v40 blocked as stale.
            </div>
          </button>

          <button
            onClick={() => onRunRaceTest('MODE_B')}
            disabled={isTesting}
            className="p-2.5 text-left border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-indigo-500 rounded-lg bg-slate-50/50 dark:bg-slate-800/30 transition text-xs"
          >
            <div className="font-semibold text-slate-800 dark:text-slate-200">Mode B: Stop Current Playback</div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Starts v50 audio playback, interrupts with v51 → Audio stops immediately, queue cleared.
            </div>
          </button>

          <button
            onClick={() => onRunRaceTest('MODE_C')}
            disabled={isTesting}
            className="p-2.5 text-left border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-indigo-500 rounded-lg bg-slate-50/50 dark:bg-slate-800/30 transition text-xs"
          >
            <div className="font-semibold text-slate-800 dark:text-slate-200">Mode C: Multiple Queued Requests</div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Fires v60, v61, v62 rapidly → Only v62 is eligible for browser playback.
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};
