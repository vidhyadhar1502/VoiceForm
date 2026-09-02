/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import {
  Mic,
  MicOff,
  Radio,
  Zap,
  VolumeX,
  Volume2,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Play,
  RotateCcw,
  Sparkles,
  Activity,
  Layers,
  CheckCircle2,
  Clock,
  Settings,
  Cpu,
  RefreshCw
} from 'lucide-react';
import { VoiceState, SpeechStatus } from '../types';

interface VoiceInteractionPanelProps {
  voiceState: VoiceState;
  audioStatus: SpeechStatus;
  activeVersion: number;
  onStartListening: () => Promise<void>;
  onStopListening: () => Promise<void>;
  onCancelListening: () => Promise<void>;
  onSwitchProvider: (type: 'browser' | 'mock') => void;
  onRunVoiceBargeInTest: () => Promise<void>;
  onConfigureMock: (config: {
    simulatedTranscript?: string;
    shouldFail?: boolean;
    permissionDenied?: boolean;
  }) => void;
  isTestingVoice: boolean;
}

const MOCK_PRESETS = [
  { label: 'Postal 600001 (v80)', text: 'My postal code is 600001' },
  { label: 'Barge-In 600028 (v81)', text: 'Actually change it to 600028' },
  { label: 'Set Name: Priya Sharma', text: 'My name is Priya Sharma' },
  { label: 'Set City: Seattle', text: 'My city is Seattle' },
  { label: 'Skip Date of Birth', text: 'Skip date of birth for now' },
];

