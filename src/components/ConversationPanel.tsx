import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, MessageSquare, Zap, RotateCcw, AlertTriangle, CheckCircle2, CornerDownRight } from 'lucide-react';
import { ConversationMessage } from '../types';

interface ConversationPanelProps {
  messages: ConversationMessage[];
  activeVersion: number;
  isProcessing: boolean;
  onSendMessage: (text: string) => Promise<void>;
  onTriggerInterruptionDemo: () => Promise<void>;
  onResetConversation: () => Promise<void>;
}

const SAMPLE_PROMPTS = [
  "My name is Vidhyadhar S.",
  "I work as a Software Developer",
  "My phone number is 9876543210",
  "Set my postal code to 600001",
  "Actually change postal code to 600028",
  "Skip the street address for now",
  "What information have I provided so far?"
];

export const ConversationPanel: React.FC<ConversationPanelProps> = ({
  messages,
  activeVersion,
  isProcessing,
  onSendMessage,
  onTriggerInterruptionDemo,
  onResetConversation
}) => {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isProcessing) return;
    const text = inputText;
    setInputText('');
    await onSendMessage(text);
  };

  const handleChipClick = async (prompt: string) => {
    if (isProcessing) return;
    setInputText('');
    await onSendMessage(prompt);
  };

  return (
    <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden flex flex-col h-[520px]">
      {/* Panel Header */}
      <div className="bg-slate-900 text-white px-5 py-3.5 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-indigo-300">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2">
              Gemini AI Conversation Orchestrator
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-900/60 border border-indigo-500/40 text-indigo-300 font-mono">
                Active v{activeVersion}
              </span>
            </h2>
            <p className="text-xs text-slate-400">Natural language form control fenced by interaction versions</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onTriggerInterruptionDemo}
            disabled={isProcessing}
            title="Fire 2 rapid contradictory prompts to observe AI version fencing"
            className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 hover:bg-amber-500/30 text-xs font-medium transition-colors disabled:opacity-50 cursor-pointer"
          >
            <Zap className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Simulate AI Interruption</span>
          </button>

          <button
            onClick={onResetConversation}
            title="Reset conversation and state"
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/50">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
            <div className="w-12 h-12 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-400 mb-3">
              <MessageSquare className="w-6 h-6" />
            </div>
            <p className="text-sm font-medium text-slate-600">VoiceForm AI Ready</p>
            <p className="text-xs text-slate-500 max-w-sm mt-1">
              Speak or type natural language instructions. Every action is interpreted by Gemini, validated against form schemas, and strictly version-fenced.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-1.5 max-w-md">
              {SAMPLE_PROMPTS.slice(0, 4).map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => handleChipClick(p)}
                  className="text-xs px-2.5 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition-colors shadow-2xs"
                >
                  "{p}"
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === 'user';
            const isStale = msg.interaction_version < activeVersion;

            return (
              <div
                key={msg.id}
                className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm shadow-2xs ${
                    isUser
                      ? 'bg-indigo-600 text-white rounded-br-xs'
                      : 'bg-white text-slate-800 border border-slate-200/80 rounded-bl-xs'
                  }`}
                >
                  {/* Top Metadata Badge */}
                  <div className="flex items-center justify-between gap-3 mb-1 text-[11px] opacity-85">
                    <span className="font-semibold uppercase tracking-wider">
                      {isUser ? 'User' : 'Gemini AI Assistant'}
                    </span>
                    <span
                      className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${
                        isUser
                          ? 'bg-indigo-700/60 text-indigo-100'
                          : isStale
                          ? 'bg-amber-100 text-amber-800 border border-amber-300'
                          : 'bg-slate-100 text-slate-600 border border-slate-200'
                      }`}
                    >
                      v{msg.interaction_version}
                    </span>
                  </div>

                  {/* Message Body */}
                  <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>

                  {/* Structured Action details for Assistant */}
                  {!isUser && msg.structured_action && (
                    <div className="mt-2 pt-2 border-t border-slate-100 text-xs flex flex-wrap items-center gap-1.5">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-800 font-mono text-[11px]">
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                        {msg.structured_action.action}
                        {msg.structured_action.target_field && `: ${msg.structured_action.target_field}`}
                      </span>

                      {msg.structured_action.value && (
                        <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-mono text-[11px]">
                          val="{msg.structured_action.value}"
                        </span>
                      )}

                      {isStale && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 border border-amber-300 text-amber-800 text-[10px]">
                          <AlertTriangle className="w-3 h-3 text-amber-600" />
                          Superseded by v{activeVersion}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
        {isProcessing && (
          <div className="flex items-center space-x-2 text-slate-500 text-xs p-2">
            <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
            <span>Interpreting intent & validating version fence...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Chips Bar */}
      <div className="px-4 py-2 bg-slate-50 border-t border-slate-200/80 flex items-center space-x-1.5 overflow-x-auto no-scrollbar">
        <span className="text-[11px] font-medium text-slate-500 whitespace-nowrap flex items-center gap-1">
          <CornerDownRight className="w-3 h-3" /> Quick:
        </span>
        {SAMPLE_PROMPTS.map((p, idx) => (
          <button
            key={idx}
            onClick={() => handleChipClick(p)}
            disabled={isProcessing}
            className="text-[11px] px-2.5 py-0.5 rounded-full bg-white border border-slate-200 text-slate-600 hover:text-indigo-600 hover:border-indigo-300 hover:bg-indigo-50/50 transition-colors whitespace-nowrap cursor-pointer disabled:opacity-50"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input Box */}
      <form onSubmit={handleSubmit} className="p-3 bg-white border-t border-slate-200 flex items-center space-x-2">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Speak or type a command (e.g. 'My name is...', 'Skip city', 'Summary')..."
          disabled={isProcessing}
          className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white text-slate-800 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!inputText.trim() || isProcessing}
          className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors flex items-center space-x-1.5 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-xs"
        >
          <span>Send</span>
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
};
