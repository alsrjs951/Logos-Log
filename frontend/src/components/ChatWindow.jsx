import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import MessageInput from './MessageInput';
import SourceCards from './SourceCards';
import { Bot, User } from 'lucide-react';

const ChatWindow = () => {
  const [messages, setMessages] = useState([
    { role: 'bot', content: '안녕하세요! 저는 심리학 논문을 기반으로 답변해 드리는 Logos-Log AI입니다. 무엇을 도와드릴까요?', sources: [] }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (query) => {
    // 1. 사용자 메시지 추가
    setMessages(prev => [...prev, { role: 'user', content: query }]);
    setIsLoading(true);

    // 2. 봇의 빈 메시지 추가 (여기에 스트리밍 데이터를 붙여넣을 예정)
    setMessages(prev => [...prev, { role: 'bot', content: '', sources: [] }]);

    try {
      // 3. 백엔드 API (SSE) 호출
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query })
      });

      if (!response.body) throw new Error('ReadableStream not supported.');

      // 4. SSE 스트리밍 파싱 로직
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunkString = decoder.decode(value, { stream: true });
          const lines = chunkString.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.replace('data: ', '').trim();
              if (!dataStr) continue;

              try {
                const parsedData = JSON.parse(dataStr);
                
                if (parsedData.type === 'sources') {
                  // 출처(Source) 데이터 업데이트
                  setMessages(prev => {
                    const newMessages = [...prev];
                    const lastMessage = { ...newMessages[newMessages.length - 1] };
                    lastMessage.sources = parsedData.data;
                    newMessages[newMessages.length - 1] = lastMessage;
                    return newMessages;
                  });
                } else if (parsedData.type === 'chunk') {
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
                }
              } catch (e) {
                console.error("JSON Parse Error:", e, dataStr);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Error fetching chat:', error);
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1].content = "서버와 통신하는 중 오류가 발생했습니다. 백엔드 서버가 실행 중인지 확인해주세요.";
        return newMessages;
      });
      setIsLoading(false);
    }
  };

  return (
    <>
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
            <div className="message-bubble typing-indicator">
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <MessageInput onSendMessage={handleSendMessage} isLoading={isLoading} />
    </>
  );
};

export default ChatWindow;
