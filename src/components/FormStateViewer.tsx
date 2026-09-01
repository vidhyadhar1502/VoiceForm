import React from 'react';
import { FormState, FormFieldValue, FieldStatus } from '../types';
import { CheckCircle2, Clock, ShieldCheck, MapPin, AlertCircle } from 'lucide-react';

interface FormStateViewerProps {
  formState: FormState;
  activeVersion: number;
}

export const FormStateViewer: React.FC<FormStateViewerProps> = ({
  formState,
  activeVersion,
}) => {
  const postalField = formState.fields?.['postal_code'] || {
    name: 'postal_code',
    label: 'Postal Code',
    value: '',
    status: 'EMPTY' as FieldStatus,
    validation_status: 'UNVALIDATED',
    updated_at: '',
    interaction_version: 10,
  };

  const getStatusBadge = (status: FieldStatus) => {
    switch (status) {
      case 'CONFIRMED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3 h-3" /> CONFIRMED
          </span>
        );
      case 'VALIDATING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">
            <Clock className="w-3 h-3" /> VALIDATING
          </span>
        );
      case 'STALE_RESULT_BLOCKED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <AlertCircle className="w-3 h-3" /> STALE BLOCKED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col h-full">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div>
          <h3 className="text-base font-bold text-slate-900">Authoritative Form State</h3>
          <p className="text-xs text-slate-500">Live memory state managed by FormStateManager</p>
        </div>
        <div className="text-right">
          <span className="text-[11px] font-medium text-slate-400">Last Mutation Version</span>
          <div className="text-xs font-mono font-bold text-slate-800">
            v{formState.last_updated_version || activeVersion}
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-4 flex-1">
        {/* Postal Code Highlighted Field (Target of Stress Test) */}
        <div className="p-4 rounded-xl border-2 border-indigo-100 bg-slate-50/70 relative">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-indigo-600" />
              <label className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Target Field: Postal Code
              </label>
            </div>
            {getStatusBadge(postalField.status)}
          </div>

          <div className="mt-3 flex items-center justify-between bg-white p-3 rounded-lg border border-slate-200 shadow-2xs">
            <div>
              <span className="text-[11px] text-slate-400 block">Current Form Value</span>
              <span className="text-xl font-mono font-black text-slate-900">
                {postalField.value || '— (Empty)'}
              </span>
            </div>
            <div className="text-right">
              <span className="text-[11px] text-slate-400 block">Field Version Tag</span>
              <span className="inline-flex items-center gap-1 text-xs font-mono font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                <ShieldCheck className="w-3.5 h-3.5" />
                v{postalField.interaction_version}
              </span>
            </div>
          </div>

          {/* Validation Details if available */}
          {postalField.validation_details && (
            <div className="mt-2.5 p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-900">
              <div className="font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Verified Geographical Location:
              </div>
              <div className="mt-1 font-mono text-[11px]">
                {postalField.validation_details.city}, {postalField.validation_details.state}
              </div>
            </div>
          )}
        </div>

        {/* Other Form Fields (Read-Only Preview of Structured Form) */}
        <div className="space-y-2 pt-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
            Other Form Fields (Voice Schema Preview)
          </span>

          {Object.entries(formState.fields || {})
            .filter(([key]) => key !== 'postal_code')
            .slice(0, 4)
            .map(([key, fieldVal]) => {
              const field = fieldVal as FormFieldValue;
              return (
                <div
                  key={key}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100 text-xs"
                >
                  <div>
                    <span className="font-medium text-slate-700 block">{field.label || key}</span>
                    <span className="font-mono text-slate-500 text-[11px]">{field.value || '—'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-slate-400">v{field.interaction_version}</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-200 text-slate-600">
                      {field.status}
                    </span>
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-400 flex items-center justify-between">
        <span>Fenced State Mutator</span>
        <span className="font-mono">Thread-Safe AsyncIO Locks</span>
      </div>
    </div>
  );
};
