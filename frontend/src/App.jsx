import { useState, useEffect, useCallback } from 'react';
import ChatWindow from './components/ChatWindow';
import JournalEditor from './components/JournalEditor';
import JournalList from './components/JournalList';
import MeaningNetwork from './components/MeaningNetwork';
import AuthModal from './components/AuthModal';
import Dashboard from './components/Dashboard';
import OnboardingFlow from './components/OnboardingFlow';
import { AlertTriangle, BrainCircuit, Check, Plus, MessageSquare, Globe, LogOut, Activity, Loader2 } from 'lucide-react';
import {
  AUTH_SESSION_EXPIRED_EVENT,
  AUTH_TOKEN_REFRESHED_EVENT,
  clearAuthSession,
  clearPersistedAuthCredentials,
  fetchApi,
  fetchWithAuth,
  refreshAccessToken,
} from './api';
import { apiResponseError, responseJsonOrNull } from './utils/apiErrors';
import { getAnalyzedJournalIds, removeAnalyzedJournalId } from './utils/analyzedJournals';
import { hasCompletedOnboarding } from './utils/onboardingState';
import './App.css';

function App() {
  const [token, setToken] = useState(null);
  const [userEmail, setUserEmail] = useState(null);
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  const [currentMode, setCurrentMode] = useState('dashboard');
  const [journals, setJournals] = useState([]);
  const [isJournalsLoading, setIsJournalsLoading] = useState(false);
  const [initialJournalForChat, setInitialJournalForChat] = useState(null);
  const [activeJournalId, setActiveJournalId] = useState(null);
  const [preselectedDate, setPreselectedDate] = useState(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [appNotice, setAppNotice] = useState(null);

  // 로그인 성공 콜백
  const handleLoginSuccess = (newToken, email) => {
    setIsJournalsLoading(true);
    setToken(newToken);
    setUserEmail(email);
    // 신규 사용자일 때만 온보딩 표시
    if (!hasCompletedOnboarding()) {
      setShowOnboarding(true);
    }
  };

  // 로그아웃 처리
  const handleLogout = useCallback(() => {
    fetchApi('/api/auth/logout', {
      method: 'POST',
    }).catch(() => {});
    clearAuthSession();
    setToken(null);
    setUserEmail(null);
    setJournals([]);
    setIsJournalsLoading(false);
    setCurrentMode('editor');
    setActiveJournalId(null);
    setInitialJournalForChat(null);
  }, []);

  useEffect(() => {
    const handleTokenRefreshed = (event) => {
      const { accessToken, email } = event.detail || {};
      if (accessToken) setToken(accessToken);
      if (email) setUserEmail(email);
    };

    window.addEventListener(AUTH_TOKEN_REFRESHED_EVENT, handleTokenRefreshed);
    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, handleLogout);
    return () => {
      window.removeEventListener(AUTH_TOKEN_REFRESHED_EVENT, handleTokenRefreshed);
      window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, handleLogout);
    };
  }, [handleLogout]);

  useEffect(() => {
    let isActive = true;

    const restoreSession = async () => {
      clearPersistedAuthCredentials();
      try {
        const restored = await refreshAccessToken({ emit: false });
        if (!isActive) return;
        if (restored?.access_token) {
          setToken(restored.access_token);
          setUserEmail(restored.user?.email || null);
          setIsJournalsLoading(true);
        }
      } catch (error) {
        console.warn('Session restore failed:', error);
      } finally {
        if (isActive) setIsAuthChecking(false);
      }
    };

    restoreSession();
    return () => {
      isActive = false;
    };
  }, []);

  // 과거 일기 목록 가져오기
  const fetchJournals = useCallback(async () => {
    if (!token) {
      setIsJournalsLoading(false);
      return;
    }
    try {
      setIsJournalsLoading(true);
      const response = await fetchWithAuth('/api/journals', {
        token,
        onToken: (newToken, email) => {
          setToken(newToken);
          if (email) setUserEmail(email);
        },
        onUnauthorized: handleLogout,
      });
      if (response.status === 401) {
        handleLogout();
        return;
      }
      if (!response.ok) {
        throw await apiResponseError(response, '일기 목록을 불러오지 못했습니다.');
      }

      const data = await responseJsonOrNull(response);
      setJournals(Array.isArray(data) ? data : []);
    } catch (error) {
      console.warn('Error fetching journals:', error);
      setAppNotice({
        tone: 'error',
        message: error.message || '일기 목록을 불러오지 못했습니다.',
      });
    } finally {
      setIsJournalsLoading(false);
    }
  }, [token, handleLogout]);

  useEffect(() => {
    if (token) {
      fetchJournals();
    }
  }, [token, fetchJournals]);

  useEffect(() => {
    if (!token) return;

    const handleJournalAnalyzed = () => {
      fetchJournals();
    };

    window.addEventListener('journal_analyzed', handleJournalAnalyzed);
    return () => {
      window.removeEventListener('journal_analyzed', handleJournalAnalyzed);
    };
  }, [token, fetchJournals]);

  // 새 일기 작성 완료 후 실행되는 분석 시작 콜백
  const handleStartAnalysis = (savedJournal) => {
    setAppNotice(null);
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
    setAppNotice(null);
    fetchJournals();
    setCurrentMode('dashboard');
    setPreselectedDate(null);
  };

  // 과거 일기를 선택하여 대화 시작하기
  const handleSelectJournal = (journal) => {
    setAppNotice(null);
    setInitialJournalForChat(journal);
    setActiveJournalId(journal.id);
    setCurrentMode('chat');
  };

  // 일기 삭제 핸들러
  const handleDeleteJournal = async (journalId) => {
    if (!window.confirm("정말로 이 감정 성찰 일기를 삭제하시겠습니까?\n해당 일기에 속한 모든 성찰 대화 기록도 연쇄 삭제됩니다.")) {
      return;
    }
    
    setAppNotice(null);
    try {
      const response = await fetchWithAuth(`/api/journals/${journalId}`, {
        method: 'DELETE',
        token,
        onToken: (newToken, email) => {
          setToken(newToken);
          if (email) setUserEmail(email);
        },
        onUnauthorized: handleLogout,
      });

      if (!response.ok) {
        throw await apiResponseError(response, '일기 삭제에 실패했습니다.');
      }

      // 일기 목록 새로고침
      fetchJournals();

      // 만약 삭제하려는 일기가 현재 활성화되어 있는 일기라면 대시보드로 이동
      if (activeJournalId === journalId) {
        setActiveJournalId(null);
        setInitialJournalForChat(null);
        setCurrentMode('dashboard');
      }

      removeAnalyzedJournalId(journalId);
      setAppNotice({ tone: 'success', message: '일기를 삭제했습니다.' });
    } catch (error) {
      console.warn('Error deleting journal:', error);
      setAppNotice({
        tone: 'error',
        message: error.message || '일기를 삭제하는 중 오류가 발생했습니다.',
      });
    }
  };


  // 새 일기 쓰기 화면으로 이동
  const handleNewJournal = (dateStr = null) => {
    setAppNotice(null);
    const validDateStr = typeof dateStr === 'string' ? dateStr : null;
    setPreselectedDate(validDateStr);
    setCurrentMode('editor');
    setActiveJournalId(null);
    setInitialJournalForChat(null);
  };

  // 일반 채팅(일기 없는 채팅)으로 이동
  const handlePlainChat = () => {
    setAppNotice(null);
    setCurrentMode('chat');
    setActiveJournalId(null);
    setInitialJournalForChat(null);
  };

  // 의미 네트워크 화면으로 이동
  const handleShowNetwork = () => {
    setAppNotice(null);
    setCurrentMode('network');
    setActiveJournalId(null);
    setInitialJournalForChat(null);
  };

  if (isAuthChecking) {
    return (
      <div className="auth-overlay" style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(5, 5, 15, 0.85)', backdropFilter: 'blur(8px)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="auth-card glass-panel" style={{ width: '360px', padding: '32px 28px', borderRadius: '16px', border: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(10, 11, 26, 0.75)', boxShadow: '0 15px 35px rgba(0, 0, 0, 0.6)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', textAlign: 'center' }}>
          <Loader2 className="animate-spin" size={28} color="var(--accent-primary)" />
          <h2 style={{ fontSize: '1.3rem', fontWeight: '800', margin: 0, color: 'var(--text-main)' }}>Logos-Log</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.86rem', margin: 0 }}>세션을 확인하는 중...</p>
        </div>
      </div>
    );
  }

  // 비로그인 상태일 때는 글라스모피즘 AuthModal만 보여줌
  if (!token) {
    return <AuthModal onLoginSuccess={handleLoginSuccess} />;
  }

  const analyzedJournalIds = getAnalyzedJournalIds();

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
          <p>내 기록을 작은 실험과 회고로 이어주는 의미 행동 도구</p>
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
            journals={journals.map(j => ({
              ...j,
              is_analyzed: analyzedJournalIds.includes(j.id)
            }))}
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
          {appNotice && (
            <div className={`app-notice ${appNotice.tone}`} role={appNotice.tone === 'error' ? 'alert' : 'status'} aria-live="polite">
              {appNotice.tone === 'error' ? <AlertTriangle size={16} /> : <Check size={16} />}
              <span>{appNotice.message}</span>
              <button type="button" onClick={() => setAppNotice(null)} aria-label="알림 닫기">
                ×
              </button>
            </div>
          )}
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
