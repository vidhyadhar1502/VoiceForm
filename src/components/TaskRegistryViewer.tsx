import React from 'react';
import { TaskRecord, TaskStatus } from '../types';
import { Cpu, CheckCircle2, XCircle, ShieldAlert, Clock, AlertTriangle } from 'lucide-react';

interface TaskRegistryViewerProps {
  tasks: TaskRecord[];
  activeVersion: number;
}

export const TaskRegistryViewer: React.FC<TaskRegistryViewerProps> = ({
  tasks,
  activeVersion,
}) => {
  const getStatusPill = (status: TaskStatus) => {
    switch (status) {
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> COMPLETED
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-100 text-rose-800">
            <XCircle className="w-3 h-3 text-rose-600" /> CANCELLED
          </span>
        );
      case 'STALE_BLOCKED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
            <ShieldAlert className="w-3 h-3 text-amber-600" /> STALE BLOCKED
          </span>
        );
      case 'ACTIVE':
      case 'RUNNING':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-100 text-sky-800 animate-pulse">
            <Clock className="w-3 h-3 text-sky-600" /> RUNNING
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5 text-indigo-600" />
          <div>
            <h3 className="text-base font-bold text-slate-900">TaskManager Async Registry</h3>
            <p className="text-xs text-slate-500">
              Cooperative cancellation handles &amp; version-tagged task records
            </p>
          </div>
        </div>
        <span className="text-xs font-mono font-medium text-slate-500">
          {tasks.length} Registered Tasks
        </span>
      </div>

      <div className="mt-4 overflow-x-auto">
        {tasks.length === 0 ? (
          <div className="py-6 text-center text-slate-400 text-xs">
            No asynchronous tasks registered in session yet.
          </div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 font-semibold uppercase text-[10px]">
                <th className="pb-2">Task ID</th>
                <th className="pb-2">Task Name</th>
                <th className="pb-2">Version Tag</th>
                <th className="pb-2">Cancellable</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Fencing Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {tasks.map((task) => {
                const isObsolete = task.version < activeVersion;
                return (
                  <tr key={task.task_id} className="hover:bg-slate-50/80">
                    <td className="py-2.5 font-bold text-slate-900">{task.task_id}</td>
                    <td className="py-2.5 font-sans font-medium text-slate-700">{task.name}</td>
                    <td className="py-2.5">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[11px] font-bold ${
                          isObsolete
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : 'bg-slate-100 text-slate-900'
                        }`}
                      >
                        v{task.version}
                        {isObsolete && ' (Obsolete)'}
                      </span>
                    </td>
                    <td className="py-2.5">
                      {task.uncancellable ? (
                        <span className="inline-flex items-center gap-1 text-[11px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                          <AlertTriangle className="w-3 h-3" /> No (Uncancellable)
                        </span>
                      ) : (
                        <span className="text-[11px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                          Yes (Cooperative)
                        </span>
                      )}
                    </td>
                    <td className="py-2.5">{getStatusPill(task.status)}</td>
                    <td className="py-2.5 font-sans text-slate-600 text-[11px]">
                      {task.status === 'STALE_BLOCKED' && (
                        <span className="font-semibold text-rose-700">
                          Blocked by StaleResultGuard
                        </span>
                      )}
                      {task.status === 'CANCELLED' && (
                        <span className="text-slate-500">Aborted on invalidation</span>
                      )}
                      {task.status === 'COMPLETED' && (
                        <span className="text-emerald-700 font-semibold">Accepted &amp; Mutated</span>
                      )}
                      {task.status === 'RUNNING' && <span className="text-sky-600">Executing...</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
