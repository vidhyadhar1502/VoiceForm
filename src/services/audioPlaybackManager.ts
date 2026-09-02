/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { AudioQueueItem, SpeechStatus } from '../types';

export type AudioStateListener = (state: {
  status: SpeechStatus;
  activeVersion: number;
  currentPlayingVersion: number | null;
  queueLength: number;
  lastBlockedVersion: number | null;
  interruptionLatencyMs: number | null;
}) => void;

export class AudioPlaybackManager {
  private activeVersion: number = 10;
  private currentPlayingVersion: number | null = null;
  private status: SpeechStatus = 'IDLE';
  private queue: AudioQueueItem[] = [];
  private currentAudioElement: HTMLAudioElement | null = null;
  private lastBlockedVersion: number | null = null;
  private lastInterruptionTime: number | null = null;
  private interruptionLatencyMs: number | null = null;
  private listeners: Set<AudioStateListener> = new Set();
  private onPlaybackEventCallback?: (eventType: string, version: number, taskId?: string, details?: any) => void;

  constructor(initialVersion: number = 10) {
    this.activeVersion = initialVersion;
  }

  public subscribe(listener: AudioStateListener): () => void {
    this.listeners.add(listener);
    this.notify();
    return () => {
      this.listeners.delete(listener);
    };
  }

  public setPlaybackEventCallback(cb: (eventType: string, version: number, taskId?: string, details?: any) => void) {
    this.onPlaybackEventCallback = cb;
  }

  private notify() {
    const state = {
      status: this.status,
      activeVersion: this.activeVersion,
      currentPlayingVersion: this.currentPlayingVersion,
      queueLength: this.queue.length,
      lastBlockedVersion: this.lastBlockedVersion,
      interruptionLatencyMs: this.interruptionLatencyMs,
    };
    this.listeners.forEach((fn) => {
      try {
        fn(state);
      } catch (err) {
        console.error('AudioPlaybackManager listener error:', err);
      }
    });
  }

  public getStatus(): SpeechStatus {
    return this.status;
  }

  public getActiveVersion(): number {
    return this.activeVersion;
  }

  public getCurrentPlayingVersion(): number | null {
    return this.currentPlayingVersion;
  }

  public isAudioCurrent(version: number): boolean {
    return version === this.activeVersion;
  }

  /**
   * Updates the active interaction version.
   * Immediately stops audio and clears obsolete queues if an interruption occurred.
   */
  public setActiveVersion(newVersion: number, reason: string = 'User Interaction') {
    const oldVersion = this.activeVersion;
    this.activeVersion = newVersion;

    // Check if audio of an older version was currently playing
    if (this.currentPlayingVersion !== null && this.currentPlayingVersion < newVersion) {
      const stopStartTime = performance.now();
      const stoppedVersion = this.currentPlayingVersion;
      this.stopCurrentAudio(`Interaction invalidated (v${stoppedVersion} -> v${newVersion})`);
      const latency = performance.now() - stopStartTime;
      this.interruptionLatencyMs = Math.round(latency * 100) / 100;
      this.status = 'INTERRUPTED';

      if (this.onPlaybackEventCallback) {
        this.onPlaybackEventCallback('AUDIO_PLAYBACK_STOPPED', stoppedVersion, undefined, {
          reason: 'interaction_invalidated',
          active_version: newVersion,
          interruption_latency_ms: this.interruptionLatencyMs,
        });
      }
    }

    // Purge queued items belonging to obsolete versions
    const initialQueueLen = this.queue.length;
    this.queue = this.queue.filter((item) => item.interaction_version === newVersion);
    if (initialQueueLen > this.queue.length && this.onPlaybackEventCallback) {
      this.onPlaybackEventCallback('AUDIO_QUEUE_CLEARED', oldVersion, undefined, {
        active_version: newVersion,
        items_cleared: initialQueueLen - this.queue.length,
      });
    }

    if (this.queue.length === 0 && this.status === 'QUEUED') {
      this.status = 'IDLE';
    }

    this.notify();
  }

  /**
   * Checkpoint 4: Version check before enqueuing audio for playback.
   */
  public enqueueAudio(item: AudioQueueItem) {
    if (item.interaction_version !== this.activeVersion) {
      // Discard stale audio payload
      this.lastBlockedVersion = item.interaction_version;
      this.status = 'BLOCKED_STALE';
      if (this.onPlaybackEventCallback) {
        this.onPlaybackEventCallback('TTS_RESULT_BLOCKED_STALE', item.interaction_version, item.task_id, {
          active_version: this.activeVersion,
          checkpoint: 'Checkpoint 4 (Frontend Enqueue Guard)',
          message: `Blocked v${item.interaction_version} audio from entering playback queue.`,
        });
      }
      this.notify();
      return false;
    }

    this.queue.push(item);
    if (this.status !== 'PLAYING') {
      this.status = 'QUEUED';
    }

    if (this.onPlaybackEventCallback) {
      this.onPlaybackEventCallback('AUDIO_QUEUED', item.interaction_version, item.task_id, {
        queue_position: this.queue.length,
      });
    }

    this.notify();

    // If not currently playing, start immediately
    if (this.currentPlayingVersion === null) {
      this.playNext();
    }
    return true;
  }

