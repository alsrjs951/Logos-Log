import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import MessageInput from './MessageInput';
import SourceCards from './SourceCards';
import ValueCardModal from './ValueCardModal';
import { Bot, User } from 'lucide-react';

const ChatWindow = ({ initialJournal, onClearInitialJournal, onNavigateToNetwork }) => {
  const [messages, setMessages] = useState([
    { role: 'bot', content: '안녕하세요! 저는 심리학 논문을 기반으로 답변해 드리는 Logos-Log AI입니다. 왼쪽 메뉴에서 일기를 쓰거나 바로 질문을 입력하여 대화를 나누어보세요.', sources: [] }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const messagesEndRef = useRef(null);
  
  // 중복 실행 및 스트림 레이스 컨디션을 방지하기 위한 Ref 추가
  const processedJournalIdRef = useRef(null);
  const abortControllerRef = useRef(null);

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

  // initialJournal이 넘어오면 채팅창을 비우고 자동으로 일기 RAG 분석을 시작합니다.
  useEffect(() => {
    if (initialJournal) {
      // 이미 같은 일기 ID로 분석 요청을 보냈다면 중복 처리 방지
      if (processedJournalIdRef.current === initialJournal.id) {
        return;
      }
      processedJournalIdRef.current = initialJournal.id;

      // 성찰 완료된 일기 ID를 localStorage에 등록 및 커스텀 이벤트 전송
      try {
        const analyzedIds = JSON.parse(localStorage.getItem('analyzed_journal_ids') || '[]');
        if (!analyzedIds.includes(initialJournal.id)) {
          analyzedIds.push(initialJournal.id);
          localStorage.setItem('analyzed_journal_ids', JSON.stringify(analyzedIds));
          // 사이드바 일기 목록 리프레시를 위해 전역 이벤트 트리거
          window.dispatchEvent(new CustomEvent('journal_analyzed', { detail: initialJournal.id }));
        }
      } catch (e) {
        console.error("LocalStorage write error:", e);
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
      handleSendMessage(queryText, true);
      
      if (onClearInitialJournal) {
        onClearInitialJournal();
      }
    }
  }, [initialJournal]);

  const handleSendMessage = async (query, isJournalOverride = false) => {
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

    // 이전 대화 맥락 추출 (일기 분석 요청이면 히스토리 없이 전송)
    const historyData = isJournalOverride 
      ? [] 
      : messages
          .filter(msg => msg.content !== '')
          .slice(1) // 첫 인사말 제외
          .map(msg => ({ role: msg.role, content: msg.content }))
          .slice(-10);

    try {
      // 3. 백엔드 API (SSE) 호출
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal, // AbortController 신호 바인딩
        body: JSON.stringify({ 
          query, 
          history: historyData,
          is_journal: isJournalOverride
        })
      });

      if (!response.body) throw new Error('ReadableStream not supported.');

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
                console.error("JSON Parse Error:", e, dataStr);
              }
            }
          }
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        // 이전 비동기 요청 취소 시에는 에러 화면 처리 없이 조용히 무시함
        console.log("Previous request aborted.");
        return;
      }
      console.error('Error fetching chat:', error);
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1].content = "서버와 통신하는 중 오류가 발생했습니다. 백엔드 서버가 실행 중인지 확인해주세요.";
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

  return (
    <>
      <div className="chat-window-header">
        <span className="chat-status-indicator">
          {isLoading ? '● AI 분석가 답변 입력 중...' : '● 성찰 세션 활성화'}
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
            
            <div className="message-bubble">
              <ReactMarkdown>{msg.content}</ReactMarkdown>
              {msg.sources && msg.sources.length > 0 && (
                <SourceCards sources={msg.sources} />
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
            <div className="message-bubble typing-indicator-container" style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '14px 20px' }}>
              <div className="typing-stage-text" style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Loader2 className="animate-spin" size={14} color="var(--accent-secondary)" />
                {loadingStage || '성찰 대화를 분석하는 중...'}
              </div>
              <div className="typing-indicator" style={{ alignSelf: 'flex-start', margin: 0 }}>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <MessageInput onSendMessage={handleSendMessage} isLoading={isLoading} />

      {isModalOpen && (
        <ValueCardModal 
          messages={messages} 
          onClose={() => setIsModalOpen(false)} 
          onNavigateToNetwork={onNavigateToNetwork}
        />
      )}
    </>
  );
};

export default ChatWindow;
