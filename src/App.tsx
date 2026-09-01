import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Header } from './components/Header';
import { MetricsCards } from './components/MetricsCards';
import { StressTestControls } from './components/StressTestControls';
import { FormStateViewer } from './components/FormStateViewer';
import { EventTimeline } from './components/EventTimeline';
import { TaskRegistryViewer } from './components/TaskRegistryViewer';
import { ConversationPanel } from './components/ConversationPanel';
import { FormState, TaskRecord, TimelineEvent, StressTestResponse, ConversationMessage } from './types';
import { Sparkles, Activity } from 'lucide-react';

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
  const [testSuccess, setTestSuccess] = useState<boolean | null>(null);

  // Active View Mode
  const [activeTab, setActiveTab] = useState<'conversation' | 'stresstest'>('conversation');

  // Controls configuration
  const [mode, setMode] = useState<'uncancellable' | 'cancellable'>('uncancellable');
  const [oldPostalCode, setOldPostalCode] = useState<string>('600001');
  const [newPostalCode, setNewPostalCode] = useState<string>('600028');
  const [validationDelay, setValidationDelay] = useState<number>(3.0);
  const [interruptTiming, setInterruptTiming] = useState<number>(1.0);

  const wsRef = useRef<WebSocket | null>(null);

  // Poll state snapshot
  const fetchStateSnapshot = useCallback(async () => {
    try {
      const res = await fetch('/api/demo/state');
      if (res.ok) {
        const data = await res.json();
        setActiveVersion(data.active_version);
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
    } catch {
      // Backend may be booting up
    }
  }, []);

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
            setFormState(data.form_state);
            setTasks(data.tasks || []);
            setStaleBlocksCount(data.stale_blocks_count || 0);
            if (data.timeline) setTimeline(data.timeline);
          } else if (data.event === 'stress_test_event' || data.event === 'structured_event') {
            const evt: TimelineEvent = data.payload;
            setTimeline((prev) => [...prev, evt]);
            if (data.active_version) setActiveVersion(data.active_version);
            if (data.form_state) setFormState(data.form_state);
            if (data.stale_blocks_count !== undefined) {
              setStaleBlocksCount(data.stale_blocks_count);
            }
          } else if (data.event === 'form_state_updated') {
            if (data.active_version) setActiveVersion(data.active_version);
            if (data.form_state) setFormState(data.form_state);
            if (data.message) {
              setMessages((prev) => [...prev, data.message]);
            }
          } else if (data.event === 'session_reset' || data.event === 'conversation_reset') {
            setActiveVersion(data.active_version);
            setFormState(data.form_state);
            setTasks([]);
            setTimeline([]);
            setMessages([]);
            setStaleBlocksCount(0);
            setCancelledTasksCount(0);
            setActiveTasksCount(0);
            setTestSuccess(null);
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
  }, [fetchStateSnapshot]);

  // Send Conversation Message
  const handleSendMessage = async (text: string) => {
    setIsProcessingAi(true);
    try {
      const response = await fetch('/api/conversation/input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.active_version) setActiveVersion(data.active_version);
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
      // Fire first slow input
      const p1 = fetch('/api/conversation/input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'Set my postal code to 600001' }),
      });

      // Rapidly fire contradictory second input 40ms later
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

  // Reset Conversation and Form
  const handleResetConversation = async () => {
    try {
      await fetch('/api/conversation/reset', { method: 'POST' });
      setMessages([]);
      setTimeline([]);
      setTestSuccess(null);
      fetchStateSnapshot();
    } catch (err) {
      console.error("Reset failed:", err);
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
      fetchStateSnapshot();
      setTimeline([]);
      setTestSuccess(null);
    } catch {
      // ignore
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900 flex flex-col font-sans">
      <Header
        activeVersion={activeVersion}
        isWsConnected={isWsConnected}
        isRunning={isRunning || isProcessingAi}
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
              <span>AI Conversation & Natural Language</span>
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
              ? 'Real-time Gemini action interpreter with interaction-version safety fencing'
              : 'Deterministic 5s delay race condition with configurable cancellation vs. fencing'}
          </div>
        </div>

        {/* Tab 1: AI Natural Language Flow */}
        {activeTab === 'conversation' && (
          <div className="space-y-6">
            <ConversationPanel
              messages={messages}
              activeVersion={activeVersion}
              isProcessing={isProcessingAi}
              onSendMessage={handleSendMessage}
              onTriggerInterruptionDemo={handleTriggerInterruptionDemo}
              onResetConversation={handleResetConversation}
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
