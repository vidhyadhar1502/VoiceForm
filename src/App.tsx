import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Header } from './components/Header';
import { MetricsCards } from './components/MetricsCards';
import { StressTestControls } from './components/StressTestControls';
import { FormStateViewer } from './components/FormStateViewer';
import { EventTimeline } from './components/EventTimeline';
import { TaskRegistryViewer } from './components/TaskRegistryViewer';
import { ConversationPanel } from './components/ConversationPanel';
import { SpeechStatusPanel } from './components/SpeechStatusPanel';
import { VoiceInteractionPanel } from './components/VoiceInteractionPanel';
import {
  FormState,
  TaskRecord,
  TimelineEvent,
  StressTestResponse,
  ConversationMessage,
  SpeechStatus,
  SpeechProviderInfo,
  SpeechMetrics,
  AudioQueueItem,
  VoiceState,
} from './types';
import { audioPlaybackManager } from './services/audioPlaybackManager';
import { voiceInteractionManager } from './services/voiceInteractionManager';
import { Sparkles, Activity, Volume2, Mic } from 'lucide-react';

export const App: React.FC = () => {
  // State
  const [activeVersion, setActiveVersion] = useState<number>(10);
  const [formState, setFormState] = useState<FormState>({
    fields: {},
    last_updated_version: 10,
  });
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [staleBlocksCount, setStaleBlocksCount] = useState<number>(0);
  const [cancelledTasksCount, setCancelledTasksCount] = useState<number>(0);
  const [activeTasksCount, setActiveTasksCount] = useState<number>(0);
  const [isWsConnected, setIsWsConnected] = useState<boolean>(false);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isProcessingAi, setIsProcessingAi] = useState<boolean>(false);
  const [isTestingVoice, setIsTestingVoice] = useState<boolean>(false);
  const [testSuccess, setTestSuccess] = useState<boolean | null>(null);

  // Speech & Audio state
  const [speechStatus, setSpeechStatus] = useState<SpeechStatus>('IDLE');
  const [currentPlayingVersion, setCurrentPlayingVersion] = useState<number | null>(null);
  const [lastBlockedAudioVersion, setLastBlockedAudioVersion] = useState<number | null>(null);
  const [interruptionLatencyMs, setInterruptionLatencyMs] = useState<number | null>(null);
  const [providerInfo, setProviderInfo] = useState<SpeechProviderInfo>({
    provider_name: 'Connecting...',
    is_fallback: false,
    rime_configured: false,
    model: '',
    voice: '',
    endpoint: '',
  });
  const [speechMetrics, setSpeechMetrics] = useState<SpeechMetrics>({
    total_tts_requests: 0,
    cancelled_tts_requests: 0,
    completed_tts_requests: 0,
    stale_tts_results_blocked: 0,
    audio_interruptions: 0,
    audio_stop_requests: 0,
  });

  // Voice Interaction state
  const [voiceState, setVoiceState] = useState<VoiceState>(voiceInteractionManager.getState());

  // Active View Mode
  const [activeTab, setActiveTab] = useState<'conversation' | 'stresstest'>('conversation');

  // Controls configuration
  const [mode, setMode] = useState<'uncancellable' | 'cancellable'>('uncancellable');
  const [oldPostalCode, setOldPostalCode] = useState<string>('600001');
  const [newPostalCode, setNewPostalCode] = useState<string>('600028');
  const [validationDelay, setValidationDelay] = useState<number>(3.0);
  const [interruptTiming, setInterruptTiming] = useState<number>(1.0);

  const wsRef = useRef<WebSocket | null>(null);

  // Fetch speech status & metrics
  const fetchSpeechStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/speech/status');
      if (res.ok) {
        const data = await res.json();
        const pInfo = data.provider_info || {};
        setProviderInfo({
          provider_name: pInfo.provider_name || 'Mock (Deterministic)',
          is_fallback: Boolean(pInfo.is_fallback),
          rime_configured: Boolean(pInfo.rime_configured),
          model: pInfo.model || '',
          voice: pInfo.voice || '',
          endpoint: pInfo.endpoint || '',
        });
        setSpeechMetrics(data.metrics || {
          total_tts_requests: 0,
          cancelled_tts_requests: 0,
          completed_tts_requests: 0,
          stale_tts_results_blocked: 0,
          audio_interruptions: 0,
          audio_stop_requests: 0,
        });
      }
    } catch {
      // Backend may be starting
    }
  }, []);

  // Poll state snapshot
  const fetchStateSnapshot = useCallback(async () => {
    try {
      const res = await fetch('/api/demo/state');
      if (res.ok) {
        const data = await res.json();
        setActiveVersion(data.active_version);
        audioPlaybackManager.setActiveVersion(data.active_version);
        setFormState(data.form_state);
        setTasks(data.tasks || []);
        setStaleBlocksCount(data.stale_results_blocked || 0);
        setCancelledTasksCount(data.cancelled_tasks_count || 0);
        setActiveTasksCount(data.active_tasks_count || 0);
        if (data.timeline && data.timeline.length > 0) {
          setTimeline(data.timeline);
        }
      }

      const convRes = await fetch('/api/conversation/history');
      if (convRes.ok) {
        const convData = await convRes.json();
        setMessages(convData.messages || []);
      }

      await fetchSpeechStatus();
    } catch {
      // Backend may be booting up
    }
  }, [fetchSpeechStatus]);

  // Audio Playback & Voice Interaction Manager Subscriptions
  useEffect(() => {
    // Set callback to report playback events to backend
    audioPlaybackManager.setPlaybackEventCallback(async (eventType, version, taskId, details) => {
      try {
        await fetch('/api/speech/playback-event', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event_type: eventType,
            interaction_version: version,
            task_id: taskId,
            details,
          }),
        });
        fetchSpeechStatus();
      } catch {
        // ignore
      }
    });

    const unsubscribeAudio = audioPlaybackManager.subscribe((state) => {
      setSpeechStatus(state.status);
      setCurrentPlayingVersion(state.currentPlayingVersion);
      if (state.lastBlockedVersion !== null) {
        setLastBlockedAudioVersion(state.lastBlockedVersion);
        voiceInteractionManager.recordStaleBlockedAfterVoice();
      }
      if (state.interruptionLatencyMs !== null) {
        setInterruptionLatencyMs(state.interruptionLatencyMs);
      }
    });

    const unsubscribeVoice = voiceInteractionManager.subscribe((state) => {
      setVoiceState(state);
    });

    // Wire voice manager submission to conversation handler
    voiceInteractionManager.setSubmitCallback(async (text, source) => {
      await handleSendMessage(text, source);
    });

    voiceInteractionManager.setTimelineEventCallback((evt) => {
      setTimeline((prev) => [
        ...prev,
        {
          event_id: `evt-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
          event_type: evt.event_type || 'VOICE_EVENT',
          interaction_version: evt.interaction_version ?? activeVersion,
          active_version: evt.active_version ?? activeVersion,
          timestamp: new Date().toISOString(),
          message: evt.message || '',
          details: evt.details || {},
        } as TimelineEvent,
      ]);
    });

    return () => {
      unsubscribeAudio();
      unsubscribeVoice();
    };
  }, [fetchSpeechStatus, activeVersion]);

  // WebSocket Connection
  useEffect(() => {
    let reconnectTimeout: any;

    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === 'session_snapshot') {
            setActiveVersion(data.active_version);
            audioPlaybackManager.setActiveVersion(data.active_version);
            setFormState(data.form_state);
            setTasks(data.tasks || []);
            setStaleBlocksCount(data.stale_blocks_count || 0);
            if (data.timeline) setTimeline(data.timeline);
          } else if (data.event === 'stress_test_event' || data.event === 'structured_event') {
            const evt: TimelineEvent = data.payload;
            setTimeline((prev) => [...prev, evt]);
            if (data.active_version) {
              setActiveVersion(data.active_version);
              audioPlaybackManager.setActiveVersion(data.active_version);
            }
            if (data.form_state) setFormState(data.form_state);
            if (data.stale_blocks_count !== undefined) {
              setStaleBlocksCount(data.stale_blocks_count);
            }
          } else if (data.event === 'form_state_updated') {
            if (data.active_version) {
              setActiveVersion(data.active_version);
              audioPlaybackManager.setActiveVersion(data.active_version);
            }
            if (data.form_state) setFormState(data.form_state);
            if (data.message) {
              setMessages((prev) => [...prev, data.message]);
            }
          } else if (data.event === 'speech_ready') {
            // Audio payload received from backend
            const payload = data.payload;
            if (payload) {
              const audioUrl = payload.audio_url || (payload.audio_base64 ? `data:audio/wav;base64,${payload.audio_base64}` : '');
              if (audioUrl) {
                audioPlaybackManager.enqueueAudio({
                  id: payload.task_id || `audio-${Date.now()}`,
                  interaction_version: payload.interaction_version,
                  audio_url: audioUrl,
                  task_id: payload.task_id,
                  provider: payload.provider,
                });
              }
            }
            fetchSpeechStatus();
          } else if (data.event === 'speech_status_update') {
            fetchSpeechStatus();
          } else if (data.event === 'session_reset' || data.event === 'conversation_reset') {
            setActiveVersion(data.active_version);
            audioPlaybackManager.reset(data.active_version);
            voiceInteractionManager.reset(data.active_version);
            setFormState(data.form_state);
            setTasks([]);
            setTimeline([]);
            setMessages([]);
            setStaleBlocksCount(0);
            setCancelledTasksCount(0);
            setActiveTasksCount(0);
            setTestSuccess(null);
            setLastBlockedAudioVersion(null);
            fetchSpeechStatus();
          }
        } catch {
          // ignore non-json
        }
      };

      ws.onclose = () => {
        setIsWsConnected(false);
        reconnectTimeout = setTimeout(connectWebSocket, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectWebSocket();
    fetchStateSnapshot();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, [fetchStateSnapshot, fetchSpeechStatus]);

  // Send Conversation Message (supports text and voice input_source)
  const handleSendMessage = async (text: string, source: string = 'text') => {
    setIsProcessingAi(true);
    try {
      const response = await fetch('/api/conversation/input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, input_source: source }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.active_version) {
          setActiveVersion(data.active_version);
          audioPlaybackManager.setActiveVersion(data.active_version);
        }
        if (data.form_state) setFormState(data.form_state);
      }
    } catch (err) {
      console.error("Conversation input failed:", err);
    } finally {
      setIsProcessingAi(false);
      fetchStateSnapshot();
    }
  };

  // Trigger Live AI Interruption Race-Condition
  const handleTriggerInterruptionDemo = async () => {
    setIsProcessingAi(true);
    try {
      const p1 = fetch('/api/conversation/input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'Set my postal code to 600001' }),
      });

      await new Promise((r) => setTimeout(r, 40));

      const p2 = fetch('/api/conversation/input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'Actually, change postal code to 600028' }),
      });

      await Promise.all([p1, p2]);
    } catch (err) {
      console.error("Interruption demo failed:", err);
    } finally {
      setIsProcessingAi(false);
      fetchStateSnapshot();
    }
  };

  // Trigger Deterministic Voice Interruption Demo Scenario (v80 -> v81)
  const handleRunVoiceBargeInTest = async () => {
    setIsTestingVoice(true);
    try {
      const res = await fetch('/api/demo/voice-interruption-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          initial_phrase: 'My postal code is 600001',
          interrupt_phrase: 'Actually change it to 600028',
          tts_delay_seconds: 1.5,
          interrupt_delay_seconds: 0.2,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.active_version) {
          setActiveVersion(data.active_version);
          audioPlaybackManager.setActiveVersion(data.active_version);
        }
        if (data.final_form_state) {
          setFormState(data.final_form_state);
        }
        if (data.stale_audio_blocked !== undefined) {
          setStaleBlocksCount((prev) => prev + (data.stale_audio_blocked ? 1 : 0));
        }
      }
    } catch (err) {
      console.error("Voice barge-in test failed:", err);
    } finally {
      setIsTestingVoice(false);
      fetchStateSnapshot();
    }
  };

  // Reset Conversation and Form
  const handleResetConversation = async () => {
    try {
      await fetch('/api/conversation/reset', { method: 'POST' });
      audioPlaybackManager.reset(10);
      voiceInteractionManager.reset(10);
      setMessages([]);
      setTimeline([]);
      setTestSuccess(null);
      setLastBlockedAudioVersion(null);
      fetchStateSnapshot();
    } catch (err) {
      console.error("Reset failed:", err);
    }
  };

  // Play Test Response for Active Version
  const handlePlayTestResponse = async () => {
    try {
      const res = await fetch('/api/speech/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: `VoiceForm active version is v${activeVersion}. All fields are protected by version fencing.`,
          interaction_version: activeVersion,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.audio_base64) {
          audioPlaybackManager.enqueueAudio({
            id: data.task_id || `test-${Date.now()}`,
            interaction_version: data.interaction_version,
            audio_url: `data:audio/wav;base64,${data.audio_base64}`,
            task_id: data.task_id,
            provider: data.provider,
          });
        }
      }
    } catch (err) {
      console.error("Play test response failed:", err);
    }
  };

  // Stop Audio Playback Immediately
  const handleStopAudio = () => {
    audioPlaybackManager.stopCurrentAudio('User clicked Stop Audio button');
  };

  // Switch Provider
  const handleSwitchProvider = async (provider: string, delay: number = 0.0) => {
    try {
      await fetch('/api/speech/provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_name: provider, artificial_delay: delay }),
      });
      await fetchSpeechStatus();
    } catch (err) {
      console.error("Switch provider failed:", err);
    }
  };

  // Run Race Tests
  const handleRunRaceTest = async (mode: 'MODE_A' | 'MODE_B' | 'MODE_C') => {
    setIsRunning(true);
    try {
      const res = await fetch('/api/demo/audio-race-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: mode }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.active_version) {
          setActiveVersion(data.active_version);
          audioPlaybackManager.setActiveVersion(data.active_version);
        }
      }
    } catch (err) {
      console.error("Race test failed:", err);
    } finally {
      setIsRunning(false);
      fetchStateSnapshot();
    }
  };

  // Run Stress Test Trigger
  const handleRunStressTest = async () => {
    setIsRunning(true);
    setTestSuccess(null);
    setTimeline([]);

    try {
      const response = await fetch('/api/demo/stress-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          old_postal_code: oldPostalCode,
          new_postal_code: newPostalCode,
          validation_delay_seconds: validationDelay,
          interrupt_after_seconds: interruptTiming,
        }),
      });

      if (response.ok) {
        const data: StressTestResponse = await response.json();
        setActiveVersion(data.final_interaction_version);
        audioPlaybackManager.setActiveVersion(data.final_interaction_version);
        setFormState(data.final_form_state);
        setTimeline(data.event_timeline);
        setStaleBlocksCount(data.stale_results_blocked);
        setCancelledTasksCount(data.cancelled_tasks_count);
        setTestSuccess(data.test_success);
      } else {
        setTestSuccess(false);
      }
    } catch {
      setTestSuccess(false);
    } finally {
      setIsRunning(false);
      fetchStateSnapshot();
    }
  };

  // Reset Session
  const handleResetSession = async () => {
    try {
      await fetch('/api/demo/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initial_version: 10 }),
      });
      audioPlaybackManager.reset(10);
      voiceInteractionManager.reset(10);
      fetchStateSnapshot();
      setTimeline([]);
      setTestSuccess(null);
      setLastBlockedAudioVersion(null);
    } catch {
      // ignore
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900 flex flex-col font-sans">
      <Header
        activeVersion={activeVersion}
        isWsConnected={isWsConnected}
        isRunning={isRunning || isProcessingAi || isTestingVoice}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Top Metrics Summary */}
        <MetricsCards
          activeVersion={activeVersion}
          staleBlocksCount={staleBlocksCount}
          cancelledTasksCount={cancelledTasksCount}
          activeTasksCount={activeTasksCount}
          testSuccess={testSuccess}
          mode={mode}
        />

        {/* Phase 5 Voice Interaction & Barge-In Panel */}
        <VoiceInteractionPanel
          voiceState={voiceState}
          audioStatus={speechStatus}
          activeVersion={activeVersion}
          onStartListening={() => voiceInteractionManager.startVoiceInteraction()}
          onStopListening={() => voiceInteractionManager.stopListening()}
          onCancelListening={() => voiceInteractionManager.cancelInteraction()}
          onSwitchProvider={(type) => voiceInteractionManager.switchProvider(type)}
          onRunVoiceBargeInTest={handleRunVoiceBargeInTest}
          onConfigureMock={(cfg) => {
            const mock = voiceInteractionManager.getMockProvider();
            mock.configure(cfg);
          }}
          isTestingVoice={isTestingVoice}
        />

        {/* Speech Status Panel (Phase 4 Authority) */}
        <SpeechStatusPanel
          status={speechStatus}
          activeVersion={activeVersion}
          currentPlayingVersion={currentPlayingVersion}
          lastBlockedVersion={lastBlockedAudioVersion}
          interruptionLatencyMs={interruptionLatencyMs}
          providerInfo={providerInfo}
          metrics={speechMetrics}
          onPlayTestResponse={handlePlayTestResponse}
          onStopAudio={handleStopAudio}
          onSwitchProvider={handleSwitchProvider}
          onRunRaceTest={handleRunRaceTest}
          isTesting={isRunning}
        />

        {/* View Mode Switcher */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setActiveTab('conversation')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                activeTab === 'conversation'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              <span>AI Conversation &amp; Voice Pipeline</span>
            </button>

            <button
              onClick={() => setActiveTab('stresstest')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                activeTab === 'stresstest'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Deterministic Stress-Test Engine</span>
            </button>
          </div>

          <div className="text-xs text-slate-500 hidden sm:block">
            {activeTab === 'conversation'
              ? 'Real-time Gemini action interpreter with Rime TTS, speech recognition & full-duplex barge-in'
              : 'Deterministic 5s delay race condition with configurable cancellation vs. fencing'}
          </div>
        </div>

        {/* Tab 1: AI Natural Language & Voice Flow */}
        {activeTab === 'conversation' && (
          <div className="space-y-6">
            <ConversationPanel
              messages={messages}
              activeVersion={activeVersion}
              isProcessing={isProcessingAi}
              onSendMessage={handleSendMessage}
              onTriggerInterruptionDemo={handleTriggerInterruptionDemo}
              onResetConversation={handleResetConversation}
              isListening={voiceState.micStatus === 'LISTENING'}
              onToggleVoiceInput={() => {
                if (voiceState.micStatus === 'LISTENING') {
                  voiceInteractionManager.stopListening();
                } else {
                  voiceInteractionManager.startVoiceInteraction();
                }
              }}
            />

            {/* Split View: Live Form State & Live Event Timeline */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-5">
                <FormStateViewer
                  formState={formState}
                  activeVersion={activeVersion}
                />
              </div>
              <div className="lg:col-span-7">
                <EventTimeline
                  timeline={timeline}
                  activeVersion={activeVersion}
                />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Deterministic Stress-Test Engine */}
        {activeTab === 'stresstest' && (
          <div className="space-y-6">
            <StressTestControls
              mode={mode}
              setMode={setMode}
              oldPostalCode={oldPostalCode}
              setOldPostalCode={setOldPostalCode}
              newPostalCode={newPostalCode}
              setNewPostalCode={setNewPostalCode}
              validationDelay={validationDelay}
              setValidationDelay={setValidationDelay}
              interruptTiming={interruptTiming}
              setInterruptTiming={setInterruptTiming}
              isRunning={isRunning}
              onRunTest={handleRunStressTest}
              onReset={handleResetSession}
            />

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-5">
                <FormStateViewer
                  formState={formState}
                  activeVersion={activeVersion}
                />
              </div>
              <div className="lg:col-span-7">
                <EventTimeline
                  timeline={timeline}
                  activeVersion={activeVersion}
                />
              </div>
            </div>
          </div>
        )}

        {/* Task Registry Inspection Panel */}
        <TaskRegistryViewer
          tasks={tasks}
          activeVersion={activeVersion}
        />
      </main>
    </div>
  );
};

export default App;

