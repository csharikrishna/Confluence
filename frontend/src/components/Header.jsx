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
  ExternalLink,
  Sparkles,
  ChevronRight
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
          {/* Brand Section */}
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
            aria-label="Confluence Platform Home"
          >
            <div className="brand-icon-wrapper" aria-hidden="true">
              <Radio size={20} />
            </div>
            <div className="brand-text-block">
              <div className="brand-title-row">
                <span className="brand-title">Confluence</span>
                <span className="brand-live-badge">LIVE</span>
              </div>
              <span className="brand-subtitle">Coastal Environmental Platform</span>
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
              <Activity size={15} aria-hidden="true" />
              <span>Overview & Telemetry</span>
            </button>

            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'chatbot' ? 'active' : ''}`}
              onClick={() => handleTabClick('chatbot')}
              aria-current={activeTab === 'chatbot' ? 'page' : undefined}
            >
              <MessageSquare size={15} aria-hidden="true" />
              <span>Coastal Chatbot</span>
            </button>
            
            <button 
              type="button"
              className={`nav-tab-btn ${activeTab === 'developer' ? 'active' : ''}`}
              onClick={() => handleTabClick('developer')}
              aria-current={activeTab === 'developer' ? 'page' : undefined}
            >
              <Key size={15} aria-hidden="true" />
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
              <ShieldCheck size={15} aria-hidden="true" />
              <span>Upstream Health</span>
              <span className="nav-tab-badge nav-tab-badge-live">
                <span className="badge-pulse-dot" aria-hidden="true" />
                7 Live
              </span>
            </button>
          </nav>

          {/* Right Header Actions */}
          <div className="header-actions">
            {/* User Account / Login Status */}
            {user ? (
              <div className="header-user-wrapper">
                <button 
                  type="button"
                  className="user-status-pill"
                  onClick={() => handleTabClick('developer')}
                  title="Manage API Keys"
                  aria-label={`User account: ${user.username || user.name}, ${user.api_keys?.length || 0} active keys`}
                >
                  <span className="user-status-dot" aria-hidden="true" />
                  <span className="user-name-text">{user.username || user.name || "Developer"}</span>
                  <span className="user-key-count">
                    ({user.api_keys?.length || 0} {user.api_keys?.length === 1 ? 'key' : 'keys'})
                  </span>
                </button>
                <button 
                  type="button"
                  onClick={onLogout}
                  className="btn-header-signout"
                  title="Sign Out"
                  aria-label="Sign out of developer account"
                >
                  <LogOut size={14} aria-hidden="true" />
                </button>
              </div>
            ) : (
              <button 
                type="button"
                className="btn-header-login"
                onClick={() => handleTabClick('developer')}
                aria-label="Developer Access & API Keys"
              >
                <User size={14} aria-hidden="true" />
                <span>Dev Access</span>
              </button>
            )}

            {/* Mobile Menu Toggle Button */}
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

        {/* Mobile Navigation Drawer Overlay */}
        {mobileMenuOpen && (
          <nav className="mobile-drawer-menu" aria-label="Mobile Navigation">
            <div className="mobile-nav-links">
              <button 
                type="button"
                className={`mobile-nav-btn ${activeTab === 'overview' ? 'active' : ''}`}
                onClick={() => handleTabClick('overview')}
              >
                <div className="mobile-nav-btn-content">
                  <Activity size={18} />
                  <span>Overview & Telemetry</span>
                </div>
                <ChevronRight size={16} className="mobile-nav-arrow" />
              </button>

              <button 
                type="button"
                className={`mobile-nav-btn ${activeTab === 'chatbot' ? 'active' : ''}`}
                onClick={() => handleTabClick('chatbot')}
              >
                <div className="mobile-nav-btn-content">
                  <MessageSquare size={18} />
                  <span>Coastal Chatbot</span>
                </div>
                <span className="badge badge-accent" style={{ fontSize: '0.7rem' }}>AI</span>
              </button>
              
              <button 
                type="button"
                className={`mobile-nav-btn ${activeTab === 'developer' ? 'active' : ''}`}
                onClick={() => handleTabClick('developer')}
              >
                <div className="mobile-nav-btn-content">
                  <Key size={18} />
                  <span>Developer Portal</span>
                </div>
                {user && (
                  <span className="nav-tab-badge">
                    {user.api_keys?.length || 0} keys
                  </span>
                )}
              </button>

              <button 
                type="button"
                className={`mobile-nav-btn ${activeTab === 'health' ? 'active' : ''}`}
                onClick={() => handleTabClick('health')}
              >
                <div className="mobile-nav-btn-content">
                  <ShieldCheck size={18} />
                  <span>Upstream Health</span>
                </div>
                <span className="nav-tab-badge nav-tab-badge-live">
                  7 Live
                </span>
              </button>

              <a 
                href="/docs" 
                target="_blank" 
                rel="noopener noreferrer"
                className="mobile-nav-btn"
                style={{ color: 'var(--text-secondary)' }}
              >
                <div className="mobile-nav-btn-content">
                  <ExternalLink size={18} />
                  <span>FastAPI Swagger Docs</span>
                </div>
                <ChevronRight size={16} className="mobile-nav-arrow" />
              </a>
            </div>

            {/* Mobile User Profile Section */}
            <div className="mobile-user-section">
              {user ? (
                <div className="mobile-user-card">
                  <div className="mobile-user-info">
                    <div className="mobile-user-avatar">
                      {(user.username || user.name || 'D')[0].toUpperCase()}
                    </div>
                    <div>
                      <div className="mobile-user-name">{user.username || user.name}</div>
                      <div className="mobile-user-meta">
                        {user.api_keys?.length || 0} active API {user.api_keys?.length === 1 ? 'key' : 'keys'}
                      </div>
                    </div>
                  </div>
                  <button 
                    type="button" 
                    onClick={() => {
                      onLogout();
                      setMobileMenuOpen(false);
                    }}
                    className="btn-mobile-signout"
                  >
                    <LogOut size={15} />
                    <span>Sign Out</span>
                  </button>
                </div>
              ) : (
                <button 
                  type="button"
                  className="btn-mobile-login"
                  onClick={() => handleTabClick('developer')}
                >
                  <User size={16} />
                  <span>Developer Sign In & API Keys</span>
                </button>
              )}
            </div>
          </nav>
        )}
      </header>
    </>
  );
}
