import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Sparkles } from 'lucide-react';

const EMOTIONS = [
  { key: 'happy', label: '행복', emoji: '😊' },
  { key: 'sad', label: '슬픔', emoji: '😢' },
  { key: 'stressed', label: '스트레스', emoji: '🤯' },
  { key: 'calm', label: '평온', emoji: '🧘' },
  { key: 'tired', label: '피로', emoji: '😴' }
];

// 로컬 타임존 기준 오늘 날짜 구하는 유틸리티
const getLocalDateString = () => {
  const offset = new Date().getTimezoneOffset() * 60000;
  const localISOTime = (new Date(Date.now() - offset)).toISOString();
  return localISOTime.split('T')[0];
};

const JournalEditor = ({ token, preselectedDate, onStartAnalysis, onSaveOnly }) => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [selectedEmotion, setSelectedEmotion] = useState('calm');
  const [selectedDate, setSelectedDate] = useState(preselectedDate || getLocalDateString());
  const [isSaving, setIsSaving] = useState(false);
  const [savedJournalData, setSavedJournalData] = useState(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);

  // 외부(예: 대시보드 캘린더 클릭)에서 주입된 preselectedDate가 변경될 때 selectedDate 상태 업데이트
  useEffect(() => {
    if (preselectedDate) {
      setSelectedDate(preselectedDate);
    } else {
      setSelectedDate(getLocalDateString());
    }
  }, [preselectedDate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim() || !content.trim() || !selectedDate) return;

    setIsSaving(true);
    try {
      // 선택된 로컬 날짜 문자열을 ISO 시간 타임스탬프로 결합
      const isoDateTime = new Date(`${selectedDate}T12:00:00`).toISOString();

      // 1. 일기를 Supabase 백엔드에 저장 (인증 토큰 동반)
      const response = await fetch('http://localhost:8000/api/journals', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          title: title.trim(),
          content: content.trim(),
          emotion: selectedEmotion,
          created_at: isoDateTime
        })
      });

      if (!response.ok) {
        throw new Error('일기 저장 실패');
      }

      const savedJournal = await response.json();
      setSavedJournalData(savedJournal);
      setShowSuccessModal(true);
      
      // 에디터 초기화
      setTitle('');
      setContent('');
      setSelectedEmotion('calm');
      setSelectedDate(getLocalDateString());
    } catch (error) {
      console.error('Error saving journal:', error);
      alert('일기를 저장하는 도중 오류가 발생했습니다. 백엔드가 켜져 있는지 확인하세요.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <>
      <form className="editor-container" onSubmit={handleSubmit}>
        
        {/* 제목 및 날짜 가로 정렬 레이아웃 */}
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', width: '100%', marginBottom: '6px' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <span className="emotion-selector-label" style={{ marginBottom: '6px', display: 'block' }}>하루의 한 줄 제목</span>
            <input
              type="text"
              className="editor-title-input"
              placeholder="오늘 하루의 제목을 붙여보세요..."
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isSaving}
              style={{ width: '100%', height: '42px', margin: 0 }}
              required
            />
          </div>
          
          <div style={{ width: '170px' }}>
            <span className="emotion-selector-label" style={{ marginBottom: '6px', display: 'block' }}>성찰 일자</span>
            <input 
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              disabled={isSaving}
              style={{
                background: 'rgba(10, 11, 26, 0.4)',
                border: '1px solid var(--border-glass)',
                borderRadius: '14px',
                padding: '10px 14px',
                color: '#ffffff',
                fontSize: '0.88rem',
                fontFamily: 'inherit',
                outline: 'none',
                cursor: 'pointer',
                width: '100%',
                height: '42px',
                boxSizing: 'border-box'
              }}
              required
            />
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <span className="emotion-selector-label">오늘의 핵심 감정</span>
          <div className="emotion-buttons">
            {EMOTIONS.map((emo) => (
              <button
                key={emo.key}
                type="button"
                className={`emotion-btn ${selectedEmotion === emo.key ? 'active' : ''}`}
                onClick={() => setSelectedEmotion(emo.key)}
                disabled={isSaving}
              >
                <span>{emo.emoji}</span>
                <span>{emo.label}</span>
              </button>
            ))}
          </div>
        </div>

        <textarea
          className="editor-content-textarea"
          placeholder="오늘 있었던 일이나 떠오르는 생각, 느꼈던 감정을 편안하게 적어보세요. 저장 완료 후 AI와 자아 성찰을 위한 실존 상담 대화를 개시할 수 있습니다..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={isSaving}
          required
        />

        <button
          type="submit"
          className="editor-submit-btn"
          disabled={isSaving || !title.trim() || !content.trim()}
        >
          <Sparkles size={18} />
          {isSaving ? '일기 저장 및 분석 준비 중...' : '일기 저장하고 성찰 시작하기'}
        </button>
      </form>

      {/* 일기 저장 성공 팝업 모달 */}
      {showSuccessModal && createPortal(
        <div style={{
          position: 'fixed',
          top: 0, left: 0, width: '100vw', height: '100vh',
          background: 'rgba(5, 5, 15, 0.85)',
          backdropFilter: 'blur(12px)',
          zIndex: 10000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px'
        }}>
          <div className="glass-panel" style={{
            width: '100%',
            maxWidth: '440px',
            background: 'rgba(12, 14, 28, 0.98)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '24px',
            padding: '28px',
            textAlign: 'center',
            boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
            animation: 'fadeIn 0.3s ease-out'
          }}>
            <div style={{
              width: '60px',
              height: '60px',
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 18px',
              color: '#10b981',
              fontSize: '1.5rem',
              fontWeight: '700'
            }}>
              ✦
            </div>
            
            <h3 style={{ fontSize: '1.25rem', fontWeight: '700', color: '#ffffff', marginBottom: '8px' }}>
              오늘의 일기가 밤하늘에 기록되었습니다
            </h3>
            <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '24px' }}>
              기록된 소중한 일기를 바탕으로 지금 바로 AI 심리학 분석가와 실존적 성찰 대화를 나누어보시겠습니까?
            </p>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {/* RAG 대화 바로가기 */}
              <button 
                onClick={() => {
                  setShowSuccessModal(false);
                  onStartAnalysis(savedJournalData);
                }}
                style={{
                  background: 'var(--accent-gradient)',
                  border: 'none',
                  borderRadius: '100px',
                  padding: '10px 24px',
                  color: '#ffffff',
                  fontSize: '0.85rem',
                  fontWeight: '700',
                  cursor: 'pointer',
                  boxShadow: '0 4px 15px rgba(99, 102, 241, 0.3)'
                }}
              >
                💬 즉시 AI 성찰 대화 시작
              </button>
              
              {/* 대시보드로 이동 */}
              <button 
                onClick={() => {
                  setShowSuccessModal(false);
                  onSaveOnly();
                }}
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid var(--border-glass)',
                  borderRadius: '100px',
                  padding: '10px 24px',
                  color: '#ffffff',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'background 0.2s'
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
                onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.04)'}
              >
                📅 홈 대시보드로 이동 (감정 캘린더)
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
};

export default JournalEditor;
