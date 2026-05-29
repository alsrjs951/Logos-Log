import React, { useState, useEffect } from 'react';
import { ShieldAlert, Check, X, Loader2 } from 'lucide-react';

const ValueCardModal = ({ messages, onClose, onSaveSuccess }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [insight, setInsight] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    // 1. 대화 히스토리에서 가치 추출 API 호출
    const extractValue = async () => {
      // 메세지 형식 포맷팅 (사용자와 봇 대화 기록만)
      const chatHistory = messages
        .filter(msg => msg.content && !msg.content.includes('[일기 분석 시작]')) // 일기 분석 요청 헤더 제외
        .map(msg => ({
          role: msg.role,
          content: msg.content
        }));

      if (chatHistory.length === 0) {
        setError('추출할 대화 내역이 부족합니다. 먼저 대화를 나누어주세요.');
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch('http://localhost:8000/api/value-cards/extract', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ history: chatHistory })
        });

        if (!response.ok) {
          throw new Error('가치 추출 실패');
        }

        const data = await response.json();
        setKeyword(data.keyword);
        setInsight(data.insight);
      } catch (err) {
        console.error('Error extracting value card:', err);
        setError('AI가 깨달음을 추출하지 못했습니다. 직접 입력하여 카드를 만들 수 있습니다.');
        setKeyword('성찰');
        setInsight('대화를 통해 내면의 깊은 가치를 돌아보았습니다.');
      } finally {
        setIsLoading(false);
      }
    };

    extractValue();
  }, [messages]);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!keyword.trim() || !insight.trim()) return;

    setIsSaving(true);
    try {
      const response = await fetch('http://localhost:8000/api/value-cards', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          keyword: keyword.trim(),
          insight: insight.trim()
        })
      });

      if (!response.ok) {
        throw new Error('가치 카드 저장 실패');
      }

      alert('나의 실존적 가치 카드가 아카이브에 성공적으로 저장되었습니다! 🌐');
      if (onSaveSuccess) onSaveSuccess();
      onClose();
    } catch (err) {
      console.error('Error saving value card:', err);
      alert('가치 카드 저장 도중 데이터베이스 오류가 발생했습니다.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel animate-fade-in">
        <div className="modal-header">
          <h3>💡 실존 가치 카드 아카이브</h3>
          <button className="modal-close-btn" onClick={onClose} disabled={isSaving}>
            <X size={18} />
          </button>
        </div>

        {isLoading ? (
          <div className="modal-loading-body">
            <Loader2 className="animate-spin" size={32} color="var(--accent-primary)" />
            <p>대화 내용 속에서 당신의 '아하 모먼트'와 핵심 가치를 발견하고 있습니다...</p>
          </div>
        ) : (
          <form onSubmit={handleSave} className="modal-form">
            {error && (
              <div className="modal-error-banner">
                <ShieldAlert size={16} />
                <span>{error}</span>
              </div>
            )}

            <div className="modal-field">
              <label htmlFor="keyword">핵심 가치 키워드</label>
              <input
                type="text"
                id="keyword"
                className="modal-input"
                placeholder="예: 자유, 책임, 관계, 용기"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                disabled={isSaving}
                maxLength={10}
                required
              />
              <span className="modal-field-tip">대화에서 발견된 당신의 가장 핵심적인 단어입니다 (최대 10자).</span>
            </div>

            <div className="modal-field" style={{ flex: 1 }}>
              <label htmlFor="insight">한 줄 인사이트 (나의 깨달음)</label>
              <textarea
                id="insight"
                className="modal-textarea"
                placeholder="대화를 나누며 마음 속에 남은 성찰의 메시지를 적어보세요..."
                value={insight}
                onChange={(e) => setInsight(e.target.value)}
                disabled={isSaving}
                required
              />
              <span className="modal-field-tip">스스로의 생각을 따뜻하고 단단하게 다듬어 기록해보세요.</span>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="modal-cancel-btn"
                onClick={onClose}
                disabled={isSaving}
              >
                취소
              </button>
              <button
                type="submit"
                className="modal-submit-btn"
                disabled={isSaving || !keyword.trim() || !insight.trim()}
              >
                <Check size={18} />
                {isSaving ? '저장 중...' : '나의 의미 네트워크에 추가'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default ValueCardModal;
