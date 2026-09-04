/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  SpeechRecognitionProvider,
  BrowserSpeechRecognitionProvider,
  MockSpeechRecognitionProvider,
  SpeechRecognitionState,
} from './speechRecognitionProvider';
import { audioPlaybackManager, AudioPlaybackManager } from './audioPlaybackManager';
import { FormState, TimelineEvent } from '../types';

export interface VoiceInteractionMetrics {
  voiceInteractionsCount: number;
  voiceInterruptionsCount: number;
  audioInterruptedForUserInputCount: number;
  speechRecognitionErrorsCount: number;
  finalTranscriptsAcceptedCount: number;
  staleResultsBlockedAfterVoiceCount: number;
  voiceActivationToStopLatencyMs: number | null;
  isRealLatencyMeasurement: boolean;
}

export interface VoiceInteractionState {
  micStatus: SpeechRecognitionState;
  providerType: 'browser' | 'mock';
  providerName: string;
  isSupported: boolean;
  activeVersion: number;
  interimTranscript: string;
  finalTranscript: string;
  isBargeInActive: boolean;
  lastInterruptionEvent: string | null;
  errorMessage: string | null;
  metrics: VoiceInteractionMetrics;
}

export type VoiceStateListener = (state: VoiceInteractionState) => void;

export class VoiceInteractionManager {
  private browserProvider: BrowserSpeechRecognitionProvider;
  private mockProvider: MockSpeechRecognitionProvider;
  private activeProvider: SpeechRecognitionProvider;
  private providerType: 'browser' | 'mock' = 'browser';
  private playbackManager: AudioPlaybackManager;

  private micStatus: SpeechRecognitionState = 'IDLE';
  private activeVersion: number = 10;
  private interimTranscript: string = '';
  private finalTranscript: string = '';
  private isBargeInActive: boolean = false;
  private lastInterruptionEvent: string | null = null;
  private errorMessage: string | null = null;

  private metrics: VoiceInteractionMetrics = {
    voiceInteractionsCount: 0,
    voiceInterruptionsCount: 0,
    audioInterruptedForUserInputCount: 0,
    speechRecognitionErrorsCount: 0,
    finalTranscriptsAcceptedCount: 0,
    staleResultsBlockedAfterVoiceCount: 0,
    voiceActivationToStopLatencyMs: null,
    isRealLatencyMeasurement: false,
  };

  private listeners: Set<VoiceStateListener> = new Set();
  private onTranscriptSubmittedCallback?: (text: string, source: string) => Promise<any>;
  private onTimelineEventCallback?: (event: Partial<TimelineEvent>) => void;

  constructor(playbackMgr: AudioPlaybackManager = audioPlaybackManager) {
    this.browserProvider = new BrowserSpeechRecognitionProvider();
    this.mockProvider = new MockSpeechRecognitionProvider();
    this.playbackManager = playbackMgr;

    // Default to browser provider if supported, else mock provider
    if (this.browserProvider.isSupported()) {
      this.activeProvider = this.browserProvider;
      this.providerType = 'browser';
      this.metrics.isRealLatencyMeasurement = true;
    } else {
      this.activeProvider = this.mockProvider;
      this.providerType = 'mock';
      this.metrics.isRealLatencyMeasurement = false;
    }

    this.wireProviderCallbacks(this.activeProvider);

    // Sync active version with playback manager
    this.playbackManager.subscribe((playbackState) => {
      this.activeVersion = playbackState.activeVersion;
      this.notify();
    });
  }

  public setSubmitCallback(cb: (text: string, source: string) => Promise<any>) {
    this.onTranscriptSubmittedCallback = cb;
  }

  public setTimelineEventCallback(cb: (event: Partial<TimelineEvent>) => void) {
    this.onTimelineEventCallback = cb;
  }

