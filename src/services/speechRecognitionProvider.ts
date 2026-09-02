/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type SpeechRecognitionState =
  | 'IDLE'
  | 'LISTENING'
  | 'PROCESSING'
  | 'ERROR'
  | 'UNSUPPORTED';

export interface SpeechRecognitionCallbacks {
  onStateChange?: (state: SpeechRecognitionState) => void;
  onInterimTranscript?: (text: string) => void;
  onFinalTranscript?: (text: string) => void;
  onError?: (error: string, isPermissionDenied?: boolean) => void;
}

export interface SpeechRecognitionProvider {
  readonly providerName: string;
  isSupported(): boolean;
  getState(): SpeechRecognitionState;
  start(options?: { continuous?: boolean; interimResults?: boolean; lang?: string }): Promise<void>;
  stop(): Promise<void>;
  abort(): Promise<void>;
  setCallbacks(callbacks: SpeechRecognitionCallbacks): void;
}

/**
 * Real Web Speech API Browser Provider
 */
export class BrowserSpeechRecognitionProvider implements SpeechRecognitionProvider {
  public readonly providerName = 'Browser Web Speech API';
  private recognition: any = null;
  private state: SpeechRecognitionState = 'IDLE';
  private callbacks: SpeechRecognitionCallbacks = {};
  private isListening: boolean = false;

  constructor() {
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      this.state = 'UNSUPPORTED';
    }
  }

  public isSupported(): boolean {
    return typeof window !== 'undefined' && (!!(window as any).SpeechRecognition || !!(window as any).webkitSpeechRecognition);
  }

  public getState(): SpeechRecognitionState {
    return this.state;
  }

  public setCallbacks(callbacks: SpeechRecognitionCallbacks): void {
    this.callbacks = callbacks;
  }

  private setState(newState: SpeechRecognitionState) {
    this.state = newState;
    this.callbacks.onStateChange?.(newState);
  }

  public async start(options?: { continuous?: boolean; interimResults?: boolean; lang?: string }): Promise<void> {
    if (!this.isSupported()) {
      this.setState('UNSUPPORTED');
      this.callbacks.onError?.('Speech recognition is not supported in this browser.', false);
      return;
    }

    if (this.isListening) {
      await this.abort();
    }

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRec();

    recognition.continuous = options?.continuous ?? false;
    recognition.interimResults = options?.interimResults ?? true;
    recognition.lang = options?.lang ?? 'en-US';

    recognition.onstart = () => {
      this.isListening = true;
      this.setState('LISTENING');
    };

    recognition.onresult = (event: any) => {
      let interim = '';
      let final = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const item = event.results[i];
        const transcriptText = item[0].transcript;
        if (item.isFinal) {
          final += transcriptText;
        } else {
          interim += transcriptText;
        }
      }

      if (interim) {
        this.callbacks.onInterimTranscript?.(interim);
      }

      if (final) {
        this.setState('PROCESSING');
        this.callbacks.onFinalTranscript?.(final);
      }
    };

    recognition.onerror = (event: any) => {
      this.isListening = false;
      const err = event.error || 'Speech recognition error';
      const isPermissionDenied = err === 'not-allowed' || err === 'service-not-allowed';
      this.setState('ERROR');
      this.callbacks.onError?.(err, isPermissionDenied);
    };

    recognition.onend = () => {
      this.isListening = false;
      if (this.state === 'LISTENING') {
        this.setState('IDLE');
      }
    };

    this.recognition = recognition;

    try {
      recognition.start();
    } catch (err: any) {
      this.isListening = false;
      this.setState('ERROR');
      this.callbacks.onError?.(err?.message || 'Failed to start microphone speech recognition', false);
    }
  }

  public async stop(): Promise<void> {
    if (this.recognition && this.isListening) {
      try {
        this.recognition.stop();
      } catch (err) {
        console.warn('Recognition stop warning:', err);
      }
    }
    this.isListening = false;
    this.setState('IDLE');
  }

  public async abort(): Promise<void> {
    if (this.recognition && this.isListening) {
      try {
        this.recognition.abort();
      } catch (err) {
        console.warn('Recognition abort warning:', err);
      }
    }
    this.isListening = false;
    this.setState('IDLE');
  }
}

/**
 * Mock Speech Recognition Provider for deterministic testing and simulations
 */
export class MockSpeechRecognitionProvider implements SpeechRecognitionProvider {
  public readonly providerName = 'Mock Speech Recognition Provider';
  private state: SpeechRecognitionState = 'IDLE';
  private callbacks: SpeechRecognitionCallbacks = {};
  private activeTimeout: any = null;

  public simulatedTranscript: string = 'My postal code is 600001';
  public interimSteps: string[] = ['My postal', 'My postal code', 'My postal code is 600001'];
  public stepDelayMs: number = 200;
  public shouldFail: boolean = false;
  public permissionDenied: boolean = false;
  public errorMessage: string = 'Simulated speech recognition error';

  public isSupported(): boolean {
    return true;
  }

  public getState(): SpeechRecognitionState {
    return this.state;
  }

  public setCallbacks(callbacks: SpeechRecognitionCallbacks): void {
    this.callbacks = callbacks;
  }

  private setState(newState: SpeechRecognitionState) {
    this.state = newState;
    this.callbacks.onStateChange?.(newState);
  }

  public configure(config: {
    simulatedTranscript?: string;
    interimSteps?: string[];
    stepDelayMs?: number;
    shouldFail?: boolean;
    permissionDenied?: boolean;
    errorMessage?: string;
  }) {
    if (config.simulatedTranscript !== undefined) this.simulatedTranscript = config.simulatedTranscript;
    if (config.interimSteps !== undefined) this.interimSteps = config.interimSteps;
    if (config.stepDelayMs !== undefined) this.stepDelayMs = config.stepDelayMs;
    if (config.shouldFail !== undefined) this.shouldFail = config.shouldFail;
    if (config.permissionDenied !== undefined) this.permissionDenied = config.permissionDenied;
    if (config.errorMessage !== undefined) this.errorMessage = config.errorMessage;
  }

  public async start(): Promise<void> {
    this.clearTimer();

    if (this.permissionDenied) {
      this.setState('ERROR');
      this.callbacks.onError?.('Microphone permission denied', true);
      return;
    }

    if (this.shouldFail) {
      this.setState('ERROR');
      this.callbacks.onError?.(this.errorMessage, false);
      return;
    }

    this.setState('LISTENING');

    // Simulate progressive interim transcripts followed by final transcript
    let stepIndex = 0;
    const runNextStep = () => {
      if (stepIndex < this.interimSteps.length) {
        const text = this.interimSteps[stepIndex];
        this.callbacks.onInterimTranscript?.(text);
        stepIndex++;
        this.activeTimeout = setTimeout(runNextStep, this.stepDelayMs);
      } else {
        this.setState('PROCESSING');
        this.callbacks.onFinalTranscript?.(this.simulatedTranscript);
        this.setState('IDLE');
      }
    };

    this.activeTimeout = setTimeout(runNextStep, this.stepDelayMs);
  }

  public async stop(): Promise<void> {
    this.clearTimer();
    this.setState('IDLE');
  }

  public async abort(): Promise<void> {
    this.clearTimer();
    this.setState('IDLE');
  }

  private clearTimer() {
    if (this.activeTimeout) {
      clearTimeout(this.activeTimeout);
      this.activeTimeout = null;
    }
  }
}
