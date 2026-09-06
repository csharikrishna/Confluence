import React, { useState, useEffect } from 'react';
import { Loader2, Sparkles, Waves } from 'lucide-react';

const STATUS_PHRASES = [
  "Ingesting 7 live oceanic & weather feeds...",
  "Collecting real-time wave buoy telemetry...",
  "Merging surface pressure & satellite radiance...",
  "Computing NOAA Heat Index & Magnus-Tetens dew point...",
  "Evaluating WMO Beaufort sea-state & small craft risks...",
  "Checking Bergeron pressure fall & inverse barometer surge...",
  "Cross-validating physical sensor boundaries...",
  "Synthesizing verified coastal guidance...",
];

/**
 * Claude-style cycling status indicator with smooth thematic buzzwords and active spinning radar
 */
export default function ClaudeLoadingIndicator({ compact = false }) {
  const [index, setIndex] = useState(0);
  const [fade, setFade] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setIndex((prev) => (prev + 1) % STATUS_PHRASES.length);
        setFade(true);
      }, 200);
    }, 1800);

    return () => clearInterval(timer);
  }, []);

  return (
    <div
      role="status"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '10px',
        padding: compact ? '8px 14px' : '10px 18px',
        background: '#FFFFFF',
        border: '1px solid var(--accent-border, #A5F3FC)',
        borderRadius: '999px',
        boxShadow: '0 2px 8px -2px rgba(8, 145, 178, 0.12)',
        fontSize: compact ? '0.82rem' : '0.86rem',
        color: 'var(--text-secondary, #475569)',
        width: 'fit-content',
        maxWidth: '100%',
        transition: 'all 0.2s ease',
      }}
    >
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Loader2
          size={compact ? 15 : 17}
          className="animate-spin"
          style={{
            color: 'var(--accent-primary, #0891B2)',
          }}
          aria-hidden="true"
        />
      </div>

      <span
        style={{
          display: 'inline-block',
          fontStyle: 'normal',
          fontWeight: 500,
          color: 'var(--text-primary)',
          opacity: fade ? 1 : 0,
          transform: fade ? 'translateY(0)' : 'translateY(-2px)',
          transition: 'opacity 0.2s ease, transform 0.2s ease',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {STATUS_PHRASES[index]}
      </span>

      <span
        style={{
          display: 'inline-block',
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          background: 'var(--accent-primary, #0891B2)',
          animation: 'pulseGlow 1.2s ease-in-out infinite',
        }}
        aria-hidden="true"
      />
    </div>
  );
}
