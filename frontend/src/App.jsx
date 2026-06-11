import { useState, useEffect } from 'react';
import ChatWindow from './components/ChatWindow';
import JournalEditor from './components/JournalEditor';
import JournalList from './components/JournalList';
import MeaningNetwork from './components/MeaningNetwork';
import AuthModal from './components/AuthModal';
import Dashboard from './components/Dashboard';
import OnboardingFlow from './components/OnboardingFlow';
import { BrainCircuit, Plus, MessageSquare, Globe, LogOut, Activity } from 'lucide-react';
import { apiUrl } from './api';
import './App.css';

function App() {
  const [token, setToken] = useState(localStorage.getItem('access_token') || null);
  const [userEmail, setUserEmail] = useState(localStorage.getItem('user_email') || null);
  const [currentMode, setCurrentMode] = useState('dashboard');
  const [journals, setJournals] = useState([]);
  const [isJournalsLoading, setIsJournalsLoading] = useState(Boolean(localStorage.getItem('access_token')));
  const [initialJournalForChat, setInitialJournalForChat] = useState(null);
  const [activeJournalId, setActiveJournalId] = useState(null);
  const [preselectedDate, setPreselectedDate] = useState(null);
  const [showOnboarding, setShowOnboarding] = useState(false);

  // 로그인 성공 콜백
  const handleLoginSuccess = (newToken, email) => {
    setIsJournalsLoading(true);
    setToken(newToken);
    setUserEmail(email);
    // 신규 사용자일 때만 온보딩 표시
    if (localStorage.getItem('onboarding_done') !== 'true') {
      setShowOnboarding(true);
    }
  };

  // 로그아웃 처리
  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_email');
    localStorage.removeItem('analyzed_journal_ids');
    setToken(null);
    setUserEmail(null);
    setJournals([]);
    setIsJournalsLoading(false);
    setCurrentMode('editor');
    setActiveJournalId(null);
    setInitialJournalForChat(null);
  };

  // 과거 일기 목록 가져오기
  const fetchJournals = async () => {
    if (!token) {
      setIsJournalsLoading(false);
      return;
    }
    try {
      setIsJournalsLoading(true);
      const response = await fetch(apiUrl('/api/journals'), {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setJournals(data);
      } else if (response.status === 401) {
        handleLogout();
      }
    } catch (error) {
      console.error('Error fetching journals:', error);
    } finally {
      setIsJournalsLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchJournals();
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;

    const handleJournalAnalyzed = () => {
      fetchJournals();
    };

    window.addEventListener('journal_analyzed', handleJournalAnalyzed);
    return () => {
      window.removeEventListener('journal_analyzed', handleJournalAnalyzed);
    };
  }, [token]);

  // 새 일기 작성 완료 후 실행되는 분석 시작 콜백
  const handleStartAnalysis = (savedJournal) => {
    // 1. 일기 목록 리프레시
    fetchJournals();
    
    // 2. 해당 일기 정보를 채팅창으로 전달
    setInitialJournalForChat(savedJournal);
    setActiveJournalId(savedJournal.id);
    
    // 3. 채팅창으로 전환
    setCurrentMode('chat');
    setPreselectedDate(null);
  };

  // 일기만 저장하고 대시보드로 가는 콜백
  const handleSaveOnly = () => {
    fetchJournals();
    setCurrentMode('dashboard');
    setPreselectedDate(null);
  };

  // 과거 일기를 선택하여 대화 시작하기
  const handleSelectJournal = (journal) => {
    setInitialJournalForChat(journal);
    setActiveJournalId(journal.id);
    setCurrentMode('chat');
  };

  // 일기 삭제 핸들러
  const handleDeleteJournal = async (journalId) => {
    if (!window.confirm("정말로 이 감정 성찰 일기를 삭제하시겠습니까?\n해당 일기에 속한 모든 성찰 대화 기록도 연쇄 삭제됩니다.")) {
      return;
    }
    
    try {
      const response = await fetch(apiUrl(`/api/journals/${journalId}`), {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        // 일기 목록 새로고침
        fetchJournals();
        
        // 만약 삭제하려는 일기가 현재 활성화되어 있는 일기라면 대시보드로 이동
        if (activeJournalId === journalId) {
          setActiveJournalId(null);
          setInitialJournalForChat(null);
          setCurrentMode('dashboard');
        }
        
        // localStorage 내 analyzed_journal_ids 리스트에서도 삭제
        try {
          const analyzedIds = JSON.parse(localStorage.getItem('analyzed_journal_ids') || '[]');
          const updatedIds = analyzedIds.filter(id => id !== journalId);
          localStorage.setItem('analyzed_journal_ids', JSON.stringify(updatedIds));
        } catch (e) {
          console.error("Error updating localStorage after deletion:", e);
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(`일기 삭제에 실패했습니다: ${errorData.detail || '서버 오류'}`);
      }
    } catch (error) {
      console.error('Error deleting journal:', error);
      alert('일기를 삭제하는 중 네트워크 오류가 발생했습니다.');
    }
  };


  // 새 일기 쓰기 화면으로 이동
  const handleNewJournal = (dateStr = null) => {
    const validDateStr = typeof dateStr === 'string' ? dateStr : null;
    setPreselectedDate(validDateStr);
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

  // 비로그인 상태일 때는 글라스모피즘 AuthModal만 보여줌
  if (!token) {
    return <AuthModal onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <>
    {showOnboarding && (
      <OnboardingFlow onComplete={() => {
        setShowOnboarding(false);
        setCurrentMode('editor');
      }} />
    )}
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
          <button className={`sidebar-action-btn ${currentMode === 'dashboard' ? 'active-mode' : ''}`} onClick={() => { setCurrentMode('dashboard'); setActiveJournalId(null); setInitialJournalForChat(null); }}>
            <Activity size={16} style={{ marginRight: '6px' }} />
            홈 대시보드
          </button>
          <button className={`sidebar-action-btn ${currentMode === 'editor' ? 'active-mode' : ''}`} onClick={() => handleNewJournal()} style={{ marginTop: 0 }}>
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
              } catch {
                return j;
              }
            })} 
            onSelectJournal={handleSelectJournal} 
            onDeleteJournal={handleDeleteJournal}
            activeJournalId={activeJournalId} 
          />
          {/* 사이드바 최하단 로그인 정보 배지 및 로그아웃 버튼 */}
          <div className="sidebar-footer">
            <div className="user-info">
              <span className="user-email-text" title={userEmail}>
                👤 {userEmail}
              </span>
            </div>
            <button className="logout-btn" onClick={handleLogout}>
              <LogOut size={13} style={{ marginRight: '6px' }} />
              로그아웃
            </button>
          </div>
        </aside>

        {/* 우측 메인 콘텐츠 영역 */}
        <main className="content-area">
          {currentMode === 'dashboard' && (
            <Dashboard 
              token={token} 
              journals={journals}
              isJournalsLoading={isJournalsLoading}
              onSelectJournal={handleSelectJournal}
              onNavigateToMode={(mode) => setCurrentMode(mode)}
              onNewJournalWithDate={handleNewJournal}
            />
          )}
          {currentMode === 'editor' && (
            <JournalEditor 
              token={token} 
              preselectedDate={preselectedDate}
              onStartAnalysis={handleStartAnalysis} 
              onSaveOnly={handleSaveOnly}
            />
          )}
          {currentMode === 'chat' && (
            <ChatWindow 
              token={token}
              initialJournal={initialJournalForChat} 
              onClearInitialJournal={() => setInitialJournalForChat(null)} 
              onNavigateToNetwork={() => setCurrentMode('network')}
            />
          )}
          {currentMode === 'network' && (
            <MeaningNetwork token={token} />
          )}
        </main>
      </div>
    </div>
    </>
  );
}

export default App;
