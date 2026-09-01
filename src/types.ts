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

export type VoiceState =
  | 'IDLE'
  | 'LISTENING'
  | 'PROCESSING'
  | 'ASSISTANT_SPEAKING'
  | 'INTERRUPTED';

export interface FormFieldValue {
  name: string;
  label: string;
  value: string;
  status: FieldStatus;
  validationStatus: ValidationStatus;
  updatedAt: string;
  interactionVersion: number;
  errorMessage?: string;
  validationDetails?: {
    city?: string;
    state?: string;
    message?: string;
  };
}

export interface FormState {
  fields: {
    fullName: FormFieldValue;
    dateOfBirth: FormFieldValue;
    phoneNumber: FormFieldValue;
    email: FormFieldValue;
    address: FormFieldValue;
    city: FormFieldValue;
    state: FormFieldValue;
    postalCode: FormFieldValue;
    occupation: FormFieldValue;
    employmentStatus: FormFieldValue;
  };
  activeFieldKey: string;
  lastUpdatedVersion: number;
}

export interface AsyncTaskRecord {
  taskId: string;
  name: string;
  targetField?: string;
  version: number;
  status: TaskStatus;
  createdAt: string;
  completedAt?: string;
  cancelledAt?: string;
  payload?: any;
  result?: any;
}

export interface SystemEventLog {
  id: string;
  timestamp: string;
  eventType: string;
  interactionVersion: number;
  activeVersion: number;
  message: string;
  details?: Record<string, any>;
  isStaleBlocked?: boolean;
}

export interface SystemMetrics {
  interruptionsCount: number;
  activeTasksCount: number;
  cancelledTasksCount: number;
  staleResultsBlockedCount: number;
  versionsCreatedCount: number;
  interruptionToAudioStopTimeMs?: number;
}

export interface InteractionState {
  activeInteractionVersion: number;
  voiceState: VoiceState;
  currentTranscript: string;
  currentAssistantResponse: string;
  speechProvider: 'Rime' | 'WebAudio' | 'Simulated';
  speechProviderStatus: 'Active' | 'Inactive' | 'Error';
  artificialToolDelaySeconds: number;
  demoModeEnabled: boolean;
}
