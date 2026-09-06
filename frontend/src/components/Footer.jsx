import React from 'react';
import { ShieldCheck, GitFork, Terminal, BookOpen } from 'lucide-react';

export function Footer({ onNavigate }) {
  return (
    <footer 
      role="contentinfo"
      style={{
        background: '#FFFFFF',
        borderTop: '1px solid var(--border-color)',
        padding: '40px 24px 32px 24px',
        marginTop: 'auto',
        width: '100%',
      }}
    >
      <div style={{
        maxWidth: '1240px',
        margin: '0 auto',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '32px',
        marginBottom: '32px',
      }}>
        {/* Col 1 */}
        <div>
          <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-primary)', marginBottom: '10px' }}>
            Confluence Platform
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            Production-grade coastal and oceanographic environmental intelligence. Synthesizing 50+ real-time hyperparameters from 7 upstream scientific providers with deterministic physics derivations.
          </p>
        </div>

        {/* Col 2 */}
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)', marginBottom: '12px' }}>
            7 Upstream Providers
          </div>
          <ul style={{ listStyle: 'none', padding: 0, fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.8' }}>
            <li>• Open-Meteo Weather (Atmospheric array)</li>
            <li>• Open-Meteo Marine (Wave & hydrodynamic)</li>
            <li>• OpenAQ Ground Array (Physical PM sensors)</li>
            <li>• USGS Seismic (Coastal earthquake & tsunami)</li>
            <li>• NASA POWER (Solar irradiance & radiation)</li>
            <li>• Sunrise-Sunset Engine (Ephemeris)</li>
            <li>• Open-Elevation (Topography & bathymetry)</li>
          </ul>
        </div>

        {/* Col 3 */}
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)', marginBottom: '12px' }}>
            Developer Resources
          </div>
          <ul style={{ listStyle: 'none', padding: 0, fontSize: '0.84rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <li>
              <button 
                type="button"
                onClick={() => onNavigate('developer')} 
                style={{ 
                  color: 'var(--accent-primary)', 
                  textAlign: 'left', 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '6px',
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  font: 'inherit',
                }}
                aria-label="Navigate to Developer Portal and API Keys"
              >
                <Terminal size={14} aria-hidden="true" />
                <span>Get Confluence API Keys</span>
              </button>
            </li>
            <li>
              <button 
                type="button"
                onClick={() => onNavigate('health')} 
                style={{ 
                  color: 'var(--accent-primary)', 
                  textAlign: 'left', 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '6px',
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  font: 'inherit',
                }}
                aria-label="Navigate to Upstream Provider Diagnostics and Status"
              >
                <ShieldCheck size={14} aria-hidden="true" />
                <span>Upstream Provider Status</span>
              </button>
            </li>
            <li>
              <a 
                href="/docs" 
                target="_blank" 
                rel="noopener noreferrer"
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                aria-label="Open Interactive OpenAPI Swagger documentation in a new tab"
              >
                <BookOpen size={14} aria-hidden="true" />
                <span>Interactive OpenAPI Docs (/docs)</span>
              </a>
            </li>
            <li>
              <a 
                href="https://github.com" 
                target="_blank" 
                rel="noopener noreferrer"
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                aria-label="Open Architecture and Schema documentation on GitHub in a new tab"
              >
                <GitFork size={14} aria-hidden="true" />
                <span>Architecture & Schema Docs</span>
              </a>
            </li>
          </ul>
        </div>
      </div>

      {/* Bottom bar */}
      <div style={{
        maxWidth: '1240px',
        margin: '0 auto',
        paddingTop: '20px',
        borderTop: '1px solid var(--border-color)',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        fontSize: '0.8rem',
        color: 'var(--text-muted)',
      }}>
        <div>
          © 2026 Confluence Environmental Intelligence. Single-Process React + FastAPI Architecture.
        </div>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          <span>ISO 8601 UTC Canonical</span>
          <span>Dual SQLite/Mongo Store</span>
          <span>Deterministic Physics Derivations</span>
        </div>
      </div>
    </footer>
  );
}

