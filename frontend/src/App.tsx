import React, { useEffect, useState } from 'react';
import { Header, NavTab } from './components/Header';
import { HomePage } from './pages/HomePage';
import { HowItWorksPage } from './pages/HowItWorksPage';
import { AboutPage } from './pages/AboutPage';
import { PrivacyPage } from './pages/PrivacyPage';
import { fetchBackendHealth } from './services/api';
import { HealthResponse } from './types/pdf';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>('home');
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    fetchBackendHealth()
      .then(setHealth)
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Header activeTab={activeTab} onSelectTab={setActiveTab} health={health} />

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        {activeTab === 'home' && <HomePage />}
        {activeTab === 'how-it-works' && (
          <HowItWorksPage onGoHome={() => setActiveTab('home')} />
        )}
        {activeTab === 'about' && <AboutPage />}
        {activeTab === 'privacy' && <PrivacyPage />}
      </main>

      <footer className="border-t border-slate-200/80 bg-white py-5">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 text-xs text-slate-500 sm:flex-row sm:px-6 lg:px-8">
          <p>
            <strong>OptiPDF Studio</strong> — Precision Custom Target-Size PDF Reducer
          </p>
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => setActiveTab('how-it-works')}
              className="hover:text-indigo-600"
            >
              How it works
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('privacy')}
              className="hover:text-indigo-600"
            >
              Privacy
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('about')}
              className="hover:text-indigo-600"
            >
              About
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
