"use client";

import React, { useEffect, useState } from "react";

interface MessageItem {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_role: string;
  text: string;
  timestamp?: string;
}

interface SuggestedSlot {
  slot_id: string;
  start_time: string;
  end_time: string;
  duration_min: number;
  formatted: string;
}

interface SuggestionResponse {
  conversation_id: string;
  thread_id: string;
  status: string;
  intent: "question" | "negotiation" | "interview_request" | "scam_signal" | string;
  suggested_reply: string | null;
  proposed_slots: SuggestedSlot[];
  is_awaiting_approval: boolean;
  compliance_passed: boolean;
  risk_flags: string[];
  detail: string;
}

export default function MessagesPage() {
  const [conversations] = useState<string[]>([
    "conv_interview_101",
    "conv_negotiation_202",
    "conv_question_303",
    "conv_scam_404",
  ]);
  const [selectedConv, setSelectedConv] = useState<string>("conv_interview_101");
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [suggestion, setSuggestion] = useState<SuggestionResponse | null>(null);
  const [editedText, setEditedText] = useState<string>("");
  const [loadingSuggestion, setLoadingSuggestion] = useState<boolean>(false);
  const [actionStatus, setActionStatus] = useState<string | null>(null);

  useEffect(() => {
    fetchMessages(selectedConv);
    fetchSuggestion(selectedConv);
  }, [selectedConv]);

  async function fetchMessages(convId: string) {
    try {
      const res = await fetch(`/api/messages?conversation_id=${convId}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      } else {
        // Fallback demo mock messages if empty
        setMessages([
          {
            id: "msg_1",
            conversation_id: convId,
            sender_id: "client_acme",
            sender_role: "client",
            text: convId.includes("interview")
              ? "Hi! We reviewed your proposal and would love to hop on a quick call this week. What days are you free?"
              : convId.includes("negotiation")
              ? "Can you do $50/hr for this milestone instead of $85?"
              : convId.includes("scam")
              ? "Contact my manager on Telegram @cryptoboss123 for payment before we start."
              : "What is your experience deploying vector databases with pgvector?",
            timestamp: new Date().toISOString(),
          },
        ]);
      }
    } catch {
      setMessages([]);
    }
  }

  async function fetchSuggestion(convId: string) {
    setLoadingSuggestion(true);
    setActionStatus(null);
    try {
      const res = await fetch(`/api/messages/${convId}/suggestion`);
      if (res.ok) {
        const data: SuggestionResponse = await res.json();
        setSuggestion(data);
        setEditedText(data.suggested_reply || "");
      } else {
        setSuggestion(null);
      }
    } catch {
      setSuggestion(null);
    } finally {
      setLoadingSuggestion(false);
    }
  }

  async function handleDecision(action: "approve" | "reject") {
    if (!suggestion) return;
    setActionStatus("Submitting decision...");
    try {
      const res = await fetch(`/api/messages/${selectedConv}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          edited_text: action === "approve" ? editedText : null,
        }),
      });
      if (res.ok) {
        setActionStatus(action === "approve" ? "✓ Message sent & calendar hold placed!" : "✓ Suggested reply rejected.");
        // Append sent message to conversation thread
        if (action === "approve" && editedText) {
          setMessages((prev) => [
            ...prev,
            {
              id: `msg_${Date.now()}`,
              conversation_id: selectedConv,
              sender_id: "freelancer_me",
              sender_role: "freelancer",
              text: editedText,
              timestamp: new Date().toISOString(),
            },
          ]);
        }
        fetchSuggestion(selectedConv);
      } else {
        setActionStatus("Failed submitting approval.");
      }
    } catch {
      setActionStatus("Network error submitting approval.");
    }
  }

  const intentColorMap: Record<string, { bg: string; text: string; label: string }> = {
    interview_request: { bg: "bg-purple-100", text: "text-purple-800", label: "Interview Request" },
    negotiation: { bg: "bg-emerald-100", text: "text-emerald-800", label: "Commercial Negotiation" },
    question: { bg: "bg-blue-100", text: "text-blue-800", label: "Technical Question" },
    scam_signal: { bg: "bg-rose-100", text: "text-rose-800", label: "Safety Threat / Scam Signal" },
  };

  const intentMeta = suggestion?.intent ? intentColorMap[suggestion.intent] || { bg: "bg-slate-100", text: "text-slate-800", label: suggestion.intent } : null;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Client Liaison & Negotiations</h1>
          <p className="text-sm text-slate-500">Autonomous intent classification, Workspace calendar holds, and human-in-the-loop review.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Thread:</span>
          <select
            value={selectedConv}
            onChange={(e) => setSelectedConv(e.target.value)}
            className="text-xs font-medium border border-slate-300 rounded-lg px-3 py-1.5 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {conversations.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Messages Transcript */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Conversation History</h2>
            <span className="text-xs text-slate-400">{messages.length} messages</span>
          </div>

          <div className="space-y-3 min-h-[360px] max-h-[500px] overflow-y-auto pr-1">
            {messages.map((m) => {
              const isClient = m.sender_role === "client";
              return (
                <div key={m.id} className={`flex flex-col ${isClient ? "items-start" : "items-end"}`}>
                  <span className="text-[10px] text-slate-400 font-medium mb-1 px-1">
                    {isClient ? "Client" : "You (Freelancer)"}
                  </span>
                  <div
                    className={`max-w-[88%] rounded-2xl px-4 py-2.5 text-xs leading-relaxed ${
                      isClient
                        ? "bg-slate-100 text-slate-800 rounded-tl-sm"
                        : "bg-indigo-600 text-white rounded-tr-sm shadow-sm"
                    }`}
                  >
                    {m.text}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Autonomous Suggestion & Approval Panel */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Copilot Suggestion</h2>
              {intentMeta && (
                <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${intentMeta.bg} ${intentMeta.text}`}>
                  {intentMeta.label}
                </span>
              )}
            </div>
            {suggestion && (
              <span className="text-xs font-mono text-slate-400">
                Status: {suggestion.status}
              </span>
            )}
          </div>

          {loadingSuggestion ? (
            <div className="py-16 text-center text-slate-400 text-xs animate-pulse">
              Running conversation graph: classifying intent & consulting Workspace MCP...
            </div>
          ) : suggestion?.intent === "scam_signal" ? (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-5 space-y-3">
              <div className="flex items-center gap-2 text-rose-800 font-bold text-sm">
                <span>⛔</span>
                <span>Outbound Reply Blocked by Security Policy</span>
              </div>
              <p className="text-xs text-rose-700 leading-relaxed">
                This client message triggered strict safety flags (off-platform contact or suspicious payment terms).
                The conversation graph has flagged this thread and automatically suppressed reply drafting.
              </p>
              {suggestion.risk_flags.length > 0 && (
                <div className="bg-white/80 rounded-lg p-2.5 text-[11px] font-mono text-rose-900 border border-rose-200">
                  {suggestion.risk_flags.join(", ")}
                </div>
              )}
            </div>
          ) : suggestion ? (
            <div className="space-y-4">
              {/* Proposed Workspace Slots */}
              {suggestion.proposed_slots && suggestion.proposed_slots.length > 0 && (
                <div className="bg-indigo-50/70 border border-indigo-100 rounded-xl p-4 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-900">
                    <span>📅</span>
                    <span>Workspace MCP: Tentative Calendar Slots (Held Upon Approval)</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                    {suggestion.proposed_slots.map((slot) => (
                      <div
                        key={slot.slot_id}
                        className="bg-white border border-indigo-200 rounded-lg p-2.5 text-xs text-indigo-950 shadow-2xs"
                      >
                        <div className="font-semibold">{slot.formatted}</div>
                        <div className="text-[10px] text-slate-400 font-mono mt-0.5">{slot.slot_id}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Draft Reply Area */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Suggested Response (Editable Before Approval)
                </label>
                <textarea
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  rows={6}
                  className="w-full text-xs font-sans border border-slate-300 rounded-xl p-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 leading-relaxed"
                />
              </div>

              {/* Approval Buttons */}
              <div className="flex items-center justify-between pt-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleDecision("approve")}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 py-2 rounded-xl transition-colors shadow-sm"
                  >
                    Approve & Send
                  </button>
                  <button
                    onClick={() => handleDecision("reject")}
                    className="bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs px-3 py-2 rounded-xl transition-colors"
                  >
                    Reject
                  </button>
                </div>

                {actionStatus && (
                  <span className="text-xs font-medium text-emerald-700 animate-fade-in">
                    {actionStatus}
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="py-12 text-center text-slate-400 text-xs">
              No suggestion active for this conversation.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
