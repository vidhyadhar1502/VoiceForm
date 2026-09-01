import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Header } from './components/Header';
import { MetricsCards } from './components/MetricsCards';
import { StressTestControls } from './components/StressTestControls';
import { FormStateViewer } from './components/FormStateViewer';
import { EventTimeline } from './components/EventTimeline';
import { TaskRegistryViewer } from './components/TaskRegistryViewer';
import { FormState, TaskRecord, TimelineEvent, StressTestResponse } from './types';

export const App: React.FC = () => {
  // State
  const [activeVersion, setActiveVersion] = useState<number>(10);
  const [formState, setFormState] = useState<FormState>({
    fields: {},
    last_updated_version: 10,
  });
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [staleBlocksCount, setStaleBlocksCount] = useState<number>(0);
  const [cancelledTasksCount, setCancelledTasksCount] = useState<number>(0);
  const [activeTasksCount, setActiveTasksCount] = useState<number>(0);
  const [isWsConnected, setIsWsConnected] = useState<boolean>(false);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [testSuccess, setTestSuccess] = useState<boolean | null>(null);

  // Controls configuration
  const [mode, setMode] = useState<'uncancellable' | 'cancellable'>('uncancellable');
  const [oldPostalCode, setOldPostalCode] = useState<string>('600001');
  const [newPostalCode, setNewPostalCode] = useState<string>('600028');
  const [validationDelay, setValidationDelay] = useState<number>(3.0);
  const [interruptTiming, setInterruptTiming] = useState<number>(1.0);

  const wsRef = useRef<WebSocket | null>(null);

  // Poll state as fallback or initial sync
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
          } else if (data.event === 'stress_test_event') {
            const evt: TimelineEvent = data.payload;
            setTimeline((prev) => [...prev, evt]);
            if (data.active_version) setActiveVersion(data.active_version);
            if (data.form_state) setFormState(data.form_state);
            if (data.stale_blocks_count !== undefined) {
              setStaleBlocksCount(data.stale_blocks_count);
            }
          } else if (data.event === 'session_reset') {
            setActiveVersion(data.active_version);
            setFormState(data.form_state);
            setTasks([]);
            setTimeline([]);
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
        isRunning={isRunning}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Metrics Grid */}
        <MetricsCards
          activeVersion={activeVersion}
          staleBlocksCount={staleBlocksCount}
          cancelledTasksCount={cancelledTasksCount}
          activeTasksCount={activeTasksCount}
          testSuccess={testSuccess}
          mode={mode}
        />

        {/* Experiment Controls */}
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

        {/* Main Split View: Left Form State, Right Event Timeline */}
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
