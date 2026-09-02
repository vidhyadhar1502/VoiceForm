/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type FieldStatus =
  | 'EMPTY'
  | 'ACTIVE'
  | 'PROCESSING'
  | 'VALIDATING'
  | 'CONFIRMED'
  | 'SKIPPED'
  | 'STALE_RESULT_BLOCKED';

export type ValidationStatus =
  | 'UNVALIDATED'
  | 'VALIDATING'
  | 'VALID'
  | 'INVALID'
  | 'STALE_BLOCKED';

export type TaskStatus =
  | 'ACTIVE'
  | 'RUNNING'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'STALE_BLOCKED'
  | 'FAILED';

export interface FormFieldValue {
  name: string;
  label: string;
  value: string;
  status: FieldStatus;
  validation_status: ValidationStatus;
  updated_at: string;
  interaction_version: number;
  error_message?: string;
  validation_details?: {
    city?: string;
    state?: string;
    message?: string;
    [key: string]: any;
  };
}

export interface FormState {
  fields: Record<string, FormFieldValue>;
  active_field_key?: string;
  last_updated_version: number;
}

export interface TaskRecord {
  task_id: string;
  name: string;
  target_field?: string;
  version: number;
  status: TaskStatus;
  created_at: string;
  completed_at?: string;
  cancelled_at?: string;
  payload?: any;
  result?: any;
  uncancellable?: boolean;
}

export interface TimelineEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  interaction_version: number;
  active_version: number;
  task_id?: string;
  message: string;
  is_stale_blocked?: boolean;
  details?: Record<string, any>;
}

export interface StructuredAction {
  action: string;
  target_field?: string;
  value?: string;
  requires_validation: boolean;
  response_text: string;
  is_valid: boolean;
  validation_error?: string;
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  text: string;
  interaction_version: number;
  active_version: number;
  structured_action?: StructuredAction;
  timestamp: string;
}

export interface StressTestResponse {
  test_run_id: string;
  mode: string;
  final_interaction_version: number;
  final_form_state: FormState;
  stale_results_blocked: number;
  cancelled_tasks_count: number;
  event_timeline: TimelineEvent[];
  test_success: boolean;
  summary: string;
}

export interface SystemSnapshot {
  active_version: number;
  form_state: FormState;
  tasks: TaskRecord[];
  stale_results_blocked: number;
  cancelled_tasks_count: number;
  active_tasks_count: number;
  timeline: TimelineEvent[];
}

export type SpeechStatus =
  | 'IDLE'
  | 'GENERATING'
  | 'QUEUED'
  | 'PLAYING'
  | 'INTERRUPTED'
  | 'BLOCKED_STALE';

export interface SpeechProviderInfo {
  provider_name: string;
  is_fallback: boolean;
  rime_configured: boolean;
  model: string;
  voice: string;
  endpoint?: string;
}

export interface SpeechMetrics {
  total_tts_requests: number;
  cancelled_tts_requests: number;
  completed_tts_requests: number;
  stale_tts_results_blocked: number;
  audio_interruptions: number;
  audio_stop_requests: number;
  interruption_stop_latency_ms?: number;
}

export interface AudioQueueItem {
  id: string;
  interaction_version: number;
  audio_url: string;
  audio_base64?: string;
  format?: string;
  task_id?: string;
  provider?: string;
}

