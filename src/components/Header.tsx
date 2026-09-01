import React from 'react';
import { ShieldCheck, Zap, Activity } from 'lucide-react';

interface HeaderProps {
  activeVersion: number;
  isWsConnected: boolean;
  isRunning: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  activeVersion,
  isWsConnected,
  isRunning,
}) => {
  return (
    <header className="border-b border-slate-200 bg-white sticky top-0 z-30 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-slate-900 text-white flex items-center justify-center font-bold tracking-tight text-lg shadow-sm">
            VF
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-slate-900">VoiceForm Engine</h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                Phase 2: Stress-Test Engine
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium">
              Deterministic Race-Condition &amp; Version-Fencing Demonstration
            </p>
          </div>
        </div>

        <div className="flex items-center flex-wrap gap-2.5">
          {/* Active Version Pill */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-slate-800 text-xs font-medium">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Active Version:</span>
            <span className="font-mono font-bold text-slate-900 bg-white px-1.5 py-0.5 rounded border border-slate-300">
              v{activeVersion}
            </span>
          </div>

          {/* WS Status Pill */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 text-xs font-medium">
            <span
              className={`w-2 h-2 rounded-full ${
                isWsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
              }`}
            />
            <span>{isWsConnected ? 'Real-Time Sync' : 'Connecting...'}</span>
          </div>

          {/* Running Indicator */}
          {isRunning && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs font-medium animate-pulse">
              <Activity className="w-3.5 h-3.5 animate-spin text-amber-600" />
              <span>Test Running...</span>
            </div>
          )}
        </div>
      </div>

      {/* Principle Banner */}
      <div className="bg-slate-900 text-slate-200 text-xs py-1.5 px-4 text-center border-t border-slate-800">
        <span className="font-semibold text-emerald-400">Core Principle:</span>{' '}
        <span className="font-mono">Cancellation improves efficiency, but version fencing guarantees correctness.</span>
      </div>
    </header>
  );
};