  /**
   * Checkpoint 5: Version check immediately before playback start.
   */
  public playNext() {
    if (this.queue.length === 0) {
      if (this.status !== 'INTERRUPTED' && this.status !== 'BLOCKED_STALE') {
        this.status = 'IDLE';
      }
      this.currentPlayingVersion = null;
      this.notify();
      return;
    }

    const item = this.queue.shift();
    if (!item) return;

    // Checkpoint 5 Verification
    if (item.interaction_version !== this.activeVersion) {
      this.lastBlockedVersion = item.interaction_version;
      this.status = 'BLOCKED_STALE';
      if (this.onPlaybackEventCallback) {
        this.onPlaybackEventCallback('TTS_RESULT_BLOCKED_STALE', item.interaction_version, item.task_id, {
          active_version: this.activeVersion,
          checkpoint: 'Checkpoint 5 (Immediate Pre-Playback Guard)',
          message: `Blocked v${item.interaction_version} audio immediately before browser speaker playback.`,
        });
      }
      this.notify();
      // Continue to next item in queue
      this.playNext();
      return;
    }

    this.currentPlayingVersion = item.interaction_version;
    this.status = 'PLAYING';
    this.notify();

    if (this.onPlaybackEventCallback) {
      this.onPlaybackEventCallback('AUDIO_PLAYBACK_STARTED', item.interaction_version, item.task_id, {
        provider: item.provider || 'Rime',
      });
    }

    try {
      const audio = new Audio(item.audio_url);
      this.currentAudioElement = audio;

      audio.onended = () => {
        if (this.currentPlayingVersion === item.interaction_version) {
          if (this.onPlaybackEventCallback) {
            this.onPlaybackEventCallback('AUDIO_PLAYBACK_COMPLETED', item.interaction_version, item.task_id);
          }
          this.currentAudioElement = null;
          this.currentPlayingVersion = null;
          this.playNext();
        }
      };

      audio.onerror = (e) => {
        console.warn('Audio playback encountered error, proceeding to next item:', e);
        this.currentAudioElement = null;
        this.currentPlayingVersion = null;
        this.playNext();
      };

      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn('Browser audio autoplay policy prevented playback or interrupted:', err);
          // If interrupted or prevented, clean up smoothly
          if (this.currentPlayingVersion === item.interaction_version) {
            this.currentAudioElement = null;
            this.currentPlayingVersion = null;
            this.playNext();
          }
        });
      }
    } catch (err) {
      console.error('Audio initialization failed:', err);
      this.currentAudioElement = null;
      this.currentPlayingVersion = null;
      this.playNext();
    }
  }

  /**
   * Immediately stops the active browser audio playback element.
   */
  public stopCurrentAudio(reason: string = 'User Stopped Playback') {
    if (this.currentAudioElement) {
      try {
        this.currentAudioElement.pause();
        this.currentAudioElement.currentTime = 0;
        this.currentAudioElement.src = '';
      } catch (err) {
        console.warn('Error stopping audio element:', err);
      }
      this.currentAudioElement = null;
    }

    const stoppedVersion = this.currentPlayingVersion;
    this.currentPlayingVersion = null;
    this.status = 'IDLE';

    if (stoppedVersion !== null && this.onPlaybackEventCallback) {
      this.onPlaybackEventCallback('AUDIO_PLAYBACK_STOPPED', stoppedVersion, undefined, {
        reason,
        active_version: this.activeVersion,
      });
    }

    this.notify();
  }

  public clearQueue() {
    const count = this.queue.length;
    this.queue = [];
    if (count > 0 && this.onPlaybackEventCallback) {
      this.onPlaybackEventCallback('AUDIO_QUEUE_CLEARED', this.activeVersion, undefined, {
        items_cleared: count,
      });
    }
    this.notify();
  }

  public reset(initialVersion: number = 10) {
    this.stopCurrentAudio('Reset');
    this.clearQueue();
    this.activeVersion = initialVersion;
    this.currentPlayingVersion = null;
    this.lastBlockedVersion = null;
    this.interruptionLatencyMs = null;
    this.status = 'IDLE';
    this.notify();
  }
}

// Global audio playback manager singleton
export const audioPlaybackManager = new AudioPlaybackManager(10);
