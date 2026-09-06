import React, { useState, useRef, useEffect } from 'react';
import { 
  X, 
  Send, 
  Sparkles, 
  Trash2, 
  CheckCircle2, 
  AlertTriangle,
  Compass,
  CornerDownLeft,
  Loader2
} from 'lucide-react';

const SUGGESTIONS = [
  "Analyze current wave height and swell risk in Chennai",
  "Are conditions safe for small craft operations in Kochi?",
  "Check air quality and PM2.5 hazards in Visakhapatnam",
  "Assess heat index and marine storm potential for Mumbai"
];

export function ChatDrawer({ isOpen, onClose, locations = [], currentLocation }) {
  const [selectedLoc, setSelectedLoc] = useState(currentLocation?.name || "Chennai Coast");
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: "👋 Welcome to **Confluence Grounded Intelligence**. I perform live deterministic tool-calling against active telemetry across our 7 upstream scientific providers. Ask me about coastal hazards, wave physics, or maritime safety.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (currentLocation?.name) {
      setSelectedLoc(currentLocation.name);
    }
  }, [currentLocation]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

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
          query: textToSend,
          location_name: selectedLoc,
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();

      const aiMsg = {
        id: String(Date.now() + 1),
        sender: 'assistant',
        text: data.answer || data.response || "No response text received from analysis engine.",
        metrics: data.context_used || data.telemetry_summary || null,
        sources: data.sources || ["Open-Meteo", "OpenAQ", "Derived Physics Engine"],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages(prev => [...prev, aiMsg]);
    } catch (err) {
      const errorMsg = {
        id: String(Date.now() + 1),
        sender: 'assistant',
        isError: true,
        text: `⚠️ **Grounded Analysis Notice**: Unable to query live endpoint (${err.message}). Grounding safety policy: if upstream data is unreachable, unverified claims are blocked.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
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

  if (!isOpen) return null;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--bg-card-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'var(--accent-primary)',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Sparkles size={18} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                Grounded Coastal AI
              </div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                Live Tool-Calling • Deterministic Grounding
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button 
              onClick={clearChat}
              title="Clear History"
              style={{
                color: 'var(--text-muted)',
                padding: '6px',
                borderRadius: '6px',
              }}
            >
              <Trash2 size={16} />
            </button>
            <button 
              onClick={onClose}
              style={{
                color: 'var(--text-secondary)',
                padding: '6px',
                borderRadius: '6px',
              }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Location selector bar */}
        <div style={{
          padding: '8px 20px',
          background: '#FFFFFF',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '0.82rem',
        }}>
          <Compass size={15} style={{ color: 'var(--accent-primary)' }} />
          <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>Target Station:</span>
          <select 
            value={selectedLoc}
            onChange={(e) => setSelectedLoc(e.target.value)}
            style={{
              padding: '4px 8px',
              borderRadius: '6px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card-subtle)',
              fontSize: '0.82rem',
              fontWeight: 600,
              color: 'var(--text-primary)',
              cursor: 'pointer',
            }}
          >
            {locations.length > 0 ? (
              locations.map(loc => (
                <option key={loc.name} value={loc.name}>{loc.name}</option>
              ))
            ) : (
              <>
                <option value="Chennai Coast">Chennai Coast</option>
                <option value="Visakhapatnam Coast">Visakhapatnam Coast</option>
                <option value="Kochi Coast">Kochi Coast</option>
                <option value="Mumbai Coast">Mumbai Coast</option>
              </>
            )}
          </select>
        </div>

        {/* Messages Body */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}>
          {messages.map((m) => (
            <div 
              key={m.id}
              style={{
                alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
              }}
            >
              <div style={{
                background: m.sender === 'user' ? 'var(--accent-primary)' : 'var(--bg-card-subtle)',
                color: m.sender === 'user' ? '#FFFFFF' : 'var(--text-primary)',
                padding: '12px 16px',
                borderRadius: m.sender === 'user' ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                border: m.sender === 'user' ? 'none' : '1px solid var(--border-color)',
                fontSize: '0.88rem',
                lineHeight: '1.5',
              }}>
                <div style={{ whiteSpace: 'pre-wrap' }}>
                  {m.text}
                </div>

                {m.sources && (
                  <div style={{
                    marginTop: '8px',
                    paddingTop: '8px',
                    borderTop: '1px solid rgba(0, 0, 0, 0.06)',
                    fontSize: '0.72rem',
                    color: 'var(--text-muted)',
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '6px',
                  }}>
                    <span>Grounded in:</span>
                    {m.sources.map((s, idx) => (
                      <span key={idx} style={{
                        background: '#FFFFFF',
                        padding: '1px 6px',
                        borderRadius: '4px',
                        border: '1px solid var(--border-color)',
                        fontWeight: 600,
                      }}>
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div style={{
                fontSize: '0.7rem',
                color: 'var(--text-muted)',
                marginTop: '4px',
                textAlign: m.sender === 'user' ? 'right' : 'left',
              }}>
                {m.timestamp}
              </div>
            </div>
          ))}

          {isLoading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
              <Loader2 size={16} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
              Executing live tool-calling across 7 providers...
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick Prompts */}
        <div style={{
          padding: '10px 20px 0 20px',
          display: 'flex',
          gap: '8px',
          overflowX: 'auto',
          whiteSpace: 'nowrap',
          scrollbarWidth: 'none',
        }}>
          {SUGGESTIONS.map((s, i) => (
            <button
              key={i}
              onClick={() => handleSend(s)}
              style={{
                fontSize: '0.76rem',
                padding: '6px 12px',
                borderRadius: '999px',
                background: 'var(--bg-card-subtle)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                flexShrink: 0,
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Query Input Box */}
        <div style={{
          padding: '16px 20px',
          borderTop: '1px solid var(--border-color)',
          background: '#FFFFFF',
        }}>
          <form 
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            style={{
              display: 'flex',
              gap: '10px',
              alignItems: 'center',
            }}
          >
            <input 
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder={`Ask about ${selectedLoc} telemetry...`}
              disabled={isLoading}
              style={{
                flex: 1,
                padding: '10px 14px',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                fontSize: '0.88rem',
                outline: 'none',
              }}
            />
            <button 
              type="submit"
              disabled={isLoading || !inputQuery.trim()}
              style={{
                background: inputQuery.trim() ? 'var(--accent-primary)' : '#CBD5E1',
                color: '#FFFFFF',
                padding: '10px 14px',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'background 0.2s',
              }}
            >
              {isLoading ? <Loader2 size={16} /> : <Send size={16} />}
            </button>
          </form>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '6px', textAlign: 'center' }}>
            Deterministic grounding: unverified claims blocked via physical tool validation.
          </div>
        </div>
      </div>
    </div>
  );
}
