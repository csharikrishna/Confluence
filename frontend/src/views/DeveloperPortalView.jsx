import React, { useState } from 'react';
import { 
  Key, 
  Copy, 
  Check, 
  Trash2, 
  Plus, 
  ShieldCheck, 
  Terminal, 
  Code, 
  AlertTriangle, 
  User, 
  Lock, 
  Mail, 
  ArrowRight,
  ExternalLink
} from 'lucide-react';

export function DeveloperPortalView({ 
  user, 
  onLoginSuccess, 
  onLogout, 
  onRefreshUser 
}) {
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register'
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  // Key creation state
  const [newKeyName, setNewKeyName] = useState('Default API Key');
  const [createdRawKey, setCreatedRawKey] = useState(null);
  const [isGeneratingKey, setIsGeneratingKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  // Quickstart code snippet state
  const [activeSnippetTab, setActiveSnippetTab] = useState('curl'); // 'curl', 'python', 'javascript'
  const [snippetStation, setSnippetStation] = useState({ name: 'Chennai Coast', lat: 13.08, lon: 80.27 });
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  const activeKeyPrefix = user?.api_keys?.[0]?.key_prefix || 'conf_live_demo_key_example';

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);

    try {
      const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body = authMode === 'login' 
        ? { username_or_email: username || email, password }
        : { email, username, password };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail?.message || data.detail || 'Authentication failed');
      }

      const tok = data.session_token || data.token;
      if (tok) {
        localStorage.setItem('conf_session_token', tok);
      }

      if (authMode === 'register') {
        const raw = data.initial_api_key?.raw_key || data.raw_key;
        if (raw) {
          setCreatedRawKey(raw);
        }
      }

      onLoginSuccess(data.user, tok);
      if (onRefreshUser) onRefreshUser();
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleGenerateKey = async (e) => {
    e.preventDefault();
    setIsGeneratingKey(true);
    try {
      const token = localStorage.getItem('conf_session_token');
      const res = await fetch('/api/auth/keys', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ key_name: newKeyName, label: newKeyName })
      });

      if (!res.ok) {
        throw new Error('Failed to generate API key');
      }

      const data = await res.json();
      setCreatedRawKey(data.raw_key || data.api_key);
      if (onRefreshUser) onRefreshUser();
    } catch (err) {
      alert(err.message);
    } finally {
      setIsGeneratingKey(false);
    }
  };

  const handleRevokeKey = async (keyId) => {
    if (!window.confirm('Are you sure you want to revoke this API key? Applications using it will immediately receive 401 Unauthorized.')) {
      return;
    }

    try {
      const token = localStorage.getItem('conf_session_token');
      const res = await fetch(`/api/auth/keys/${keyId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (res.ok) {
        onRefreshUser();
      } else {
        alert('Failed to revoke key');
      }
    } catch (err) {
      console.error(err);
    }
  };

  const copyToClipboard = (text, setCopied) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const currentDisplayKey = createdRawKey || activeKeyPrefix;

  const codeSnippets = {
    curl: `curl -X GET "https://confluence-ocean.onrender.com/environment?lat=${snippetStation.lat}&lon=${snippetStation.lon}&name=${encodeURIComponent(snippetStation.name)}" \\
  -H "X-API-Key: ${currentDisplayKey}" \\
  -H "Accept: application/json"`,

    python: `import requests

url = "https://confluence-ocean.onrender.com/environment"
params = {
    "lat": ${snippetStation.lat},
    "lon": ${snippetStation.lon},
    "name": "${snippetStation.name}"
}
headers = {
    "X-API-Key": "${currentDisplayKey}",
    "Accept": "application/json"
}

response = requests.get(url, params=params, headers=headers)
telemetry = response.json()

print(f"Significant Wave Height: {telemetry['data']['marine']['wave_height_m']} m")
print(f"Heat Index: {telemetry['data']['derived_insights']['heat_index_c']} °C")`,

    javascript: `// Confluence Coastal Telemetry API Client
const endpoint = new URL("https://confluence-ocean.onrender.com/environment");
endpoint.searchParams.set("lat", "${snippetStation.lat}");
endpoint.searchParams.set("lon", "${snippetStation.lon}");
endpoint.searchParams.set("name", "${snippetStation.name}");

const response = await fetch(endpoint, {
  headers: {
    "X-API-Key": "${currentDisplayKey}",
    "Accept": "application/json"
  }
});

const data = await response.json();
console.log("Current Sea State:", data.data.derived_insights.sea_state);
console.log("Air Temperature:", data.data.weather.temperature_c);`
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '36px' }}>
      {/* Live region for accessibility announcements */}
      <div aria-live="polite" aria-atomic="true" className="skip-link">
        {copiedKey ? 'API key copied to clipboard' : ''}
        {copiedSnippet ? 'Code snippet copied to clipboard' : ''}
      </div>
      
      {/* Header Banner */}
      <div>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          background: 'var(--accent-light)',
          color: 'var(--accent-primary)',
          border: '1px solid var(--accent-border)',
          padding: '4px 12px',
          borderRadius: 'var(--radius-full)',
          fontSize: '0.82rem',
          fontWeight: 600,
          marginBottom: '12px',
        }}>
          <Terminal size={14} aria-hidden="true" />
          <span>Developer API Gateway • Authentication & Key Management</span>
        </div>
        <h1 style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', textWrap: 'balance' }}>
          Confluence Developer Portal
        </h1>
        <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginTop: '4px', maxWidth: '720px' }}>
          Authenticate your coastal applications, manage secure API credentials, and query our multi-source telemetry endpoints.
        </p>
      </div>

      {/* Raw Key Modal if newly created */}
      {createdRawKey && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-key-title">
          <div className="modal-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--status-success)', marginBottom: '14px' }}>
              <ShieldCheck size={24} aria-hidden="true" />
              <h2 id="modal-key-title" style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--text-primary)', margin: 0 }}>
                New Confluence API Key Generated
              </h2>
            </div>

            <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: 1.5 }}>
              Please copy and safely store your API key now. For your security, this raw key will not be shown again.
            </p>

            <div style={{
              background: 'var(--code-bg)',
              color: 'var(--code-text)',
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.88rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px',
              wordBreak: 'break-all',
              marginBottom: '18px',
            }}>
              <span className="tabular-nums">{createdRawKey}</span>
              <button
                type="button"
                onClick={() => copyToClipboard(createdRawKey, setCopiedKey)}
                aria-label="Copy new API key to clipboard"
                style={{
                  background: 'rgba(255, 255, 255, 0.15)',
                  color: '#FFFFFF',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.78rem',
                  flexShrink: 0,
                  cursor: 'pointer',
                  border: 'none',
                }}
              >
                {copiedKey ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
                <span>{copiedKey ? 'Copied' : 'Copy Key'}</span>
              </button>
            </div>

            <div style={{
              background: 'var(--status-warning-bg)',
              border: '1px solid var(--status-warning-border)',
              borderRadius: 'var(--radius-md)',
              padding: '10px 14px',
              fontSize: '0.8rem',
              color: '#92400E',
              marginBottom: '20px',
            }}>
              ⚠️ Treat this key like a password. Do not commit it to public repositories.
            </div>

            <button
              type="button"
              className="btn-primary"
              style={{ width: '100%' }}
              onClick={() => setCreatedRawKey(null)}
            >
              I Have Saved My API Key
            </button>
          </div>
        </div>
      )}

      {/* Main Content: Authenticated vs Unauthenticated */}
      {!user ? (
        /* Login / Register Card */
        <div style={{
          maxWidth: '480px',
          margin: '0 auto',
          width: '100%',
          background: '#FFFFFF',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-xl)',
          padding: '32px',
          boxShadow: 'var(--shadow-md)',
        }}>
          {/* Tabs */}
          <div 
            role="tablist" 
            aria-label="Authentication mode"
            style={{
              display: 'flex',
              background: 'var(--bg-card-subtle)',
              padding: '4px',
              borderRadius: 'var(--radius-md)',
              marginBottom: '24px',
            }}
          >
            <button
              type="button"
              role="tab"
              id="tab-login"
              aria-selected={authMode === 'login'}
              aria-controls="auth-form-panel"
              onClick={() => { setAuthMode('login'); setAuthError(''); }}
              style={{
                flex: 1,
                padding: '8px',
                borderRadius: '6px',
                fontSize: '0.88rem',
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: authMode === 'login' ? '#FFFFFF' : 'transparent',
                color: authMode === 'login' ? 'var(--text-primary)' : 'var(--text-secondary)',
                boxShadow: authMode === 'login' ? 'var(--shadow-sm)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              role="tab"
              id="tab-register"
              aria-selected={authMode === 'register'}
              aria-controls="auth-form-panel"
              onClick={() => { setAuthMode('register'); setAuthError(''); }}
              style={{
                flex: 1,
                padding: '8px',
                borderRadius: '6px',
                fontSize: '0.88rem',
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: authMode === 'register' ? '#FFFFFF' : 'transparent',
                color: authMode === 'register' ? 'var(--text-primary)' : 'var(--text-secondary)',
                boxShadow: authMode === 'register' ? 'var(--shadow-sm)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              Create Account
            </button>
          </div>

          <form id="auth-form-panel" role="tabpanel" aria-labelledby={authMode === 'login' ? 'tab-login' : 'tab-register'} onSubmit={handleAuthSubmit}>
            {authMode === 'register' && (
              <div className="form-group">
                <label htmlFor="auth-email" className="form-label">Email Address</label>
                <div style={{ position: 'relative' }}>
                  <input
                    id="auth-email"
                    name="email"
                    type="email"
                    required
                    autoComplete="email"
                    spellCheck={false}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="developer@maritime-org.com"
                    className="form-input"
                  />
                </div>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="auth-username" className="form-label">
                {authMode === 'register' ? 'Username' : 'Username or Email'}
              </label>
              <input
                id="auth-username"
                name="username"
                type="text"
                required
                autoComplete={authMode === 'login' ? 'username' : 'new-username'}
                spellCheck={false}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="coastal_dev"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="auth-password" className="form-label">Password</label>
              <input
                id="auth-password"
                name="password"
                type="password"
                required
                autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="form-input"
              />
            </div>

            {authError && (
              <div 
                role="alert"
                style={{
                  padding: '10px 14px',
                  background: 'var(--status-danger-bg)',
                  border: '1px solid var(--status-danger-border)',
                  color: 'var(--status-danger)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.82rem',
                  marginBottom: '16px',
                }}
              >
                {authError}
              </div>
            )}

            <button
              type="submit"
              disabled={authLoading}
              className="btn-primary"
              style={{ width: '100%', padding: '12px' }}
            >
              {authLoading ? 'Authenticating…' : authMode === 'login' ? 'Sign In' : 'Create Account & Issue Key'}
            </button>
          </form>

          <div style={{ marginTop: '20px', fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center' }}>
            New accounts receive an instant <code style={{ color: 'var(--accent-primary)' }}>conf_live_…</code> API key.
          </div>
        </div>
      ) : (
        /* Authenticated Developer Dashboard */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          
          {/* User Profile Banner */}
          <div style={{
            background: '#FFFFFF',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            padding: '24px',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: 'var(--accent-light)',
                color: 'var(--accent-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: '1.2rem',
              }}>
                {user.username?.[0]?.toUpperCase() || 'U'}
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {user.username}
                  </span>
                  <span className="badge badge-success">Active Developer</span>
                </div>
                <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  {user.email} • Tier: Free Developer (100&nbsp;req/min)
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button 
                type="button"
                onClick={onLogout}
                className="btn-secondary"
                style={{ fontSize: '0.85rem' }}
                aria-label="Sign out of developer account"
              >
                Sign Out
              </button>
            </div>
          </div>

          {/* Active API Keys Section */}
          <div className="card">
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              marginBottom: '20px',
            }}>
              <div>
                <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Active API Keys ({user.api_keys?.length || 0})
                </h2>
                <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
                  Keys authenticate your calls to <code style={{ color: 'var(--accent-primary)' }}>/environment</code> and other endpoints.
                </p>
              </div>

              {/* Create Key Form */}
              <form onSubmit={handleGenerateKey} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <label htmlFor="new-key-name" className="skip-link">New API Key Name</label>
                <input
                  id="new-key-name"
                  name="keyName"
                  type="text"
                  spellCheck={false}
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="Key name (e.g. Staging App)"
                  className="form-input"
                  style={{ width: '200px', padding: '8px 12px', fontSize: '0.84rem' }}
                />
                <button
                  type="submit"
                  disabled={isGeneratingKey}
                  className="btn-primary"
                  style={{ padding: '8px 14px', fontSize: '0.84rem' }}
                  aria-label="Generate new API key"
                >
                  <Plus size={16} aria-hidden="true" />
                  <span>Generate Key</span>
                </button>
              </form>
            </div>

            {/* Keys Table */}
            {user.api_keys && user.api_keys.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: '0.86rem',
                  textAlign: 'left',
                }}>
                  <caption className="skip-link">Registered API Keys and access permissions</caption>
                  <thead>
                    <tr style={{ background: 'var(--bg-card-subtle)', borderBottom: '1px solid var(--border-color)' }}>
                      <th scope="col" style={{ padding: '12px 16px', fontWeight: 600 }}>Key Name</th>
                      <th scope="col" style={{ padding: '12px 16px', fontWeight: 600 }}>Key Prefix</th>
                      <th scope="col" style={{ padding: '12px 16px', fontWeight: 600 }}>Created</th>
                      <th scope="col" style={{ padding: '12px 16px', fontWeight: 600 }}>Last Used</th>
                      <th scope="col" style={{ padding: '12px 16px', fontWeight: 600 }}>Status</th>
                      <th scope="col" style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {user.api_keys.map((k) => (
                      <tr key={k.key_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                        <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {k.key_name || 'API Key'}
                        </td>
                        <td className="tabular-nums" style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '0.82rem', color: 'var(--accent-primary)' }}>
                          {k.key_prefix}
                        </td>
                        <td className="tabular-nums" style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                          {k.created_at ? new Date(k.created_at).toLocaleDateString() : 'Today'}
                        </td>
                        <td className="tabular-nums" style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                          {k.last_used_at ? new Date(k.last_used_at).toLocaleTimeString() : 'Never'}
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          <span className={`badge ${k.is_active ? 'badge-success' : 'badge-danger'}`}>
                            {k.is_active ? 'Active' : 'Revoked'}
                          </span>
                        </td>
                        <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                          {k.is_active ? (
                            <button
                              type="button"
                              onClick={() => handleRevokeKey(k.key_id)}
                              className="btn-danger"
                              aria-label={`Revoke API key ${k.key_name || k.key_prefix}`}
                            >
                              <Trash2 size={13} aria-hidden="true" />
                              Revoke
                            </button>
                          ) : (
                            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                              Deactivated
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{
                textAlign: 'center',
                padding: '32px 16px',
                color: 'var(--text-secondary)',
                fontSize: '0.9rem',
              }}>
                No active API keys found. Click “Generate Key” above to create your first key.
              </div>
            )}
          </div>

          {/* Interactive Code Generator & Quickstart */}
          <div className="card">
            <div style={{ marginBottom: '18px' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--accent-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Integration Quickstart
              </div>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                Query Live Coastal Telemetry
              </h2>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Pass your key via the <code style={{ color: 'var(--accent-primary)' }}>X-API-Key</code> HTTP header.
              </p>
            </div>

            {/* Code Block */}
            <div className="code-block-wrapper">
              <div className="code-header">
                <div className="code-tabs" role="tablist" aria-label="Code sample language">
                  <button
                    type="button"
                    role="tab"
                    id="code-tab-curl"
                    aria-selected={activeSnippetTab === 'curl'}
                    aria-controls="code-panel"
                    className={`code-tab-btn ${activeSnippetTab === 'curl' ? 'active' : ''}`}
                    onClick={() => setActiveSnippetTab('curl')}
                  >
                    cURL
                  </button>
                  <button
                    type="button"
                    role="tab"
                    id="code-tab-python"
                    aria-selected={activeSnippetTab === 'python'}
                    aria-controls="code-panel"
                    className={`code-tab-btn ${activeSnippetTab === 'python' ? 'active' : ''}`}
                    onClick={() => setActiveSnippetTab('python')}
                  >
                    Python (requests)
                  </button>
                  <button
                    type="button"
                    role="tab"
                    id="code-tab-js"
                    aria-selected={activeSnippetTab === 'javascript'}
                    aria-controls="code-panel"
                    className={`code-tab-btn ${activeSnippetTab === 'javascript' ? 'active' : ''}`}
                    onClick={() => setActiveSnippetTab('javascript')}
                  >
                    JavaScript (fetch)
                  </button>
                </div>

                <button
                  type="button"
                  className="code-copy-btn"
                  onClick={() => copyToClipboard(codeSnippets[activeSnippetTab], setCopiedSnippet)}
                  aria-label={`Copy ${activeSnippetTab} code snippet to clipboard`}
                >
                  {copiedSnippet ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
                  <span>{copiedSnippet ? 'Copied' : 'Copy Snippet'}</span>
                </button>
              </div>

              <pre id="code-panel" role="tabpanel" aria-labelledby={`code-tab-${activeSnippetTab === 'javascript' ? 'js' : activeSnippetTab}`} className="code-content">
                <code>{codeSnippets[activeSnippetTab]}</code>
              </pre>
            </div>
          </div>

          {/* Rate Limits & SLA */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '16px',
          }}>
            <div style={{ background: '#FFFFFF', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Tier Rate Limit</div>
              <div className="tabular-nums" style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>100&nbsp;requests / min</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>Burst capacity with sliding window</div>
            </div>

            <div style={{ background: '#FFFFFF', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Uptime SLA</div>
              <div className="tabular-nums" style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>99.9% Target SLA</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>Multi-source failover architecture</div>
            </div>

            <div style={{ background: '#FFFFFF', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>OpenAPI Schema</div>
              <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
                <a 
                  href="/docs" 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  aria-label="Open Interactive Swagger UI in a new tab"
                >
                  Swagger UI <ExternalLink size={16} aria-hidden="true" />
                </a>
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>Interactive testing & client generation</div>
            </div>
          </div>

        </div>
      )}

    </div>
  );
}

