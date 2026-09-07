import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  MessageSquare, 
  Trash2, 
  Loader2, 
  Code, 
  Copy, 
  Check, 
  ShieldCheck, 
  X 
} from 'lucide-react';
import MarkdownMessage from './MarkdownMessage.jsx';
import ClaudeLoadingIndicator from './ClaudeLoadingIndicator.jsx';

const SUGGESTIONS = [
  "Is it safe to fish near Chennai right now?",
  "What are wave conditions and ocean swell in Kochi?",
  "Are there any active alerts or hazards in Mumbai?",
  "How is the weather and sea state near Visakhapatnam?",
  "What are conditions in the Sundarbans / Kolkata delta?",
  "What is the weather in Delhi right now?"
];

export function ChatbotSection({ initialQuery = "" }) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: "👋 Welcome to Confluence Coastal Assistant. I perform live deterministic tool-calling against real-time physical sensor data across our 10 upstream scientific providers. Ask me about coastal departure safety, wave swell, sea states, or marine hazards.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
  ]);
  const [inputQuery, setInputQuery] = useState(initialQuery || '');
  const [isLoading, setIsLoading] = useState(false);
  const [contextData, setContextData] = useState(null);
  const [showInspector, setShowInspector] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (initialQuery) {
      setInputQuery(initialQuery);
    }
  }, [initialQuery]);

  const handleSend = async (queryText) => {
    const textToSend = queryText || inputQuery;
    if (!textToSend.trim() || isLoading) return;

    const userMsg = {
      id: String(Date.now()),
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInputQuery('');
    setIsLoading(true);

    try {
      const response = await fetch('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: textToSend,
          bypass_cache: false,
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();

      const aiMsg = {
        id: String(Date.now() + 1),
        sender: 'assistant',
        text: data.answer || "No response text received from analysis engine.",
        locationMatched: data.location_matched || null,
        groundingData: data.grounding_data || null,
        activeAlerts: data.active_alerts || [],
        llmModel: data.llm_model,
        cacheHit: data.cache_hit,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      if (data.grounding_data) {
        setContextData(data.grounding_data);
      }

      setMessages(prev => [...prev, aiMsg]);
    } catch (err) {
      const errorMsg = {
        id: String(Date.now() + 1),
        sender: 'assistant',
        isError: true,
        text: `⚠️ Grounded Analysis Notice: Unable to query live endpoint (${err.message}). Grounding safety policy: unverified claims are blocked when live sensors are unreachable.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: 'welcome-reset',
        sender: 'assistant',
        text: "Conversation cleared. Ready for new coastal telemetry queries.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
    ]);
  };

  const copyJsonToClipboard = () => {
    if (contextData) {
      navigator.clipboard.writeText(JSON.stringify(contextData, null, 2));
      setCopiedJson(true);
      setTimeout(() => setCopiedJson(false), 2000);
    }
  };

  return (
    <section 
      id="chatbot" 
      aria-label="Coastal Assistant Chatbot"
      style={{
        background: '#FFFFFF',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-xl)',
        padding: '32px',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
      }}
    >
      {/* Section Header */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        borderBottom: '1px solid var(--border-color)',
        paddingBottom: '20px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #0891B2 0%, #0E7490 100%)',
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 10px rgba(8, 145, 178, 0.22)',
          }} aria-hidden="true">
            <MessageSquare size={22} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                Confluence Coastal AI Assistant
              </h2>
              <span className="badge badge-success">
                Live Grounded
              </span>
            </div>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Grounded Marine Decision Support • Deterministic Physics • Live 10-Source Tool-Calling
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {contextData && (
            <button
              type="button"
              onClick={() => setShowInspector(true)}
              className="btn-secondary"
              style={{ fontSize: '0.82rem', padding: '6px 12px' }}
              title="Inspect Raw Grounding Telemetry Context"
              aria-label="Inspect raw grounding telemetry JSON context"
            >
              <Code size={14} aria-hidden="true" />
              <span>Inspect Grounding JSON</span>
            </button>
          )}

          <button
            type="button"
            onClick={clearChat}
            className="btn-secondary"
            style={{ fontSize: '0.82rem', padding: '6px 12px' }}
            title="Clear Chat History"
            aria-label="Clear chat conversation history"
          >
            <Trash2 size={14} aria-hidden="true" />
            <span>Clear</span>
          </button>
        </div>
      </div>

      {/* Preset Question Chips */}
      <div>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
          Suggested Inquiries
        </div>
        <div 
          role="group" 
          aria-label="Suggested questions"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          {SUGGESTIONS.map((s, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSend(s)}
              style={{
                fontSize: '0.82rem',
                padding: '6px 12px',
                borderRadius: 'var(--radius-full)',
                background: 'var(--bg-card-subtle)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'border-color 0.15s ease, color 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent-primary)';
                e.currentTarget.style.color = 'var(--accent-primary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-color)';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Messages Stream Box with aria-live="polite" */}
      <div 
        aria-live="polite"
        aria-label="Chat conversation stream"
        style={{
          background: 'var(--bg-card-subtle)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
          minHeight: '340px',
          maxHeight: '520px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        {messages.map((m) => (
          <div 
            key={m.id}
            style={{
              alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
            }}
          >
            <div style={{
              background: m.sender === 'user' ? 'var(--accent-primary)' : '#FFFFFF',
              color: m.sender === 'user' ? '#FFFFFF' : 'var(--text-primary)',
              padding: '14px 18px',
              borderRadius: m.sender === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
              border: m.sender === 'user' ? 'none' : '1px solid var(--border-color)',
              boxShadow: 'var(--shadow-sm)',
              fontSize: '0.92rem',
              lineHeight: '1.6',
            }}>
              <MarkdownMessage content={m.text} isUser={m.sender === 'user'} />

              {m.locationMatched && (
                <div style={{
                  marginTop: '10px',
                  paddingTop: '10px',
                  borderTop: '1px solid rgba(0, 0, 0, 0.08)',
                  fontSize: '0.78rem',
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '8px',
                }}>
                  <span style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>
                    📍 Station Grounding: {m.locationMatched}
                  </span>
                  {m.llmModel && (
                    <span style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      color: '#0369A1',
                      background: '#F0F9FF',
                      padding: '2px 7px',
                      borderRadius: '4px',
                      border: '1px solid #BAE6FD',
                    }}>
                      ✦ {m.llmModel}
                    </span>
                  )}
                  {m.cacheHit && (
                    <span style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      color: '#047857',
                      background: '#ECFDF5',
                      padding: '2px 7px',
                      borderRadius: '4px',
                      border: '1px solid #A7F3D0',
                    }}>
                      ⚡ Cached
                    </span>
                  )}
                  {m.activeAlerts && m.activeAlerts.length > 0 && (
                    <span className="badge badge-warning" style={{ fontSize: '0.72rem' }}>
                      ⚠️ {m.activeAlerts.length} Active Alert(s)
                    </span>
                  )}
                  {m.groundingData && (
                    <button
                      type="button"
                      onClick={() => {
                        setContextData(m.groundingData);
                        setShowInspector(true);
                      }}
                      style={{
                        marginLeft: 'auto',
                        fontSize: '0.74rem',
                        color: 'var(--accent-primary)',
                        textDecoration: 'underline',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                      }}
                      aria-label={`Inspect raw grounding JSON for ${m.locationMatched}`}
                    >
                      Inspect Context JSON
                    </button>
                  )}
                </div>
              )}
            </div>
            <div style={{
              fontSize: '0.72rem',
              color: 'var(--text-muted)',
              marginTop: '4px',
              textAlign: m.sender === 'user' ? 'right' : 'left',
              padding: '0 4px',
            }}>
              {m.timestamp}
            </div>
          </div>
        ))}

        {isLoading && (
          <div style={{ alignSelf: 'flex-start', margin: '6px 0' }}>
            <ClaudeLoadingIndicator />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Query Input Box */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <form 
          onSubmit={(e) => { e.preventDefault(); handleSend(); }}
          style={{
            display: 'flex',
            gap: '10px',
            alignItems: 'center',
          }}
        >
          <label htmlFor="coastal-chat-input" className="skip-link">
            Ask a coastal question
          </label>
          <input 
            id="coastal-chat-input"
            name="query"
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder="Ask a coastal question (e.g. “Can small boats go out in Kochi right now?”)…"
            disabled={isLoading}
            spellCheck={false}
            autoComplete="off"
            style={{
              flex: 1,
              padding: '12px 16px',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.92rem',
              background: '#FFFFFF',
            }}
          />
          <button 
            type="submit"
            disabled={isLoading || !inputQuery.trim()}
            className="btn-primary"
            style={{
              padding: '12px 20px',
              opacity: inputQuery.trim() ? 1 : 0.6,
            }}
            aria-label="Submit coastal question"
          >
            {isLoading ? <Loader2 size={18} className="animate-spin" aria-hidden="true" /> : <Send size={18} aria-hidden="true" />}
            <span>Ask AI</span>
          </button>
        </form>

        {/* Quick Station Badges */}
        <div 
          role="group" 
          aria-label="Active Coastal Stations"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.78rem',
            color: 'var(--text-muted)',
          }}
        >
          <span style={{ fontWeight: 600, textTransform: 'uppercase' }}>Stations:</span>
          <button 
            type="button" 
            onClick={() => handleSend("What are current coastal conditions near Chennai Coast?")}
            style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 500 }}
          >
            Chennai
          </button>
          <span>•</span>
          <button 
            type="button" 
            onClick={() => handleSend("What are current coastal conditions near Visakhapatnam Coast?")}
            style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 500 }}
          >
            Visakhapatnam
          </button>
          <span>•</span>
          <button 
            type="button" 
            onClick={() => handleSend("What are current coastal conditions near Kochi Coast?")}
            style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 500 }}
          >
            Kochi
          </button>
          <span>•</span>
          <button 
            type="button" 
            onClick={() => handleSend("What are current coastal conditions near Mumbai Coast?")}
            style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 500 }}
          >
            Mumbai
          </button>
          <span>•</span>
          <button 
            type="button" 
            onClick={() => handleSend("What are current coastal conditions near Kolkata / Sundarbans?")}
            style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 500 }}
          >
            Sundarbans
          </button>
        </div>
      </div>

      {/* Grounding Context Inspector Modal */}
      {showInspector && contextData && (
        <div 
          className="modal-backdrop" 
          onClick={() => setShowInspector(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="inspector-modal-title"
        >
          <div 
            className="modal-card" 
            style={{ maxWidth: '720px', width: '100%', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }} 
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-primary)' }}>
                <ShieldCheck size={20} aria-hidden="true" />
                <h3 id="inspector-modal-title" style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Grounded Telemetry Snapshot (Verified Sensor Context)
                </h3>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  type="button"
                  onClick={copyJsonToClipboard}
                  className="btn-secondary"
                  style={{ padding: '4px 10px', fontSize: '0.78rem' }}
                  aria-label={copiedJson ? "Context JSON copied" : "Copy context JSON to clipboard"}
                >
                  {copiedJson ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
                  <span>{copiedJson ? 'Copied' : 'Copy JSON'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowInspector(false)}
                  className="btn-secondary"
                  style={{ padding: '4px 8px', fontSize: '0.78rem' }}
                  aria-label="Close Inspector Modal"
                >
                  <X size={16} aria-hidden="true" />
                </button>
              </div>
            </div>

            <pre style={{
              flex: 1,
              overflowY: 'auto',
              background: 'var(--code-bg)',
              color: 'var(--code-text)',
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.82rem',
              fontFamily: 'var(--font-mono)',
              lineHeight: 1.5,
            }}>
              <code>{JSON.stringify(contextData, null, 2)}</code>
            </pre>

            <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
              <button 
                type="button"
                className="btn-primary"
                onClick={() => setShowInspector(false)}
                style={{ padding: '8px 16px', fontSize: '0.85rem' }}
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
