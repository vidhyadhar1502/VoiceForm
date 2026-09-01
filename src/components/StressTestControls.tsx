import React from 'react';
import { Play, RotateCcw, Sliders, AlertTriangle, ShieldCheck } from 'lucide-react';

interface StressTestControlsProps {
  mode: 'uncancellable' | 'cancellable';
  setMode: (m: 'uncancellable' | 'cancellable') => void;
  oldPostalCode: string;
  setOldPostalCode: (val: string) => void;
  newPostalCode: string;
  setNewPostalCode: (val: string) => void;
  validationDelay: number;
  setValidationDelay: (val: number) => void;
  interruptTiming: number;
  setInterruptTiming: (val: number) => void;
  isRunning: boolean;
  onRunTest: () => void;
  onReset: () => void;
}

export const StressTestControls: React.FC<StressTestControlsProps> = ({
  mode,
  setMode,
  oldPostalCode,
  setOldPostalCode,
  newPostalCode,
  setNewPostalCode,
  validationDelay,
  setValidationDelay,
  interruptTiming,
  setInterruptTiming,
  isRunning,
  onRunTest,
  onReset,
}) => {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Sliders className="w-5 h-5 text-indigo-600" />
          <h2 className="text-base font-bold text-slate-900">Race Condition Experiment Controls</h2>
        </div>
        <button
          onClick={onReset}
          disabled={isRunning}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 rounded-lg transition-colors disabled:opacity-50 cursor-pointer"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Reset Session
        </button>
      </div>

      <div className="mt-4 space-y-5">
        {/* Mode Selector */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
            Execution Mode
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Mode B: Uncancellable */}
            <button
              type="button"
              onClick={() => setMode('uncancellable')}
              disabled={isRunning}
              className={`p-3.5 text-left rounded-xl border transition-all cursor-pointer ${
                mode === 'uncancellable'
                  ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-indigo-600" />
                  Mode B: Uncancellable Task
                </span>
                {mode === 'uncancellable' && (
                  <span className="w-2 h-2 rounded-full bg-indigo-600" />
                )}
              </div>
              <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">
                Task 1 continues in background and returns stale. <strong>StaleResultGuard</strong> fences it and prevents overwriting newer state.
              </p>
              <div className="mt-2 text-[11px] font-semibold text-indigo-700 bg-indigo-100/60 inline-block px-2 py-0.5 rounded">
                ⭐ Proves Version Fencing Correctness
              </div>
            </button>

            {/* Mode A: Cancellable */}
            <button
              type="button"
              onClick={() => setMode('cancellable')}
              disabled={isRunning}
              className={`p-3.5 text-left rounded-xl border transition-all cursor-pointer ${
                mode === 'cancellable'
                  ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  Mode A: Cancellable Task
                </span>
                {mode === 'cancellable' && (
                  <span className="w-2 h-2 rounded-full bg-indigo-600" />
                )}
              </div>
              <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">
                TaskManager cooperative cancellation triggers immediately when the user interrupts, cancelling Task 1 in-flight for efficiency.
              </p>
              <div className="mt-2 text-[11px] font-semibold text-slate-700 bg-slate-100 inline-block px-2 py-0.5 rounded">
                ⚡ Proves Cancellation Efficiency
              </div>
            </button>
          </div>
        </div>

        {/* Postal Codes & Delays */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {/* Initial Input */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              1. Initial Postal Code (Req 1)
            </label>
            <input
              type="text"
              value={oldPostalCode}
              onChange={(e) => setOldPostalCode(e.target.value)}
              disabled={isRunning}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm font-mono font-medium text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="e.g. 600001"
            />
            <span className="text-[11px] text-slate-500 mt-1 block">Chennai Central (Will start slow validation)</span>
          </div>

          {/* Replacement Input */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              2. Interrupted Correction (Req 2)
            </label>
            <input
              type="text"
              value={newPostalCode}
              onChange={(e) => setNewPostalCode(e.target.value)}
              disabled={isRunning}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm font-mono font-medium text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="e.g. 600028"
            />
            <span className="text-[11px] text-slate-500 mt-1 block">Chennai RA Puram (Must win final state)</span>
          </div>

          {/* Validation Delay */}
          <div>
            <div className="flex justify-between items-center mb-1.5">
              <label className="text-xs font-semibold text-slate-700">
                Validation Artificial Delay
              </label>
              <span className="text-xs font-mono font-bold text-indigo-700">{validationDelay}s</span>
            </div>
            <input
              type="range"
              min="1.0"
              max="6.0"
              step="0.5"
              value={validationDelay}
              onChange={(e) => setValidationDelay(parseFloat(e.target.value))}
              disabled={isRunning}
              className="w-full accent-indigo-600"
            />
            <span className="text-[11px] text-slate-500 mt-1 block">Slow validation tool time</span>
          </div>

          {/* Interruption Timing */}
          <div>
            <div className="flex justify-between items-center mb-1.5">
              <label className="text-xs font-semibold text-slate-700">
                Interruption Timing
              </label>
              <span className="text-xs font-mono font-bold text-indigo-700">{interruptTiming}s</span>
            </div>
            <input
              type="range"
              min="0.5"
              max={Math.max(1.0, validationDelay - 0.5)}
              step="0.5"
              value={interruptTiming}
              onChange={(e) => setInterruptTiming(parseFloat(e.target.value))}
              disabled={isRunning}
              className="w-full accent-indigo-600"
            />
            <span className="text-[11px] text-slate-500 mt-1 block">Triggers before Req 1 completes</span>
          </div>
        </div>

        {/* Run Button */}
        <div className="pt-2">
          <button
            onClick={onRunTest}
            disabled={isRunning}
            className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-bold text-sm rounded-xl shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {isRunning ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Executing Deterministic Race Condition Flow...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>Run Deterministic Stress Test</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
