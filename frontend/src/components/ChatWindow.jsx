import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import ReactMarkdown from 'react-markdown';
import MessageInput from './MessageInput';
import SourceCards from './SourceCards';
import ValueCardModal from './ValueCardModal';
import { Bot, User, Heart, Phone } from 'lucide-react';
import { fetchWithAuth } from '../api';
import { apiResponseError, responseJsonOrNull } from '../utils/apiErrors';
import { addAnalyzedJournalId, hasAnalyzedJournalId } from '../utils/analyzedJournals';

// 자해/자살 위기 감지 시 노출되는 검증된 전문 상담 핫라인 (단일 소스)
const CRISIS_RESOURCES = [
  { name: '자살예방 상담전화', phone: '1393', desc: '24시간 연중무휴' },
  { name: '정신건강 상담전화', phone: '1577-0199', desc: '24시간' },
  { name: '생명의전화', phone: '1588-9191', desc: '24시간' },
];

// 위기 신호 감지 시 답변 상단에 노출되는 안심 안내 + 상담 핫라인 배너
const CrisisBanner = () => (
  <div style={{
    margin: '0 0 14px',
    padding: '14px 16px',
    background: 'rgba(244, 63, 94, 0.08)',
    border: '1px solid rgba(244, 63, 94, 0.35)',
    borderRadius: '12px',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
      <Heart size={16} color="#fb7185" />
      <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#fb7185' }}>
        지금 많이 힘드시다면, 혼자 견디지 않으셔도 됩니다
      </span>
    </div>
    <p style={{ fontSize: '0.78rem', lineHeight: 1.55, color: 'var(--text-main)', margin: '0 0 12px' }}>
      당신의 안전이 무엇보다 소중합니다. 아래 전문 상담 기관이 24시간 당신의 이야기를 기다리고 있어요.
      지금 마음이 너무 무겁다면 잠시 전화로 도움을 받아보시는 건 어떨까요?
    </p>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {CRISIS_RESOURCES.map((r) => (
        <a
          key={r.phone}
          href={`tel:${r.phone.replace(/-/g, '')}`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            background: 'rgba(244, 63, 94, 0.06)',
            border: '1px solid rgba(244, 63, 94, 0.22)',
            borderRadius: '8px',
            textDecoration: 'none',
          }}
        >
          <Phone size={14} color="#fb7185" />
          <span style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--text-main)' }}>{r.name}</span>
          <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#fb7185' }}>{r.phone}</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>{r.desc}</span>
        </a>
      ))}
    </div>
  </div>
);

