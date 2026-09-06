import React from 'react';
import { Sparkles } from 'lucide-react';

export function FloatingChatButton({ onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="floating-chat-trigger"
      aria-label="Open Floating Coastal AI Assistant"
      title="Open Floating Coastal AI Assistant"
    >
      <span className="floating-chat-pulse-dot" />
      <span className="floating-chat-text">Ask Coastal AI</span>
      <Sparkles size={16} aria-hidden="true" />
    </button>
  );
}
