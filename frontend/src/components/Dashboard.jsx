import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Loader2, Calendar, Award, MessageSquare, Globe, Heart, ChevronLeft, ChevronRight, BookOpen, Clock, Activity } from 'lucide-react';

const EMOTION_COLORS = {
  happy: { color: '#10b981', emoji: '😊', label: '행복', bg: 'rgba(16, 185, 129, 0.15)' },
  sad: { color: '#6366f1', emoji: '😢', label: '슬픔', bg: 'rgba(99, 102, 241, 0.15)' },
  stressed: { color: '#ec4899', emoji: '🤯', label: '스트레스', bg: 'rgba(236, 72, 153, 0.15)' },
  calm: { color: '#06b6d4', emoji: '🧘', label: '평온', bg: 'rgba(6, 182, 212, 0.15)' },
  tired: { color: '#f59e0b', emoji: '😴', label: '피로', bg: 'rgba(245, 158, 11, 0.15)' }
};

const Dashboard = ({ token, onSelectJournal, onNavigateToMode, onNewJournalWithDate }) => {
  const [journals, setJournals] = useState([]);
  const [valueCardsCount, setValueCardsCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [currentDate, setCurrentDate] = useState(new Date());
  
  // 일기 상세 보기 모달 상태
  const [selectedJournal, setSelectedJournal] = useState(null);
  
  // 데이터 로드
  useEffect(() => {
    const fetchDashboardData = async () => {
      if (!token) return;
      try {
        setIsLoading(true);
        
        // 1. 일기 전체 목록 (상세 본문이 카드 피드와 모달에 필요하므로 전체 조회 활용)
        const journalRes = await fetch('http://localhost:8000/api/journals', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        let journalData = [];
        if (journalRes.ok) {
          journalData = await journalRes.json();
          setJournals(journalData);
        }

        // 2. 가치 카드 개수 조회
        const cardsRes = await fetch('http://localhost:8000/api/value-cards', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (cardsRes.ok) {
          const cardsData = await cardsRes.json();
          setValueCardsCount(cardsData.length);
        }
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboardData();
  }, [token]);

  // Streak (연속 작성 일수) 계산
  const calculateStreak = () => {
    if (journals.length === 0) return 0;
    
    // 날짜 문자열(YYYY-MM-DD) 중복 제거 및 내림차순 정렬
    const writtenDates = [...new Set(journals.map(j => {
      const d = new Date(j.created_at);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }))].sort((a, b) => new Date(b) - new Date(a));

    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`;

    // 마지막 작성일이 오늘이나 어제가 아니면 Streak은 0
    if (writtenDates[0] !== todayStr && writtenDates[0] !== yesterdayStr) {
      return 0;
    }

    let streak = 0;
    let checkDate = new Date(writtenDates[0]);

    for (let i = 0; i < writtenDates.length; i++) {
      const curDateStr = `${checkDate.getFullYear()}-${String(checkDate.getMonth() + 1).padStart(2, '0')}-${String(checkDate.getDate()).padStart(2, '0')}`;
      if (writtenDates.includes(curDateStr)) {
        streak++;
        // 하루 전으로 날짜를 돌려서 체크
        checkDate.setDate(checkDate.getDate() - 1);
      } else {
        break;
      }
    }
    return streak;
  };

  const streak = calculateStreak();

  // 감정 비율 계산
  const getEmotionRatios = () => {
    if (journals.length === 0) return {};
    const counts = {};
    journals.forEach(j => {
      counts[j.emotion] = (counts[j.emotion] || 0) + 1;
    });

    const ratios = {};
    Object.keys(counts).forEach(key => {
      ratios[key] = Math.round((counts[key] / journals.length) * 100);
    });
    return ratios;
  };

  const emotionRatios = getEmotionRatios();

  // 달력 렌더링 헬퍼
  const getDaysInMonth = (year, month) => new Date(year, month + 1, 0).getDate();
  const getFirstDayOfMonth = (year, month) => new Date(year, month, 1).getDay();

  const handlePrevMonth = () => {
    setCurrentDate(prev => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(prev => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  };

  const renderCalendar = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const totalDays = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);
    
    const calendarCells = [];
    
    // 1. 첫째 주 빈칸 채우기 (이전 달 날짜들)
    for (let i = 0; i < firstDay; i++) {
      calendarCells.push(<div key={`empty-${i}`} className="calendar-cell empty" style={{ opacity: 0.15, cursor: 'default' }}></div>);
    }

    // 2. 이번 달 날짜들 채우기
    for (let day = 1; day <= totalDays; day++) {
      // 해당 날짜에 작성된 일기 찾기
      const targetDateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const dayJournals = journals.filter(j => {
        const jd = new Date(j.created_at);
        const jdStr = `${jd.getFullYear()}-${String(jd.getMonth() + 1).padStart(2, '0')}-${String(jd.getDate()).padStart(2, '0')}`;
        return jdStr === targetDateStr;
      });

      const hasJournal = dayJournals.length > 0;
      const primaryJournal = dayJournals[0]; // 그날의 대표 일기
      const emotionMeta = primaryJournal ? EMOTION_COLORS[primaryJournal.emotion] : null;

      calendarCells.push(
        <div 
          key={`day-${day}`} 
          className={`calendar-cell ${hasJournal ? 'has-journal' : ''}`}
          style={{
            position: 'relative',
            background: hasJournal ? emotionMeta.bg : 'rgba(255, 255, 255, 0.02)',
            border: hasJournal ? `1px solid ${emotionMeta.color}35` : '1px solid rgba(255, 255, 255, 0.03)',
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
          onClick={() => {
            if (hasJournal) {
              setSelectedJournal(primaryJournal);
            } else {
              if (onNewJournalWithDate) {
                onNewJournalWithDate(targetDateStr);
              }
            }
          }}
          title={hasJournal ? `${primaryJournal.title} (클릭하여 읽기)` : `${targetDateStr} 일기 쓰기`}
          onMouseEnter={e => {
            e.currentTarget.style.transform = 'scale(1.05)';
            if (hasJournal) {
              e.currentTarget.style.borderColor = emotionMeta.color;
            } else {
              e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)';
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
            }
          }}
          onMouseLeave={e => {
            e.currentTarget.style.transform = 'none';
            if (hasJournal) {
              e.currentTarget.style.borderColor = `${emotionMeta.color}35`;
            } else {
              e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.03)';
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)';
            }
          }}
        >
          <span className="calendar-day-num" style={{ fontSize: '0.85rem', fontWeight: '500', color: hasJournal ? '#ffffff' : 'var(--text-muted)' }}>
            {day}
          </span>
          {hasJournal && (
            <div className="calendar-emotion-emoji" style={{
              fontSize: '1.25rem',
              marginTop: '4px',
              textAlign: 'center'
            }}>
              {emotionMeta.emoji}
            </div>
          )}
        </div>
      );
    }

    return calendarCells;
  };

  const formatDate = (dateString) => {
    const d = new Date(dateString);
    return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '15px' }}>
        <Loader2 className="animate-spin" size={36} color="var(--accent-primary)" />
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>저널링 대시보드를 구성하는 중...</p>
      </div>
    );
  }

  return (
    <div className="dashboard-container" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '24px',
      height: '100%',
      overflowY: 'auto',
      padding: '10px 5px',
      scrollbarWidth: 'thin'
    }}>
      
      {/* 1. 상단 환영 메세지 및 주요 통계 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px' }}>
        
        {/* Streak 카드 */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '18px', background: 'rgba(99, 102, 241, 0.05)', border: '1px solid rgba(99, 102, 241, 0.15)' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'rgba(99,102,241,0.15)', display: 'flex', alignItems: 'center', justifySelf: 'center', justifyContent: 'center', color: 'var(--accent-primary)' }}>
            <Award size={24} />
          </div>
          <div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '500' }}>연속 저널링 기록</p>
            <h3 style={{ fontSize: '1.6rem', fontWeight: '700', marginTop: '2px' }}>
              {streak} <span style={{ fontSize: '0.95rem', fontWeight: '500', color: 'var(--text-muted)' }}>일 연속</span>
            </h3>
          </div>
        </div>

        {/* 누적 일기 카드 */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '18px' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifySelf: 'center', justifyContent: 'center', color: 'var(--text-main)' }}>
            <BookOpen size={22} />
          </div>
          <div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '500' }}>나의 성찰 일기</p>
            <h3 style={{ fontSize: '1.6rem', fontWeight: '700', marginTop: '2px' }}>
              {journals.length} <span style={{ fontSize: '0.95rem', fontWeight: '500', color: 'var(--text-muted)' }}>편 작성</span>
            </h3>
          </div>
        </div>

        {/* 가치 별자리 카드 */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '18px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.15)' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifySelf: 'center', justifyContent: 'center', color: 'var(--accent-secondary)' }}>
            <Globe size={22} />
          </div>
          <div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '500' }}>성찰 가치 노드</p>
            <h3 style={{ fontSize: '1.6rem', fontWeight: '700', marginTop: '2px' }}>
              {valueCardsCount} <span style={{ fontSize: '0.95rem', fontWeight: '500', color: 'var(--text-muted)' }}>개 활성화</span>
            </h3>
          </div>
        </div>

      </div>

      {/* 2. 메인 바디: 달력 & 감정 통계 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 2fr) minmax(240px, 1fr))', gap: '20px', alignItems: 'start' }}>
        
        {/* 좌측: 감정 캘린더 */}
        <div className="glass-panel" style={{ padding: '24px', flex: 2 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Calendar size={18} color="var(--accent-primary)" />
              <h2 style={{ fontSize: '1.05rem', fontWeight: '600' }}>나의 감정 성찰 달력</h2>
            </div>
            
            {/* 달 변경 버튼 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button onClick={handlePrevMonth} style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-glass)', borderRadius: '8px', width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#ffffff' }}>
                <ChevronLeft size={16} />
              </button>
              <span style={{ fontSize: '0.9rem', fontWeight: '600', minWidth: '85px', textAlign: 'center' }}>
                {currentDate.getFullYear()}년 {currentDate.getMonth() + 1}월
              </span>
              <button onClick={handleNextMonth} style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-glass)', borderRadius: '8px', width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#ffffff' }}>
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          {/* 달력 그리드 */}
          <div className="calendar-grid" style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: '8px',
          }}>
            {/* 요일 헤더 */}
            {['일', '월', '화', '수', '목', '금', '토'].map((w, idx) => (
              <div key={idx} style={{
                textAlign: 'center',
                fontSize: '0.72rem',
                fontWeight: '600',
                color: idx === 0 ? '#ef4444' : idx === 6 ? '#3b82f6' : 'var(--text-muted)',
                paddingBottom: '8px',
              }}>
                {w}
              </div>
            ))}
            
            {/* 날짜 셀들 */}
            {renderCalendar()}
          </div>
          
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '16px', justifyContent: 'center', borderTop: '1px solid var(--border-glass)', paddingTop: '14px' }}>
            {Object.keys(EMOTION_COLORS).map(key => {
              const meta = EMOTION_COLORS[key];
              return (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: meta.color }}></span>
                  <span>{meta.emoji} {meta.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 우측: 감정 분포 통계 */}
        <div className="glass-panel" style={{ padding: '24px', flex: 1, display: 'flex', flexDirection: 'column', gap: '20px', height: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} color="var(--accent-secondary)" />
            <h2 style={{ fontSize: '1.05rem', fontWeight: '600' }}>이달의 마음 온도 비율</h2>
          </div>

          {journals.length === 0 ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '180px', color: 'var(--text-muted)', fontSize: '0.82rem', textAlign: 'center' }}>
              일기를 작성하시면<br/>감정 통계 분석이 활성화됩니다.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', flex: 1 }}>
              {Object.keys(EMOTION_COLORS).map(key => {
                const meta = EMOTION_COLORS[key];
                const ratio = emotionRatios[key] || 0;
                
                return (
                  <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem' }}>
                      <span style={{ fontWeight: '500', color: 'var(--text-main)' }}>
                        {meta.emoji} {meta.label}
                      </span>
                      <span style={{ fontWeight: '700', color: meta.color }}>{ratio}%</span>
                    </div>
                    {/* 진행률 바 */}
                    <div style={{ height: '6px', background: 'rgba(255,255,255,0.04)', borderRadius: '10px', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${ratio}%`,
                        background: meta.color,
                        borderRadius: '10px',
                        transition: 'width 0.5s ease'
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>

      {/* 3. 최근 일기 피드 리스트 */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={18} color="var(--accent-primary)" />
            <h2 style={{ fontSize: '1.05rem', fontWeight: '600' }}>최근 작성한 성찰 일기</h2>
          </div>
          <button 
            onClick={() => onNewJournalWithDate ? onNewJournalWithDate() : onNavigateToMode('editor')}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent-primary)',
              fontSize: '0.78rem',
              fontWeight: '600',
              cursor: 'pointer',
            }}
          >
            + 새 일기 쓰기
          </button>
        </div>

        {journals.length === 0 ? (
          <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: '0.88rem', marginBottom: '12px' }}>기록된 일기가 아직 없습니다.</p>
            <button 
              onClick={() => onNewJournalWithDate ? onNewJournalWithDate() : onNavigateToMode('editor')}
              style={{
                background: 'var(--accent-gradient)',
                border: 'none',
                borderRadius: '20px',
                padding: '6px 16px',
                color: '#ffffff',
                fontWeight: '600',
                fontSize: '0.78rem',
                cursor: 'pointer'
              }}
            >
              첫 일기 작성하기
            </button>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
            {journals.slice(0, 3).map((journal) => {
              const meta = EMOTION_COLORS[journal.emotion] || EMOTION_COLORS.happy;
              return (
                <div 
                  key={journal.id}
                  className="source-card-v2"
                  style={{
                    background: 'rgba(12, 14, 28, 0.4)',
                    border: '1px solid rgba(255,255,255,0.05)',
                    borderRadius: '16px',
                    padding: '16px',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: '130px'
                  }}
                  onClick={() => setSelectedJournal(journal)}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: '500' }}>
                        {formatDate(journal.created_at)}
                      </span>
                      <span style={{ fontSize: '1rem' }}>{meta.emoji}</span>
                    </div>
                    <h4 style={{ fontSize: '0.88rem', fontWeight: '700', marginBottom: '6px', color: '#ffffff' }}>
                      {journal.title}
                    </h4>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.45', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                      {journal.content}
                    </p>
                  </div>
                  <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.7rem', color: 'var(--accent-primary)', fontWeight: '600' }}>
                    <BookOpen size={10} />
                    <span>성찰 본문 읽기</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. 일기 본문 읽기 및 RAG 활성화 팝업 모달 */}
      {selectedJournal && createPortal(
        <div
          style={{
            position: 'fixed',
            top: 0, left: 0, width: '100vw', height: '100vh',
            background: 'rgba(5, 5, 15, 0.85)',
            backdropFilter: 'blur(10px)',
            zIndex: 9000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
          onClick={() => setSelectedJournal(null)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '560px',
              maxHeight: '85vh',
              background: 'rgba(12, 14, 28, 0.98)',
              border: `1px solid ${EMOTION_COLORS[selectedJournal.emotion]?.color || 'var(--accent-primary)'}30`,
              borderRadius: '24px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
            onClick={e => e.stopPropagation()}
          >
            {/* 탑 컬러 바 */}
            <div style={{
              height: '4px',
              background: EMOTION_COLORS[selectedJournal.emotion]?.color || 'var(--accent-primary)',
              flexShrink: 0
            }} />
            
            {/* 헤더 */}
            <div style={{ padding: '24px 24px 16px', borderBottom: '1px solid var(--border-glass)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', fontWeight: '500' }}>
                  {formatDate(selectedJournal.created_at)} 저널 기록
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: '#ffffff' }}>
                    {selectedJournal.title}
                  </h3>
                  <span style={{ fontSize: '1.2rem' }}>
                    {EMOTION_COLORS[selectedJournal.emotion]?.emoji}
                  </span>
                </div>
              </div>
              <button 
                onClick={() => setSelectedJournal(null)}
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: 'none',
                  borderRadius: '50%',
                  width: '28px',
                  height: '28px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  color: 'var(--text-muted)'
                }}
              >
                <X size={14} />
              </button>
            </div>

            {/* 본문 콘텐츠 */}
            <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
              <p style={{
                fontSize: '0.9rem',
                lineHeight: '1.75',
                color: '#e2e8f0',
                whiteSpace: 'pre-wrap',
                margin: 0
              }}>
                {selectedJournal.content}
              </p>
            </div>

            {/* 푸터 액션 */}
            <div style={{
              padding: '16px 24px',
              borderTop: '1px solid var(--border-glass)',
              background: 'rgba(255,255,255,0.01)',
              display: 'flex',
              gap: '12px',
              justifyContent: 'flex-end'
            }}>
              <button 
                onClick={() => setSelectedJournal(null)}
                style={{
                  background: 'none',
                  border: '1px solid var(--border-glass)',
                  borderRadius: '100px',
                  padding: '8px 18px',
                  color: 'var(--text-muted)',
                  fontSize: '0.82rem',
                  fontWeight: '600',
                  cursor: 'pointer'
                }}
              >
                닫기
              </button>
              
              {/* RAG 성찰 세션 활성화 */}
              <button 
                onClick={() => {
                  onSelectJournal(selectedJournal);
                  setSelectedJournal(null);
                }}
                style={{
                  background: 'var(--accent-gradient)',
                  border: 'none',
                  borderRadius: '100px',
                  padding: '8px 20px',
                  color: '#ffffff',
                  fontSize: '0.82rem',
                  fontWeight: '700',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)'
                }}
              >
                <MessageSquare size={14} />
                <span>AI 성찰 분석실 개시</span>
              </button>
            </div>

          </div>
        </div>,
        document.body
      )}

    </div>
  );
};

// SVG 닫기 아이콘 유틸
const X = ({ size = 16, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
  </svg>
);

export default Dashboard;