// 일반 대괄호 숫자[N] 또는 [논문 N] 텍스트를 인라인 마크다운 앵커 링크로 전처리하는 가드 헬퍼
const preprocessCitations = (text) => {
  if (!text) return '';
  // 1) "[논문 N]" 또는 "[논문N]" -> "[N](#source-N)"
  let formatted = text.replace(/\[논문\s*(\d+)\]/g, '[$1](#source-$1)');
  // 2) "[N]" (뒤에 마크다운 앵커 괄호가 붙지 않은 단독 대괄호 숫자) -> "[N](#source-N)"
  formatted = formatted.replace(/\[(\d+)\](?!\(#source-\d+\))/g, '[$1](#source-$1)');
  return formatted;
};

// 2단계 근거 발췌 요약 팝오버를 관리하는 개별 인라인 텍스트 컴포넌트
const CitationBadge = ({ href, sources, msgIndex }) => {
  const [showPopover, setShowPopover] = useState(false);
  const [popoverPosition, setPopoverPosition] = useState(null);
  const wrapperRef = useRef(null);
  const popoverRef = useRef(null);
  const closeTimerRef = useRef(null);

  const sourceIndex = parseInt(href.replace('#source-', ''));
  const source = sources && sources[sourceIndex - 1];

  const rawAuthor = source?.author || '';
  const authorText = rawAuthor.length > 12 
    ? rawAuthor.substring(0, 12) + '...' 
    : rawAuthor;

  const citationLabel = `[${sourceIndex}]`;
  const sourceTitle = String(source?.title || source?.filename || '').replace(/\s+/g, ' ').trim();
  const locationParts = [];
  if (source?.section) locationParts.push(source.section);
  if (source?.page_start && source?.page_end && source.page_start !== source.page_end) {
    locationParts.push(`p. ${source.page_start}-${source.page_end}`);
  } else if (source?.page_start) {
    locationParts.push(`p. ${source.page_start}`);
  }
  const locationLabel = locationParts.join(' · ');

  const updatePopoverPosition = () => {
    const trigger = wrapperRef.current;
    if (!trigger) return;

    const rect = trigger.getBoundingClientRect();
    const viewportPadding = 16;
    const width = Math.min(320, Math.max(240, window.innerWidth - viewportPadding * 2));
    const centerX = rect.left + rect.width / 2;
    const left = Math.min(
      Math.max(viewportPadding, centerX - width / 2),
      window.innerWidth - width - viewportPadding
    );
    const spaceAbove = rect.top;
    const spaceBelow = window.innerHeight - rect.bottom;
    const placement = spaceAbove > spaceBelow && spaceAbove > 180 ? 'top' : 'bottom';
    const availableHeight = placement === 'top'
      ? Math.max(140, rect.top - viewportPadding * 2)
      : Math.max(140, window.innerHeight - rect.bottom - viewportPadding * 2);

    setPopoverPosition({
      left,
      width,
      top: placement === 'top' ? rect.top - 12 : rect.bottom + 12,
      placement,
      arrowX: Math.min(Math.max(18, centerX - left), width - 18),
      maxHeight: Math.min(360, availableHeight),
    });
  };

  const openPopover = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
    }
    updatePopoverPosition();
    setShowPopover(true);
  };

  const scheduleClosePopover = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
    }
    closeTimerRef.current = setTimeout(() => {
      setShowPopover(false);
    }, 140);
  };

  const handleCitationClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    updatePopoverPosition();
    setShowPopover(prev => !prev);
  };

  const handleOpenDetail = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setShowPopover(false);
    
    const el = document.getElementById(`source-card-${msgIndex}-${sourceIndex}`);
    if (el) {
      el.click();
    }
  };

  const summaryText = source?.summary_ko
    ? source.summary_ko 
    : (source?.content_ko || source?.content || '').slice(0, 85) + '...';

  useEffect(() => {
    if (!showPopover) return;

    updatePopoverPosition();
    window.addEventListener('resize', updatePopoverPosition);
    window.addEventListener('scroll', updatePopoverPosition, true);

    return () => {
      window.removeEventListener('resize', updatePopoverPosition);
      window.removeEventListener('scroll', updatePopoverPosition, true);
    };
  }, [showPopover]);

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  if (!source) return <span>[{sourceIndex}]</span>;

  return (
    <span 
      ref={wrapperRef}
      className="inline-citation-text-wrapper"
      style={{ position: 'relative', display: 'inline-block' }}
      onMouseEnter={openPopover}
      onMouseLeave={scheduleClosePopover}
    >
      <span 
        className={`inline-citation-text ${showPopover ? 'highlighted' : ''}`}
        title="마우스를 올리거나 클릭하여 근거 발췌 요약 보기"
        style={{
          cursor: 'pointer',
          color: '#818cf8',
          margin: '0 2px',
          padding: '0 2px',
          fontSize: '0.92em',
          fontWeight: '600',
          transition: 'all 0.15s ease-in-out',
          userSelect: 'none',
          display: 'inline',
          borderRadius: '2px',
          backgroundColor: showPopover ? 'rgba(253, 224, 71, 0.35)' : 'transparent',
        }}
        onClick={handleCitationClick}
      >
        {citationLabel}
      </span>

      {showPopover && popoverPosition && createPortal(
        <div
          ref={popoverRef}
          className="citation-popover"
          style={{
            position: 'fixed',
            top: `${popoverPosition.top}px`,
            left: `${popoverPosition.left}px`,
            transform: popoverPosition.placement === 'top' ? 'translateY(-100%)' : 'none',
            width: `${popoverPosition.width}px`,
            maxHeight: `${popoverPosition.maxHeight}px`,
            background: 'rgba(12, 14, 28, 0.98)',
            border: '1px solid rgba(99, 102, 241, 0.45)',
            borderRadius: '12px',
            padding: '12px 14px',
            boxShadow: '0 12px 30px rgba(0, 0, 0, 0.65), 0 0 15px rgba(99, 102, 241, 0.2)',
            zIndex: 99999,
            textAlign: 'left',
            fontStyle: 'normal',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            pointerEvents: 'auto',
            backdropFilter: 'blur(10px)',
            overflowY: 'auto',
          }}
          onClick={e => e.stopPropagation()}
          onMouseEnter={openPopover}
          onMouseLeave={scheduleClosePopover}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{
              fontSize: '0.66rem',
              fontWeight: '800',
              color: 'rgba(255,255,255,0.4)',
              letterSpacing: '0.5px'
            }}>
              [근거 발췌 {sourceIndex}]
            </span>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: '700',
              color: '#818cf8',
            }}>
              {authorText} ({source.year || '연도 미상'})
            </span>
          </div>

          <p style={{
            fontSize: '0.78rem',
            lineHeight: '1.45',
            color: 'var(--text-main)',
            margin: 0,
            fontWeight: '500',
            overflowWrap: 'anywhere',
            wordBreak: 'keep-all',
          }}>
            {summaryText}
          </p>

          {(sourceTitle || locationLabel) && (
            <div style={{
              padding: '8px 10px',
              background: 'rgba(255,255,255,0.035)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: '8px',
            }}>
              {sourceTitle && (
                <p style={{
                  fontSize: '0.68rem',
                  lineHeight: 1.4,
                  color: 'var(--text-main)',
                  fontWeight: 650,
                  margin: 0,
                }}>
                  {sourceTitle.length > 92 ? `${sourceTitle.slice(0, 92).trim()}…` : sourceTitle}
                </p>
              )}
              {locationLabel && (
                <p style={{
                  fontSize: '0.65rem',
                  lineHeight: 1.35,
                  color: '#a5b4fc',
                  fontWeight: 700,
                  margin: sourceTitle ? '4px 0 0' : 0,
                }}>
                  {locationLabel}
                </p>
              )}
            </div>
          )}

          <button
            onClick={handleOpenDetail}
            style={{
              marginTop: '4px',
              background: 'rgba(99, 102, 241, 0.12)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: '6px',
              padding: '5px 0',
              fontSize: '0.72rem',
              fontWeight: '700',
              color: '#a5b4fc',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              transition: 'all 0.2s',
              width: '100%',
              lineHeight: 1.35,
              whiteSpace: 'normal',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(99, 102, 241, 0.25)';
              e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.6)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'rgba(99, 102, 241, 0.12)';
              e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.3)';
            }}
          >
            <span>근거 발췌와 출처 정보 보기 ➜</span>
          </button>

          <div style={{
            position: 'absolute',
            top: popoverPosition.placement === 'top' ? '100%' : 'auto',
            bottom: popoverPosition.placement === 'bottom' ? '100%' : 'auto',
            left: `${popoverPosition.arrowX}px`,
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '7px solid transparent',
            borderRight: '7px solid transparent',
            borderTop: popoverPosition.placement === 'top' ? '7px solid rgba(99, 102, 241, 0.45)' : 'none',
            borderBottom: popoverPosition.placement === 'bottom' ? '7px solid rgba(99, 102, 241, 0.45)' : 'none',
          }} />
          <div style={{
            position: 'absolute',
            top: popoverPosition.placement === 'top' ? '99%' : 'auto',
            bottom: popoverPosition.placement === 'bottom' ? '99%' : 'auto',
            left: `${popoverPosition.arrowX}px`,
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '6px solid transparent',
            borderRight: '6px solid transparent',
            borderTop: popoverPosition.placement === 'top' ? '6px solid rgba(12, 14, 28, 0.98)' : 'none',
            borderBottom: popoverPosition.placement === 'bottom' ? '6px solid rgba(12, 14, 28, 0.98)' : 'none',
          }} />
        </div>,
        document.body
      )}
    </span>
  );
};

