import React from 'react';
import { Shield, ShieldAlert, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';

interface MetricsCardsProps {
  activeVersion: number;
  staleBlocksCount: number;
  cancelledTasksCount: number;
  activeTasksCount: number;
  testSuccess: boolean | null;
  mode: string;
}

export const MetricsCards: React.FC<MetricsCardsProps> = ({
  activeVersion,
  staleBlocksCount,
  cancelledTasksCount,
  activeTasksCount,
  testSuccess,
  mode,
}) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
      {/* Active Version Card */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Version</span>
          <Shield className="w-4 h-4 text-indigo-600" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-black font-mono text-slate-900">v{activeVersion}</span>
          <span className="text-xs text-slate-500">Monotonic</span>
        </div>
        <div className="mt-1 text-[11px] text-slate-500">
          Source of truth for all mutations
        </div>
      </div>

      {/* Stale Results Blocked Card */}
      <div
        className={`p-4 rounded-xl border transition-colors ${
          staleBlocksCount > 0
            ? 'bg-amber-50/70 border-amber-300'
            : 'bg-white border-slate-200 shadow-xs'
        }`}
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Stale Results Blocked</span>
          <ShieldAlert
            className={`w-4 h-4 ${
              staleBlocksCount > 0 ? 'text-amber-600' : 'text-slate-400'
            }`}
          />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span
            className={`text-2xl font-black font-mono ${
              staleBlocksCount > 0 ? 'text-amber-700' : 'text-slate-900'
            }`}
          >
            {staleBlocksCount}
          </span>
          {staleBlocksCount > 0 && (
            <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-amber-200 text-amber-900">
              Fenced
            </span>
          )}
        </div>
        <div className="mt-1 text-[11px] text-slate-500">
          Prevented from corrupting UI state
        </div>
      </div>

      {/* Cancelled Tasks Card */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Tasks Cancelled</span>
          <XCircle className="w-4 h-4 text-slate-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-black font-mono text-slate-900">{cancelledTasksCount}</span>
          <span className="text-xs text-slate-500">({activeTasksCount} active)</span>
        </div>
        <div className="mt-1 text-[11px] text-slate-500">
          Aborted early for efficiency
        </div>
      </div>

      {/* Correctness Status Card */}
      <div
        className={`p-4 rounded-xl border ${
          testSuccess === true
            ? 'bg-emerald-50/70 border-emerald-300'
            : testSuccess === false
            ? 'bg-rose-50/70 border-rose-300'
            : 'bg-white border-slate-200 shadow-xs'
        }`}
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Correctness Status</span>
          {testSuccess === true ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          ) : (
            <RefreshCw className="w-4 h-4 text-slate-400" />
          )}
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span
            className={`text-sm font-bold ${
              testSuccess === true
                ? 'text-emerald-800'
                : testSuccess === false
                ? 'text-rose-800'
                : 'text-slate-700'
            }`}
          >
            {testSuccess === true
              ? 'Guaranteed by Fence'
              : testSuccess === false
              ? 'Verification Failed'
              : 'Ready for Test'}
          </span>
        </div>
        <div className="mt-1 text-[11px] text-slate-500">
          {mode === 'uncancellable' ? 'Mode B: Fencing test' : 'Mode A: Cancellation test'}
        </div>
      </div>
    </div>
  );
};