  public subscribe(listener: VoiceStateListener): () => void {
    this.listeners.add(listener);
    this.notify();
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify() {
    const state = this.getState();
    this.listeners.forEach((fn) => {
      try {
        fn(state);
      } catch (err) {
        console.error('VoiceInteractionManager listener error:', err);
      }
    });
  }

  public getState(): VoiceInteractionState {
    return {
      micStatus: this.micStatus,
      providerType: this.providerType,
      providerName: this.activeProvider.providerName,
      isSupported: this.activeProvider.isSupported(),
      activeVersion: this.activeVersion,
      interimTranscript: this.interimTranscript,
      finalTranscript: this.finalTranscript,
      isBargeInActive: this.isBargeInActive,
      lastInterruptionEvent: this.lastInterruptionEvent,
      errorMessage: this.errorMessage,
      metrics: { ...this.metrics },
    };
  }

  public getMockProvider(): MockSpeechRecognitionProvider {
    return this.mockProvider;
  }

  public switchProvider(type: 'browser' | 'mock') {
    if (this.micStatus === 'LISTENING') {
      this.stopListening();
    }

    this.providerType = type;
    if (type === 'browser') {
      this.activeProvider = this.browserProvider;
      this.metrics.isRealLatencyMeasurement = true;
    } else {
      this.activeProvider = this.mockProvider;
      this.metrics.isRealLatencyMeasurement = false;
    }

    this.wireProviderCallbacks(this.activeProvider);
    this.micStatus = this.activeProvider.getState();
    this.errorMessage = null;
    this.notify();
  }

  private wireProviderCallbacks(provider: SpeechRecognitionProvider) {
    provider.setCallbacks({
      onStateChange: (newState) => {
        this.micStatus = newState;
        this.notify();
      },
      onInterimTranscript: (text) => {
        this.interimTranscript = text;
        this.notify();
      },
      onFinalTranscript: (text) => {
        this.finalTranscript = text;
        this.interimTranscript = '';
        this.metrics.finalTranscriptsAcceptedCount++;
        this.notify();
        this.handleFinalTranscript(text);
      },
      onError: (err, isPermissionDenied) => {
        this.micStatus = 'ERROR';
        this.metrics.speechRecognitionErrorsCount++;
        this.errorMessage = isPermissionDenied
          ? 'Microphone permission denied. Please allow microphone access or switch to Mock STT.'
          : `Speech Recognition Error: ${err}`;
        this.notify();
      },
    });
  }

  /**
   * Primary voice interaction activation.
   * Immediately executes Barge-In interruption:
   * 1. Stops browser speaker playback synchronously.
   * 2. Clears obsolete queued audio.
   * 3. Calculates precise interruption stop latency.
   * 4. Starts speech-to-text recognition.
   */
  public async startVoiceInteraction(): Promise<void> {
    this.errorMessage = null;
    this.interimTranscript = '';
    this.metrics.voiceInteractionsCount++;

    // Measure interruption stop latency if audio was playing
    const wasPlaying = this.playbackManager.getStatus() === 'PLAYING';
    const stopStartTime = performance.now();

    // Checkpoint: Synchronous audio stop & queue purge
    this.playbackManager.stopCurrentAudio('User Voice Barge-in');
    this.playbackManager.clearQueue();

    if (wasPlaying) {
      const stopDuration = performance.now() - stopStartTime;
      const formattedLatency = Math.round(stopDuration * 100) / 100;
      this.metrics.voiceInterruptionsCount++;
      this.metrics.audioInterruptedForUserInputCount++;
      this.metrics.voiceActivationToStopLatencyMs = formattedLatency;
      this.isBargeInActive = true;
      this.lastInterruptionEvent = `AUDIO_INTERRUPTED_FOR_USER_INPUT (${formattedLatency}ms)`;

      this.onTimelineEventCallback?.({
        event_type: 'USER_INTERRUPTION_DETECTED',
        interaction_version: this.activeVersion,
        active_version: this.activeVersion,
        message: `Voice barge-in detected; audio playback stopped in ${formattedLatency}ms`,
        details: { latency_ms: formattedLatency, is_real: this.metrics.isRealLatencyMeasurement },
      });
    } else {
      this.isBargeInActive = false;
    }

    this.onTimelineEventCallback?.({
      event_type: 'LISTENING_STARTED',
      interaction_version: this.activeVersion,
      active_version: this.activeVersion,
      message: `Microphone listening started via ${this.activeProvider.providerName}`,
    });

    this.notify();

    // Start speech recognition
    try {
      await this.activeProvider.start({
        continuous: false,
        interimResults: true,
        lang: 'en-US',
      });
    } catch (err: any) {
      this.micStatus = 'ERROR';
      this.errorMessage = err?.message || 'Failed to start speech recognition';
      this.notify();
    }
  }

  public async stopListening(): Promise<void> {
    await this.activeProvider.stop();
    this.micStatus = 'IDLE';
    this.notify();
  }

  public async cancelInteraction(): Promise<void> {
    await this.activeProvider.abort();
    this.interimTranscript = '';
    this.micStatus = 'IDLE';
    this.isBargeInActive = false;
    this.notify();
  }

  private async handleFinalTranscript(text: string) {
    const cleanText = text.trim();
    if (!cleanText) {
      this.micStatus = 'IDLE';
      this.notify();
      return;
    }

    this.onTimelineEventCallback?.({
      event_type: 'FINAL_TRANSCRIPT_RECEIVED',
      interaction_version: this.activeVersion,
      active_version: this.activeVersion,
      message: `Final transcript received: "${cleanText}"`,
      details: { transcript: cleanText, source: 'voice' },
    });

    if (this.onTranscriptSubmittedCallback) {
      try {
        await this.onTranscriptSubmittedCallback(cleanText, 'voice');
      } catch (err) {
        console.error('Error dispatching voice transcript:', err);
      }
    }

    this.micStatus = 'IDLE';
    this.notify();
  }

  public recordStaleBlockedAfterVoice() {
    this.metrics.staleResultsBlockedAfterVoiceCount++;
    this.notify();
  }

  public setActiveVersion(version: number) {
    this.activeVersion = version;
    this.notify();
  }

  public reset(initialVersion: number = 10) {
    this.cancelInteraction();
    this.activeVersion = initialVersion;
    this.interimTranscript = '';
    this.finalTranscript = '';
    this.isBargeInActive = false;
    this.lastInterruptionEvent = null;
    this.errorMessage = null;
    this.metrics = {
      voiceInteractionsCount: 0,
      voiceInterruptionsCount: 0,
      audioInterruptedForUserInputCount: 0,
      speechRecognitionErrorsCount: 0,
      finalTranscriptsAcceptedCount: 0,
      staleResultsBlockedAfterVoiceCount: 0,
      voiceActivationToStopLatencyMs: null,
      isRealLatencyMeasurement: this.providerType === 'browser',
    };
    this.notify();
  }
}

// Global singleton for voice interaction manager
export const voiceInteractionManager = new VoiceInteractionManager(audioPlaybackManager);