const ThinkingIndicator = ({ loadingStage }) => {
  const stageText = loadingStage || '성찰 대화를 분석하는 중...';

  return (
    <div className="ai-thinking-panel">
      <div className="ai-thinking-header">
        <div className="ai-thinking-orb" aria-hidden="true">
          <Bot size={16} />
          <span className="ai-thinking-orb-ring" />
        </div>
        <div className="ai-thinking-copy">
          <span className="ai-thinking-label">AI가 답변을 만들고 있어요</span>
          <span className="ai-thinking-stage">{stageText}</span>
        </div>
        <div className="ai-thinking-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>

      <div className="ai-thinking-activity" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
        <span />
      </div>

      <div className="skeleton-container ai-thinking-lines">
        <div className="skeleton-line" style={{ width: '92%' }} />
        <div className="skeleton-line" style={{ width: '78%' }} />
        <div className="skeleton-line" style={{ width: '54%' }} />
      </div>
    </div>
  );
};

const ChatWindow = ({ token, initialJournal, onClearInitialJournal, onNavigateToNetwork }) => {
  const [messages, setMessages] = useState([
    { role: 'bot', content: '안녕하세요. Logos-Log는 오늘의 기록을 함께 살펴보고, 의미 있는 가치 카드와 다음 작은 실험으로 이어가도록 돕습니다. 일기를 선택해 성찰 대화를 시작하거나, 지금 떠오르는 고민을 바로 적어도 좋습니다.', sources: [] }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeJournalId, setActiveJournalId] = useState(null);
  const messagesEndRef = useRef(null);
  
  // 중복 실행 및 스트림 레이스 컨디션을 방지하기 위한 Ref 추가
  const processedJournalIdRef = useRef(null);
  const abortControllerRef = useRef(null);
  const handleSendMessageRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 컴포넌트 언마운트 시 진행 중인 요청 취소 클린업
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // initialJournal이 넘어오면 대화 이력이 존재하는지 먼저 조회하고, 없으면 자동으로 일기 RAG 분석을 시작합니다.
  useEffect(() => {
    if (initialJournal) {
      // 이미 같은 일기 ID로 처리 중이라면 중복 방지
      if (processedJournalIdRef.current === initialJournal.id) {
        return;
      }
      processedJournalIdRef.current = initialJournal.id;
      setActiveJournalId(initialJournal.id);

      const fetchHistoryAndStart = async () => {
        try {
          setIsLoading(true);
          setLoadingStage('🔄 과거 성찰 대화 내역을 불러오는 중...');
          
          const res = await fetchWithAuth(`/api/chat/history/${initialJournal.id}`, { token });
          if (res.ok) {
            const historyData = await responseJsonOrNull(res);
            
            if (Array.isArray(historyData) && historyData.length > 0) {
              // 대화 이력이 존재하면 저장된 대화 복원
              setMessages(historyData);
              setIsLoading(false);
              setLoadingStage('');
              
              if (onClearInitialJournal) {
                onClearInitialJournal();
              }
              return; // 이력 복원 완료했으므로 신규 분석은 진행하지 않음
            }
          }
        } catch (err) {
          console.warn("Failed to load chat history:", err);
        } finally {
          setIsLoading(false);
          setLoadingStage('');
        }

        // 대화 이력이 없는 경우에만 신규 RAG 분석 세션 실행
        if (!hasAnalyzedJournalId(initialJournal.id)) {
          addAnalyzedJournalId(initialJournal.id);
          // 사이드바 일기 목록 리프레시를 위해 전역 이벤트 트리거
          window.dispatchEvent(new CustomEvent('journal_analyzed', { detail: initialJournal.id }));
        }
        
        setMessages([]); // 기존 메시지 초기화
        
        const emotionEmojiMap = {
          happy: '😊',
          sad: '😢',
          stressed: '🤯',
          calm: '🧘',
          tired: '😴'
        };
        const emoji = emotionEmojiMap[initialJournal.emotion] || '📝';
        
        const queryText = `[일기 분석 요청]\n제목: ${initialJournal.title}\n감정 상태: ${emoji} (${initialJournal.emotion})\n본문:\n${initialJournal.content}`;
        
        // 일기 분석 API 요청 시작
        if (handleSendMessageRef.current) {
          await handleSendMessageRef.current(queryText, true, initialJournal.id);
        }
        
        if (onClearInitialJournal) {
          onClearInitialJournal();
        }
      };

      fetchHistoryAndStart();
    }
  }, [initialJournal, onClearInitialJournal, token]);

  const handleSendMessage = async (query, isJournalOverride = false, journalIdOverride = null) => {
    // 이미 진행 중인 이전 RAG 요청이 있다면 강제로 취소(Abort)하여 혼선 방지
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // 새로운 AbortController 인스턴스 생성 및 Ref 저장
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // 1. 사용자 메시지 추가 (일기 분석 요청이면 읽기 쉽게 포맷)
    const displayContent = isJournalOverride 
      ? `📖 **[일기 분석 시작]**\n\n**제목:** ${query.split('\n')[1].replace('제목: ', '')}\n**감정:** ${query.split('\n')[2].replace('감정 상태: ', '')}\n\n${query.split('\n').slice(4).join('\n')}`
      : query;

    setMessages(prev => [...prev, { role: 'user', content: displayContent }]);
    setIsLoading(true);
    setLoadingStage('🚀 AI 성찰 세션을 개시하고 있습니다...');

    // 2. 봇의 빈 메시지 추가 (스트리밍 수신용)
    setMessages(prev => [...prev, { role: 'bot', content: '', sources: [] }]);

    // 이전 대화 맥락 추출 (일기 분석 요청이면 히스토리 없이 전송, 웰컴 메시지는 필터링)
    const historyData = isJournalOverride 
      ? [] 
      : messages
          .filter(msg => msg.content !== '' && !msg.content.startsWith('안녕하세요! 저는 심리학 논문을 기반으로 답변해 드리는'))
          .map(msg => ({ role: msg.role, content: msg.content }))
          .slice(-10);

    const targetJournalId = journalIdOverride || activeJournalId;

    try {
      // 3. 백엔드 API (SSE) 호출
      const response = await fetchWithAuth('/api/chat', {
        method: 'POST',
        token,
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal, // AbortController 신호 바인딩
        body: JSON.stringify({ 
          query, 
          history: historyData,
          is_journal: isJournalOverride,
          journal_id: targetJournalId
        })
      });

      if (!response.ok) {
        throw await apiResponseError(response, '성찰 답변을 불러오지 못했습니다.');
      }

      if (!response.body) throw new Error('이 브라우저에서는 스트리밍 응답을 읽을 수 없습니다.');

      // 4. SSE 스트리밍 파싱 로직
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          // 버퍼에 누적 후 줄바꿈 기준으로 split
          buffer += decoder.decode(value, { stream: !done });
          const lines = buffer.split('\n');
          
          // 마지막 줄은 불완전한 조각일 수 있으므로 버퍼에 보관하고 lines 목록에서 제외
          buffer = lines.pop();

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (!trimmedLine) continue;

            if (trimmedLine.startsWith('data: ')) {
              const dataStr = trimmedLine.replace('data: ', '').trim();
              if (!dataStr) continue;

              try {
                const parsedData = JSON.parse(dataStr);
                
                if (parsedData.type === 'status') {
                  // RAG 단계별로 안내 메시지 설정
                  const stage = parsedData.data;
                  if (stage === 'translating') {
                    setLoadingStage('🔍 성찰 일기의 핵심 주제어 번역 및 영어 학술 키워드로 확장 중...');
                  } else if (stage === 'searching') {
                    setLoadingStage('📖 자기결정이론 및 로고테라피 관련 학술 DB에서 매칭 구절 탐색 중...');
                  } else if (stage === 'generating') {
                    setLoadingStage('✍️ 분석된 논문 통찰을 엮어 맞춤형 심리학 성찰 답변을 구성하는 중...');
                  }
                } else if (parsedData.type === 'sources') {
                  // 출처(Source) 데이터 업데이트
                  setMessages(prev => {
                    const newMessages = [...prev];
                    const lastMessage = { ...newMessages[newMessages.length - 1] };
                    lastMessage.sources = parsedData.data;
                    newMessages[newMessages.length - 1] = lastMessage;
                    return newMessages;
                  });
                } else if (parsedData.type === 'crisis') {
                  // 위기 신호 감지: 해당 답변에 상담 핫라인 배너를 노출하도록 플래그 설정
                  setMessages(prev => {
                    const newMessages = [...prev];
                    const lastMessage = { ...newMessages[newMessages.length - 1] };
                    lastMessage.crisis = true;
                    newMessages[newMessages.length - 1] = lastMessage;
                    return newMessages;
                  });
                } else if (parsedData.type === 'chunk') {
                  // 첫 텍스트가 도착하는 순간 로딩 안내 문구 클리어
                  setLoadingStage('');
                  // 타자 치듯 텍스트 이어붙이기
                  setMessages(prev => {
                    const newMessages = [...prev];
                    const lastMessage = { ...newMessages[newMessages.length - 1] };
                    lastMessage.content += parsedData.data;
                    newMessages[newMessages.length - 1] = lastMessage;
                    return newMessages;
                  });
                } else if (parsedData.type === 'done') {
                  // 완료
                  setIsLoading(false);
                  setLoadingStage('');
                }
              } catch (e) {
                console.warn("Chat stream JSON parse error:", e, dataStr);
              }
            }
          }
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        // 이전 비동기 요청 취소 시에는 에러 화면 처리 없이 조용히 무시함
        return;
      }
      console.warn('Error fetching chat:', error);
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1].content = error.message || "서버와 통신하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
        return newMessages;
      });
      setIsLoading(false);
      setLoadingStage('');
    } finally {
      // 본인이 마지막으로 할당한 컨트롤러라면 해제
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
    }
  };

  useLayoutEffect(() => {
    handleSendMessageRef.current = handleSendMessage;
  });

  return (
    <>
      <div className="chat-window-header">
        <span className={`chat-status-indicator ${isLoading ? 'is-loading' : ''}`}>
          <span className="chat-status-dot" />
          {isLoading ? '성찰 답변을 구성 중...' : '성찰 대화 활성화'}
        </span>
        {messages.length > 1 && (
          <button 
            className="archive-value-btn" 
            onClick={() => setIsModalOpen(true)}
            disabled={isLoading}
          >
            💡 가치 카드로 저장하기
          </button>
        )}
      </div>

      <div className="chat-area">
        {messages.map((msg, index) => (
          <div key={index} className={`message-row ${msg.role}`}>
            {msg.role === 'bot' && (
              <div style={{ marginRight: '10px', marginTop: '5px' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Bot size={18} color="var(--accent-secondary)" />
                </div>
              </div>
            )}
            
            <div
              className="message-bubble"
              style={msg.role === 'bot' ? { flex: 1, minWidth: 0 } : {}}
            >
              {msg.role === 'bot' && msg.crisis && <CrisisBanner />}
              <div style={{ display: 'block', width: '100%', position: 'relative' }}>
                <ReactMarkdown
                  components={{
                    a: ({ href, children }) => {
                      if (href && href.startsWith('#source-')) {
                        return (
                          <CitationBadge 
                            href={href} 
                            sources={msg.sources} 
                            msgIndex={index}
                          />
                        );
                      }
                      return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
                    }
                  }}
                >
                  {msg.role === 'bot' ? preprocessCitations(msg.content) : msg.content}
                </ReactMarkdown>
                {isLoading && index === messages.length - 1 && msg.role === 'bot' && msg.content !== '' && (
                  <span className="chat-typing-cursor"></span>
                )}
              </div>

              {/* 학술 근거 안내 배너 */}
              {msg.sources && msg.sources.length > 0 && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  margin: '12px 0 6px',
                  padding: '8px 12px',
                  background: 'rgba(16, 185, 129, 0.05)',
                  border: '1px solid rgba(16, 185, 129, 0.18)',
                  borderRadius: '8px',
                  width: 'fit-content'
                }}>
                  <span style={{ 
                    display: 'inline-block', 
                    width: '6px', 
                    height: '6px', 
                    borderRadius: '50%', 
                    background: '#10b981',
                  }}></span>
                  <span style={{ fontSize: '0.68rem', fontWeight: '700', color: '#10b981', letterSpacing: '0.2px' }}>
                    검색된 연구 발췌 {msg.sources.length}건을 근거로 답변을 구성했습니다
                  </span>
                </div>
              )}

              {msg.sources && msg.sources.length > 0 && (
                <SourceCards sources={msg.sources} msgIndex={index} />
              )}
            </div>

            {msg.role === 'user' && (
              <div style={{ marginLeft: '10px', marginTop: '5px' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--accent-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <User size={18} color="white" />
                </div>
              </div>
            )}
          </div>
        ))}

        {isLoading && messages[messages.length - 1].role === 'user' && (
          <div className="message-row bot">
             <div style={{ marginRight: '10px', marginTop: '5px' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Bot size={18} color="var(--accent-secondary)" />
                </div>
              </div>
            <div className="message-bubble typing-indicator-container" style={{ flex: 1, minWidth: 0 }}>
              <ThinkingIndicator loadingStage={loadingStage} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <MessageInput onSendMessage={handleSendMessage} isLoading={isLoading} />

      {isModalOpen && (
        <ValueCardModal 
          token={token}
          messages={messages} 
          onClose={() => setIsModalOpen(false)} 
          onNavigateToNetwork={onNavigateToNetwork}
          emotion={initialJournal?.emotion || null}
        />
      )}
    </>
  );
};

export default ChatWindow;