export const VoiceInteractionPanel: React.FC<VoiceInteractionPanelProps> = ({
  voiceState,
  audioStatus,
  activeVersion,
  onStartListening,
  onStopListening,
  onCancelListening,
  onSwitchProvider,
  onRunVoiceBargeInTest,
  onConfigureMock,
  isTestingVoice,
}) => {
  const [customMockText, setCustomMockText] = useState('My postal code is 600001');
  const [simulatePermissionDenied, setSimulatePermissionDenied] = useState(false);
  const [simulateFailure, setSimulateFailure] = useState(false);

  const isListening = voiceState.micStatus === 'LISTENING';
  const isProcessing = voiceState.micStatus === 'PROCESSING';
  const isError = voiceState.micStatus === 'ERROR';
  const isUnsupported = voiceState.micStatus === 'UNSUPPORTED';
  const isBrowserMode = voiceState.providerType === 'browser';

  const handleToggleListening = async () => {
    if (isListening) {
      await onStopListening();
    } else {
      if (!isBrowserMode) {
        onConfigureMock({
          simulatedTranscript: customMockText,
          permissionDenied: simulatePermissionDenied,
          shouldFail: simulateFailure,
        });
      }
      await onStartListening();
    }
  };

  const getMicBadge = () => {
    switch (voiceState.micStatus) {
      case 'LISTENING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 animate-pulse">
            <Radio className="w-3.5 h-3.5 animate-spin" /> LISTENING (LIVE MIC)
          </span>
        );
      case 'PROCESSING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 animate-pulse">
            <Zap className="w-3.5 h-3.5" /> PROCESSING STT
          </span>
        );
      case 'ERROR':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <ShieldAlert className="w-3.5 h-3.5" /> STT ERROR
          </span>
        );
      case 'UNSUPPORTED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20">
            <AlertTriangle className="w-3.5 h-3.5" /> BROWSER UNSUPPORTED
          </span>
        );
      case 'IDLE':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20">
            <Mic className="w-3.5 h-3.5" /> MIC IDLE
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden flex flex-col">
      {/* Panel Header */}
      <div className="bg-slate-900 text-white px-5 py-3.5 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-rose-500/20 border border-rose-400/30 flex items-center justify-center text-rose-300">
            <Mic className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-white tracking-tight">
                Voice Input & Full-Duplex Barge-In Engine
              </h2>
              {getMicBadge()}
            </div>
            <p className="text-xs text-slate-400">
              Speech-to-text pipeline with instant audio interruption & monotonic version fencing
            </p>
          </div>
        </div>

        {/* STT Mode Selector */}
        <div className="flex items-center gap-1.5 bg-slate-800 p-1 rounded-lg border border-slate-700">
          <button
            onClick={() => onSwitchProvider('browser')}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              isBrowserMode
                ? 'bg-rose-600 text-white shadow-2xs font-semibold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Browser STT
          </button>
          <button
            onClick={() => onSwitchProvider('mock')}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
              !isBrowserMode
                ? 'bg-indigo-600 text-white shadow-2xs font-semibold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Deterministic Mock
          </button>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Main Microphone Action & Barge-In Visualizer */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center bg-slate-50/80 p-4 rounded-xl border border-slate-200">
          {/* Big Mic Button */}
          <div className="md:col-span-4 flex flex-col items-center justify-center p-2">
            <button
              onClick={handleToggleListening}
              disabled={isUnsupported}
              className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-md cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                isListening
                  ? 'bg-rose-600 text-white ring-4 ring-rose-300 animate-pulse scale-105'
                  : isProcessing
                  ? 'bg-amber-500 text-white animate-bounce'
                  : 'bg-indigo-600 hover:bg-indigo-700 text-white hover:scale-105'
              }`}
            >
              {isListening ? (
                <MicOff className="w-8 h-8 animate-spin" />
              ) : (
                <Mic className="w-8 h-8" />
              )}
            </button>
            <span className="mt-2 text-xs font-semibold text-slate-700">
              {isListening ? 'Click to Stop Speaking' : 'Click to Speak (Voice Input)'}
            </span>
            <span className="text-[11px] text-slate-500 text-center mt-0.5">
              {audioStatus === 'PLAYING'
                ? '⚡ Clicking will instantly interrupt playing audio'
                : `Provider: ${voiceState.providerName}`}
            </span>
          </div>

          {/* Transcript & Barge-In Live Telemetry */}
          <div className="md:col-span-8 space-y-2.5">
            {/* Interim Transcript Live Stream */}
            <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-xs text-slate-500 font-medium mb-1">
                <span className="flex items-center gap-1.5 text-slate-700">
                  <Activity className="w-3.5 h-3.5 text-rose-500" />
                  Live Interim Transcript:
                </span>
                {isListening && (
                  <span className="flex items-center gap-1 text-[11px] text-rose-600 font-mono font-semibold animate-pulse">
                    <span className="w-2 h-2 rounded-full bg-rose-500"></span> STREAMING AUDIO...
                  </span>
                )}
              </div>
              <div className="text-sm font-mono min-h-[28px] text-slate-800 bg-slate-50 px-2.5 py-1.5 rounded border border-slate-100 flex items-center">
                {voiceState.interimTranscript ? (
                  <span className="text-slate-900 font-medium">{voiceState.interimTranscript}</span>
                ) : (
                  <span className="text-slate-400 italic text-xs">
                    {isListening ? 'Listening for speech input...' : 'Waiting for voice activation...'}
                  </span>
                )}
              </div>
            </div>

            {/* Last Final Transcript Sent to Pipeline */}
            <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-xs text-slate-500 font-medium mb-1">
                <span className="flex items-center gap-1.5 text-slate-700">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  Last Confirmed Final Transcript:
                </span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-50 border border-indigo-200 text-indigo-700 font-semibold">
                  Tagged v{voiceState.activeVersion}
                </span>
              </div>
              <div className="text-sm font-mono min-h-[28px] text-slate-800 bg-slate-50 px-2.5 py-1.5 rounded border border-slate-100 flex items-center justify-between">
                {voiceState.finalTranscript ? (
                  <span className="text-emerald-900 font-medium">"{voiceState.finalTranscript}"</span>
                ) : (
                  <span className="text-slate-400 italic text-xs">No voice transcript dispatched yet</span>
                )}
                {voiceState.finalTranscript && (
                  <span className="text-[10px] text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded font-semibold">
                    ✓ Pipeline Accepted
                  </span>
                )}
              </div>
            </div>

            {/* Barge-In Interruption Event Badge */}
            {voiceState.lastInterruptionEvent && (
              <div className="p-2.5 rounded-lg bg-purple-50 border border-purple-200 flex items-center justify-between text-xs text-purple-900">
                <div className="flex items-center gap-1.5">
                  <VolumeX className="w-4 h-4 text-purple-600 shrink-0" />
                  <span className="font-semibold">Barge-in Interruption:</span>
                  <span>{voiceState.lastInterruptionEvent}</span>
                </div>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-200 text-purple-800 font-mono font-bold">
                  v{voiceState.activeVersion} FENCED
                </span>
              </div>
            )}

            {/* Error Display */}
            {voiceState.errorMessage && (
              <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 flex items-center gap-2 text-xs text-rose-800">
                <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0" />
                <span>{voiceState.errorMessage}</span>
              </div>
            )}
          </div>
        </div>

        {/* Deterministic Barge-In Scenario Runner */}
        <div className="p-4 bg-indigo-50/50 rounded-xl border border-indigo-100 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-xs font-semibold text-indigo-950 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              Automated End-to-End Voice Interruption Scenario (v80 → v81)
            </h3>
            <p className="text-[11px] text-indigo-800/80 mt-0.5">
              Simulates: Voice v80 ("postal code 600001") → Rime audio starts → User voice barge-in v81 ("Actually 600028") → v80 audio stopped & blocked → Form state updated to 600028.
            </p>
          </div>
          <button
            onClick={onRunVoiceBargeInTest}
            disabled={isTestingVoice}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-colors flex items-center space-x-1.5 shrink-0 shadow-xs cursor-pointer disabled:opacity-50"
          >
            {isTestingVoice ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Running Test...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                <span>Run Voice Barge-In Test</span>
              </>
            )}
          </button>
        </div>

        {/* Mock STT Configuration (Only shown in Mock Mode) */}
        {!isBrowserMode && (
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-indigo-600" />
                Deterministic Mock Speech Recognition Configuration
              </span>
              <span className="text-[10px] bg-slate-200 text-slate-700 px-2 py-0.5 rounded font-mono">
                No mic hardware required
              </span>
            </div>

            {/* Presets */}
            <div className="flex flex-wrap gap-1.5">
              {MOCK_PRESETS.map((preset, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setCustomMockText(preset.text);
                    onConfigureMock({ simulatedTranscript: preset.text });
                  }}
                  className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors cursor-pointer ${
                    customMockText === preset.text
                      ? 'bg-indigo-600 text-white border-indigo-600 font-medium'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Custom Input */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={customMockText}
                onChange={(e) => {
                  setCustomMockText(e.target.value);
                  onConfigureMock({ simulatedTranscript: e.target.value });
                }}
                placeholder="Type custom mock voice phrase..."
                className="flex-1 bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <label className="flex items-center gap-1 text-xs text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={simulatePermissionDenied}
                  onChange={(e) => {
                    setSimulatePermissionDenied(e.target.checked);
                    onConfigureMock({ permissionDenied: e.target.checked });
                  }}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                Permission Denied
              </label>
              <label className="flex items-center gap-1 text-xs text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={simulateFailure}
                  onChange={(e) => {
                    setSimulateFailure(e.target.checked);
                    onConfigureMock({ shouldFail: e.target.checked });
                  }}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                STT Error
              </label>
            </div>
          </div>
        )}

        {/* Observability Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 pt-1">
          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-center">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Voice Inputs</span>
            <span className="text-base font-bold text-slate-800">{voiceState.metrics.voiceInteractionsCount}</span>
          </div>

          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-center">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Voice Barge-ins</span>
            <span className="text-base font-bold text-purple-700">{voiceState.metrics.voiceInterruptionsCount}</span>
          </div>

          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-center">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Audio Stopped</span>
            <span className="text-base font-bold text-rose-700">{voiceState.metrics.audioInterruptedForUserInputCount}</span>
          </div>

          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-center">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Stop Latency</span>
            <span className="text-base font-bold text-indigo-700 font-mono">
              {voiceState.metrics.voiceActivationToStopLatencyMs !== null
                ? `${voiceState.metrics.voiceActivationToStopLatencyMs}ms`
                : '—'}
            </span>
            <span className="text-[9px] text-slate-400 block">
              {voiceState.metrics.isRealLatencyMeasurement ? 'Real Browser' : 'Simulated'}
            </span>
          </div>

          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-center">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Transcripts Accepted</span>
            <span className="text-base font-bold text-emerald-700">{voiceState.metrics.finalTranscriptsAcceptedCount}</span>
          </div>

          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-center">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Stale Blocked</span>
            <span className="text-base font-bold text-amber-700">{voiceState.metrics.staleResultsBlockedAfterVoiceCount}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
