import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { ChatDrawer } from './components/ChatDrawer';
import { ChatbotSection } from './components/ChatbotSection';
import { FloatingChatButton } from './components/FloatingChatButton';
import { OverviewView } from './views/OverviewView';
import { DeveloperPortalView } from './views/DeveloperPortalView';
import { UpstreamHealthView } from './views/UpstreamHealthView';

export function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [user, setUser] = useState(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [locations, setLocations] = useState([
    { name: "Chennai Coast", lat: 13.08, lon: 80.27 },
    { name: "Visakhapatnam Coast", lat: 17.69, lon: 83.22 },
    { name: "Kochi Coast", lat: 9.93, lon: 76.26 },
    { name: "Mumbai Coast", lat: 18.94, lon: 72.84 },
    { name: "Kolkata / Sundarbans Coast", lat: 21.63, lon: 88.15 }
  ]);

  // Sync hash routing
  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace('#', '').toLowerCase();
      if (['overview', 'chatbot', 'developer', 'health'].includes(hash)) {
        setActiveTab(hash);
      }
    };
    handleHash();
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    window.location.hash = tab;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Check auth session
  const checkSession = async () => {
    const token = localStorage.getItem('conf_session_token');
    if (!token) {
      setUser(null);
      return;
    }

    try {
      const res = await fetch('/api/auth/me', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        localStorage.removeItem('conf_session_token');
        setUser(null);
      }
    } catch (err) {
      console.error("Session check error:", err);
    }
  };

  useEffect(() => {
    checkSession();

    fetch('/locations')
      .then(res => res.json())
      .then(data => {
        if (data.locations && data.locations.length > 0) {
          setLocations(data.locations);
        }
      })
      .catch(e => console.log("Using default coastal locations:", e));
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('conf_session_token');
    setUser(null);
  };

  return (
    <div className="app-container">
      {/* Navigation Header */}
      <Header 
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        onOpenChat={() => setIsChatOpen(true)}
        user={user}
        onLogout={handleLogout}
      />

      {/* Main Page View */}
      <main className="main-content">
        {activeTab === 'overview' && (
          <OverviewView 
            onNavigate={handleTabChange}
            onOpenChat={() => setIsChatOpen(true)}
          />
        )}

        {activeTab === 'chatbot' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <ChatbotSection />
          </div>
        )}

        {activeTab === 'developer' && (
          <DeveloperPortalView 
            user={user}
            onLoginSuccess={(userData) => setUser(userData)}
            onLogout={handleLogout}
            onRefreshUser={checkSession}
          />
        )}

        {activeTab === 'health' && (
          <UpstreamHealthView />
        )}
      </main>

      {/* Floating Action Button to launch drawer (only when not on full chatbot tab and drawer not open) */}
      {activeTab !== 'chatbot' && !isChatOpen && (
        <FloatingChatButton onClick={() => setIsChatOpen(true)} />
      )}

      {/* Slide-out Grounded Assistant Drawer */}
      <ChatDrawer 
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        locations={locations}
      />

      {/* Global Footer */}
      <Footer onNavigate={handleTabChange} />
    </div>
  );
}

export default App;
