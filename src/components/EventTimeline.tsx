import React, { useState } from 'react';
import { TimelineEvent } from '../types';
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ListOrdered
} from 'lucide-react';

interface EventTimelineProps {
  timeline: TimelineEvent[];
  activeVersion: number;
}

export const EventTimeline: React.FC<EventTimelineProps> = ({
  timeline,
  activeVersion,
}) => {
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpandedEvents((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getEventBadge = (type: string, isStale: boolean) => {
    if (isStale || type === 'STALE_RESULT_BLOCKED') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-600 text-white shadow-xs animate-bounce">
          <ShieldAlert className="w-3.5 h-3.5" /> STALE RESULT BLOCKED
        </span>
      );
    }

    switch (type) {
      case 'INTERACTION_STARTED':
      case 'USER_INPUT_RECEIVED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-indigo-100 text-indigo-800">
            {type}
          </span>
        );
      case 'INTERRUPTION_DETECTED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-amber-500 text-white">
            <AlertTriangle className="w-3 h-3" /> INTERRUPTION
          </span>
        );
      case 'VERSION_INVALIDATED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-800">
            VERSION INVALIDATED
          </span>
        );
      case 'TASK_CANCELLED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800">
            <XCircle className="w-3 h-3" /> TASK CANCELLED
          </span>
        );
      case 'VALIDATION_STARTED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-sky-100 text-sky-800">
            <Clock className="w-3 h-3" /> VALIDATION STARTED
          </span>
        );
      case 'VALIDATION_RESULT_ACCEPTED':
      case 'FORM_STATE_UPDATED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> RESULT ACCEPTED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
            {type}
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col h-full">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <ListOrdered className="w-5 h-5 text-indigo-600" />
          <div>
            <h3 className="text-base font-bold text-slate-900">Deterministic Event Timeline</h3>
            <p className="text-xs text-slate-500">Live sequential execution trace with version tags</p>
          </div>
        </div>
        <span className="text-xs font-mono font-semibold px-2 py-1 bg-slate-100 rounded text-slate-700">
          {timeline.length} Events
        </span>
      </div>

      <div className="mt-4 flex-1 overflow-y-auto max-h-[500px] pr-1 space-y-3">
        {timeline.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-xs">
            No events recorded yet. Click &quot;Run Deterministic Stress Test&quot; to begin.
          </div>
        ) : (
          timeline.map((evt, idx) => {
            const isStale = evt.is_stale_blocked || evt.event_type === 'STALE_RESULT_BLOCKED';
            const isExpanded = !!expandedEvents[evt.event_id];
            const hasDetails = evt.details && Object.keys(evt.details).length > 0;

            return (
              <div
                key={evt.event_id || idx}
                className={`p-3.5 rounded-xl border transition-all ${
                  isStale
                    ? 'border-rose-300 bg-rose-50/70 shadow-xs ring-2 ring-rose-400/30'
                    : evt.event_type === 'INTERRUPTION_DETECTED'
                    ? 'border-amber-300 bg-amber-50/50'
                    : evt.event_type === 'VALIDATION_RESULT_ACCEPTED'
                    ? 'border-emerald-300 bg-emerald-50/50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[11px] font-mono font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                      #{idx + 1}
                    </span>
                    {getEventBadge(evt.event_type, isStale)}
                  </div>

                  <div className="flex items-center gap-1.5 text-[11px] font-mono">
                    <span className="text-slate-500">Op:</span>
                    <span
                      className={`font-bold px-1.5 py-0.5 rounded ${
                        evt.interaction_version !== evt.active_version
                          ? 'bg-rose-100 text-rose-800'
                          : 'bg-slate-100 text-slate-800'
                      }`}
                    >
                      v{evt.interaction_version}
                    </span>
                    <ArrowRight className="w-3 h-3 text-slate-300" />
                    <span className="text-slate-500">Active:</span>
                    <span className="font-bold px-1.5 py-0.5 rounded bg-slate-900 text-white">
                      v{evt.active_version}
                    </span>
                  </div>
                </div>

                {/* Message */}
                <p className="mt-2 text-xs font-medium text-slate-800 leading-relaxed">
                  {evt.message}
                </p>

                {/* Stale Fence Alert Banner */}
                {isStale && (
                  <div className="mt-2 p-2 rounded-lg bg-rose-100 border border-rose-200 text-rose-900 text-[11px] flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4 shrink-0 text-rose-700" />
                    <span>
                      <strong>Version Fenced:</strong> Stale result from Version {evt.interaction_version} was rejected because Active Version is {evt.active_version}. Form memory was preserved!
                    </span>
                  </div>
                )}

                {/* Expandable Details */}
                {hasDetails && (
                  <div className="mt-2 pt-2 border-t border-slate-100">
                    <button
                      onClick={() => toggleExpand(evt.event_id)}
                      className="text-[11px] text-slate-500 hover:text-slate-800 flex items-center gap-1 cursor-pointer font-medium"
                    >
                      {isExpanded ? (
                        <ChevronDown className="w-3 h-3" />
                      ) : (
                        <ChevronRight className="w-3 h-3" />
                      )}
                      <span>{isExpanded ? 'Hide Payload' : 'View Payload Details'}</span>
                    </button>

                    {isExpanded && (
                      <pre className="mt-2 p-2 rounded bg-slate-900 text-emerald-400 font-mono text-[10px] overflow-x-auto">
                        {JSON.stringify(evt.details, null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
