import React from 'react';
import { MessageSquare } from 'lucide-react';

export function FloatingChatButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 40,
        background: 'linear-gradient(135deg, #0891B2 0%, #0E7490 100%)',
        color: '#FFFFFF',
        padding: '12px 20px',
        borderRadius: 'var(--radius-full)',
        boxShadow: '0 8px 24px rgba(8, 145, 178, 0.35)',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        fontWeight: 600,
        fontSize: '0.9rem',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        border: 'none',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = '0 12px 30px rgba(8, 145, 178, 0.45)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = '0 8px 24px rgba(8, 145, 178, 0.35)';
      }}
      aria-label="Open Coastal Chatbot"
    >
      <span style={{
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        background: '#10B981',
        boxShadow: '0 0 8px #10B981',
      }} />
      <span>Ask Coastal AI</span>
      <MessageSquare size={17} />
    </button>
  );
}
