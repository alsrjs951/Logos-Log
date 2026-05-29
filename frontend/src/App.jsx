import React, { useState, useEffect } from 'react';
import ChatWindow from './components/ChatWindow';
import JournalEditor from './components/JournalEditor';
import JournalList from './components/JournalList';
import MeaningNetwork from './components/MeaningNetwork';
import { BrainCircuit, Plus, MessageSquare, Globe } from 'lucide-react';
import './App.css';

function App() {
  const [currentMode, setCurrentMode] = useState('editor'); // 'editor' | 'chat' | 'network'
  const [journals, setJournals] = useState([]);
  const [initialJournalForChat, setInitialJournalForChat] = useState(null);
  const [activeJournalId, setActiveJournalId] = useState(null);

  // 과거 일기 목록 가져오기
  const fetchJournals = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/journals');
      if (response.ok) {
        const data = await response.json();
        setJournals(data);
      }
    } catch (error) {
      console.error('Error fetching journals:', error);
    }
  };

  useEffect(() => {
    fetchJournals();

    const handleJournalAnalyzed = () => {
      fetchJournals();
    };

    window.addEventListener('journal_analyzed', handleJournalAnalyzed);
    return () => {
      window.removeEventListener('journal_analyzed', handleJournalAnalyzed);
    };
  }, []);

  // 새 일기 작성 완료 후 실행되는 분석 시작 콜백
  const handleStartAnalysis = (savedJournal) => {
    // 1. 일기 목록 리프레시
    fetchJournals();
    
    // 2. 해당 일기 정보를 채팅창으로 전달
    setInitialJournalForChat(savedJournal);
    setActiveJournalId(savedJournal.id);
    
    // 3. 채팅창으로 전환
    setCurrentMode('chat');
  };

  // 과거 일기를 선택하여 대화 시작하기
  const handleSelectJournal = (journal) => {
    setInitialJournalForChat(journal);
    setActiveJournalId(journal.id);
    setCurrentMode('chat');
  };

  // 새 일기 쓰기 화면으로 이동
  const handleNewJournal = () => {
    setCurrentMode('editor');
    setActiveJournalId(null);
    setInitialJournalForChat(null);
  };

  // 일반 채팅(일기 없는 채팅)으로 이동
  const handlePlainChat = () => {
    setCurrentMode('chat');
    setActiveJournalId(null);
    setInitialJournalForChat(null);
  };

  // 의미 네트워크 화면으로 이동
  const handleShowNetwork = () => {
    setCurrentMode('network');
    setActiveJournalId(null);
    setInitialJournalForChat(null);
  };

  return (
    <div className="app-container glass-panel">
      <header className="app-header">
        <div className="logo-icon">
          <BrainCircuit size={24} />
        </div>
        <div className="header-titles">
          <h1>Logos-Log</h1>
          <p>학술 RAG 기반 실존적 의미 탐구 저널링 AI 동반자</p>
        </div>
      </header>

      <div className="main-layout">
        {/* 좌측 사이드바 */}
        <aside className="sidebar">
          <button className={`sidebar-action-btn ${currentMode === 'editor' ? 'active-mode' : ''}`} onClick={handleNewJournal}>
            <Plus size={16} />
            새 일기 쓰기
          </button>
          <button className={`sidebar-action-btn ${currentMode === 'chat' && !activeJournalId ? 'active-mode' : ''}`} onClick={handlePlainChat} style={{ marginTop: 0 }}>
            <MessageSquare size={16} />
            바로 대화하기
          </button>
          <button className={`sidebar-action-btn ${currentMode === 'network' ? 'active-mode' : ''}`} onClick={handleShowNetwork} style={{ marginTop: 0 }}>
            <Globe size={16} />
            의미 네트워크
          </button>

          <div className="sidebar-list-title">나의 감정 성찰 기록</div>
          <JournalList 
            journals={journals.map(j => {
              try {
                const analyzedIds = JSON.parse(localStorage.getItem('analyzed_journal_ids') || '[]');
                return {
                  ...j,
                  is_analyzed: analyzedIds.includes(j.id)
                };
              } catch (e) {
                return j;
              }
            })} 
            onSelectJournal={handleSelectJournal} 
            activeJournalId={activeJournalId} 
          />
        </aside>

        {/* 우측 메인 콘텐츠 영역 */}
        <main className="content-area">
          {currentMode === 'editor' && (
            <JournalEditor onStartAnalysis={handleStartAnalysis} />
          )}
          {currentMode === 'chat' && (
            <ChatWindow 
              initialJournal={initialJournalForChat} 
              onClearInitialJournal={() => setInitialJournalForChat(null)} 
              onNavigateToNetwork={() => setCurrentMode('network')}
            />
          )}
          {currentMode === 'network' && (
            <MeaningNetwork />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
