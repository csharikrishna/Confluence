import React, { useState } from 'react';
import { 
  Activity, 
  Key, 
  Radio, 
  MessageSquare, 
  Menu, 
  X, 
  ShieldCheck, 
  User, 
  LogOut,
  ExternalLink
} from 'lucide-react';

export function Header({ activeTab, setActiveTab, onOpenChat, user, onLogout }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleTabClick = (tab) => {
    setActiveTab(tab);
    setMobileMenuOpen(false);
  };

  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <header className="site-header" role="banner">
        <div className="header-inner">
          {/* Brand */}
          <div 
            className="brand-section" 
            onClick={() => handleTabClick('overview')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleTabClick('overview');
              }
            }}
            aria-label="Confluence Home"
          >
            <div className="brand-icon-wrapper" aria-hidden="true">
              <Radio size={22} />
            </div>
            <div>
              <div className="brand-title">
                Confluence
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '-2px' }}>
                Coastal Environmental Platform
              </div>
            </div>
          </div>

          {/* Desktop Navigation Tabs */}
          <nav className="nav-tabs" aria-label="Main Navigation">
            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => handleTabClick('overview')}
              aria-current={activeTab === 'overview' ? 'page' : undefined}
            >
              <Activity size={16} aria-hidden="true" />
              <span>Overview & Telemetry</span>
            </button>

            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'chatbot' ? 'active' : ''}`}
              onClick={() => handleTabClick('chatbot')}
              aria-current={activeTab === 'chatbot' ? 'page' : undefined}
            >
              <MessageSquare size={16} aria-hidden="true" />
              <span>Coastal Chatbot</span>
            </button>
            
            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'developer' ? 'active' : ''}`}
              onClick={() => handleTabClick('developer')}
              aria-current={activeTab === 'developer' ? 'page' : undefined}
            >
              <Key size={16} aria-hidden="true" />
              <span>Developer Portal</span>
              {user && (
                <span className="nav-tab-badge">
                  {user.api_keys?.length || 0}
                </span>
              )}
            </button>

            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'health' ? 'active' : ''}`}
              onClick={() => handleTabClick('health')}
              aria-current={activeTab === 'health' ? 'page' : undefined}
            >
              <ShieldCheck size={16} aria-hidden="true" />
              <span>Upstream Health</span>
              <span className="nav-tab-badge" style={{ background: '#ECFDF5', color: '#047857', fontWeight: 600 }}>
                7 Live
              </span>
            </button>
          </nav>

          {/* Header Actions */}
          <div className="header-actions">
            {user ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button 
                  type="button"
                  className="user-status-pill"
                  onClick={() => handleTabClick('developer')}
                  title="Manage API Keys"
                  aria-label={`User account: ${user.username}, with ${user.api_keys?.length || 0} active keys`}
                >
                  <div className="user-status-dot" aria-hidden="true" />
                  <span>{user.username}</span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    ({user.api_keys?.length || 0} keys)
                  </span>
                </button>
                <button 
                  type="button"
                  onClick={onLogout}
                  className="btn-secondary"
                  style={{ padding: '6px 10px', fontSize: '0.8rem' }}
                  title="Sign Out"
                  aria-label="Sign out of developer account"
                >
                  <LogOut size={14} aria-hidden="true" />
                </button>
              </div>
            ) : (
              <button 
                type="button"
                className="btn-secondary"
                onClick={() => handleTabClick('developer')}
                style={{ fontSize: '0.84rem', padding: '8px 14px' }}
                aria-label="Developer Access & API Keys"
              >
                <User size={15} aria-hidden="true" />
                <span>Developer Access</span>
              </button>
            )}

            <button 
              type="button"
              className="btn-ai-assistant"
              onClick={onOpenChat}
              id="open-chat-drawer-btn"
              aria-label="Open Coastal AI Assistant Drawer"
            >
              <MessageSquare size={16} aria-hidden="true" />
              <span>Coastal Chatbot</span>
            </button>

            {/* Mobile Menu Toggle */}
            <button 
              type="button"
              className="mobile-menu-btn"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle Navigation Menu"
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
            </button>
          </div>
        </div>

        {/* Mobile Drawer Menu */}
        {mobileMenuOpen && (
          <nav 
            className="mobile-drawer-menu"
            style={{
              background: '#FFFFFF',
              borderBottom: '1px solid var(--border-color)',
              padding: '16px 20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
            }}
            aria-label="Mobile Navigation"
          >
            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => handleTabClick('overview')}
              style={{ width: '100%', justifyContent: 'flex-start', padding: '12px 16px' }}
            >
              <Activity size={18} aria-hidden="true" />
              <span>Overview & Telemetry</span>
            </button>

            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'chatbot' ? 'active' : ''}`}
              onClick={() => handleTabClick('chatbot')}
              style={{ width: '100%', justifyContent: 'flex-start', padding: '12px 16px' }}
            >
              <MessageSquare size={18} aria-hidden="true" />
              <span>Coastal Chatbot (Live AI)</span>
            </button>
            
            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'developer' ? 'active' : ''}`}
              onClick={() => handleTabClick('developer')}
              style={{ width: '100%', justifyContent: 'flex-start', padding: '12px 16px' }}
            >
              <Key size={18} aria-hidden="true" />
              <span>Developer Portal & API Keys</span>
            </button>

            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'health' ? 'active' : ''}`}
              onClick={() => handleTabClick('health')}
              style={{ width: '100%', justifyContent: 'flex-start', padding: '12px 16px' }}
            >
              <ShieldCheck size={18} aria-hidden="true" />
              <span>Upstream Health (7 Providers)</span>
            </button>

            <a 
              href="/docs" 
              target="_blank" 
              rel="noopener noreferrer"
              className="nav-tab-btn"
              style={{ width: '100%', justifyContent: 'flex-start', padding: '12px 16px', color: 'var(--text-secondary)' }}
            >
              <ExternalLink size={18} aria-hidden="true" />
              <span>FastAPI Interactive Docs</span>
            </a>
          </nav>
        )}
      </header>
    </>
  );
}
