import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ShieldAlert, Check, X, Loader2 } from 'lucide-react';
import { apiUrl } from '../api';

const ValueCardModal = ({ token, messages, onClose, onNavigateToNetwork, emotion }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [insight, setInsight] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  // insight→행동 루프: 저장된 카드에 연결할 '다짐'(선택)
  const [savedCardId, setSavedCardId] = useState(null);
  const [intentionText, setIntentionText] = useState('');
  const [intentionSaving, setIntentionSaving] = useState(false);
  const [intentionSaved, setIntentionSaved] = useState(false);

  // 캔버스 기반 카드 이미지 드로잉 및 다운로드 처리 함수
  const exportCardAsImage = () => {
    if (!keyword || !insight) return;

    const canvas = document.createElement('canvas');
    canvas.width = 800;
    canvas.height = 1200;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const emotionColorMap = {
      happy: '#10b981', 
      sad: '#6366f1', 
      stressed: '#ec4899', 
      calm: '#06b6d4', 
      tired: '#f59e0b' 
    };
    const themeColor = emotionColorMap[emotion] || '#6366f1';

    // 1. 우주 배경 그리기
    const bgGrad = ctx.createLinearGradient(0, 0, 0, 1200);
    bgGrad.addColorStop(0, '#0a0b1a');
    bgGrad.addColorStop(0.5, '#060713');
    bgGrad.addColorStop(1, '#020308');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, 800, 1200);

    // 1-1. 성간 오로라 광원 효과 추가
    const radialGrad = ctx.createRadialGradient(400, 500, 50, 400, 500, 400);
    radialGrad.addColorStop(0, hexToRgbAlpha(themeColor, 0.18));
    radialGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = radialGrad;
    ctx.fillRect(0, 0, 800, 1200);

    // 1-2. 무작위 별빛 파우더 드로잉
    ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
    for (let i = 0; i < 50; i++) {
      const x = Math.random() * 800;
      const y = Math.random() * 1200;
      const size = Math.random() * 1.8 + 0.5;
      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fill();
    }

    // 2. 글라스모피즘 카드 모양 그리기
    const cardX = 80;
    const cardY = 150;
    const cardW = 640;
    const cardH = 900;
    const cardR = 32;

    ctx.save();
    ctx.shadowColor = 'rgba(0, 0, 0, 0.55)';
    ctx.shadowBlur = 45;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 15;

    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(cardX, cardY, cardW, cardH, cardR);
    } else {
      drawRoundRectPolyfill(ctx, cardX, cardY, cardW, cardH, cardR);
    }
    ctx.fillStyle = 'rgba(255, 255, 255, 0.035)';
    ctx.fill();
    ctx.restore();

    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(cardX, cardY, cardW, cardH, cardR);
    } else {
      drawRoundRectPolyfill(ctx, cardX, cardY, cardW, cardH, cardR);
    }
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 3. 카드 상단 장식 별 렌더링
    ctx.save();
    ctx.shadowColor = themeColor;
    ctx.shadowBlur = 15;
    ctx.fillStyle = '#ffffff';
    drawStar(ctx, 400, 240, 4, 15, 6);
    ctx.restore();

    // 4. 타이틀 텍스트 렌더링
    ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.font = '600 13px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('L O G O S  -  L O G   |   M E A N I N G   A R C H I V E', 400, 290);

    const emojiMap = { happy: '😊 행복', sad: '😢 슬픔', stressed: '🤯 스트레스', calm: '🧘 평온', tired: '😴 피로' };
    const emotionLabel = emojiMap[emotion] || '📝 성찰';
    ctx.fillStyle = hexToRgbAlpha(themeColor, 0.85);
    ctx.font = '700 14px Inter, sans-serif';
    ctx.fillText(`마음 온도: ${emotionLabel}`, 400, 330);

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.beginPath();
    ctx.moveTo(250, 370);
    ctx.lineTo(550, 370);
    ctx.stroke();

    // 4-1. 핵심 가치 키워드 (네온 글로우)
    ctx.save();
    ctx.shadowColor = themeColor;
    ctx.shadowBlur = 25;
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 58px Inter, system-ui, sans-serif';
    ctx.fillText(keyword, 400, 480);
    ctx.restore();

    // 4-2. 인사이트 본문 (다단 줄바꿈 연산)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.82)';
    ctx.font = '500 24px Inter, system-ui, sans-serif';
    const maxTextWidth = 460;
    const lineHeight = 42;
    const textYStart = 580;
    wrapText(ctx, insight, 400, textYStart, maxTextWidth, lineHeight);

    // 5. 하단 데코 및 브랜딩 날짜 표기
    ctx.fillStyle = 'rgba(255, 255, 255, 0.18)';
    ctx.font = '600 12px Inter, sans-serif';
    ctx.fillText('나의 마음 깊은 곳에서 건져 올린 실존 가치를 기록합니다.', 400, 930);

    const now = new Date();
    const dateStr = `${now.getFullYear()}. ${String(now.getMonth() + 1).padStart(2, '0')}. ${String(now.getDate()).padStart(2, '0')}.`;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.28)';
    ctx.font = '700 13px Inter, sans-serif';
    ctx.fillText(dateStr, 400, 970);

    // 6. 다운로드 트리거
    const dataUrl = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.download = `[Logos-Log]_가치카드_${keyword}.png`;
    link.href = dataUrl;
    link.click();
  };

  const hexToRgbAlpha = (hex, alpha) => {
    const cleanHex = hex.replace('#', '');
    const r = parseInt(cleanHex.substring(0, 2), 16);
    const g = parseInt(cleanHex.substring(2, 4), 16);
    const b = parseInt(cleanHex.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const drawRoundRectPolyfill = (ctx, x, y, width, height, radius) => {
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
  };

  const drawStar = (ctx, cx, cy, spikes, outerRadius, innerRadius) => {
    let rot = Math.PI / 2 * 3;
    const step = Math.PI / spikes;

    ctx.beginPath();
    ctx.moveTo(cx, cy - outerRadius);
    for (let i = 0; i < spikes; i++) {
      let x = cx + Math.cos(rot) * outerRadius;
      let y = cy + Math.sin(rot) * outerRadius;
      ctx.lineTo(x, y);
      rot += step;

      x = cx + Math.cos(rot) * innerRadius;
      y = cy + Math.sin(rot) * innerRadius;
      ctx.lineTo(x, y);
      rot += step;
    }
    ctx.lineTo(cx, cy - outerRadius);
    ctx.closePath();
    ctx.fill();
  };

  const wrapText = (ctx, text, x, y, maxWidth, lineHeight) => {
    const chars = text.split('');
    let line = '';
    let lines = [];

    for (let i = 0; i < chars.length; i++) {
      let testLine = line + chars[i];
      let testWidth = ctx.measureText(testLine).width;
      if (testWidth > maxWidth && i > 0) {
        lines.push(line);
        line = chars[i];
      } else {
        line = testLine;
      }
    }
    lines.push(line);

    for (let j = 0; j < lines.length; j++) {
      ctx.fillText(lines[j], x, y + (j * lineHeight));
    }
  };

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
        const response = await fetch(apiUrl('/api/value-cards/extract'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
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
      const response = await fetch(apiUrl('/api/value-cards'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          keyword: keyword.trim(),
          insight: insight.trim(),
          emotion: emotion
        })
      });

      if (!response.ok) {
        throw new Error('가치 카드 저장 실패');
      }

      const data = await response.json();
      setSavedCardId(data.id);
      setIsSuccess(true);
    } catch (err) {
      console.error('Error saving value card:', err);
      alert('가치 카드 저장 도중 데이터베이스 오류가 발생했습니다.');
    } finally {
      setIsSaving(false);
    }
  };

  // 깨달음을 행동으로: 저장된 카드에 다짐 연결 (선택 - 강요하지 않음)
  const handleSaveIntention = async () => {
    if (!savedCardId || !intentionText.trim()) return;
    setIntentionSaving(true);
    try {
      const response = await fetch(apiUrl('/api/intentions'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ card_id: savedCardId, intention: intentionText.trim() }),
      });
      if (!response.ok) throw new Error('다짐 저장 실패');
      setIntentionSaved(true);
    } catch (err) {
      console.error('Error saving intention:', err);
      alert('다짐 저장 중 오류가 발생했습니다.');
    } finally {
      setIntentionSaving(false);
    }
  };

  return createPortal(
    <div className="modal-overlay">
      <div className="modal-content glass-panel animate-fade-in">
        <div className="modal-header">
          <h3>{isSuccess ? '✨ 가치 노드 활성화' : '💡 실존 가치 카드 아카이브'}</h3>
          <button className="modal-close-btn" onClick={onClose} disabled={isSaving}>
            <X size={18} />
          </button>
        </div>

        {isSuccess ? (
          <div className="modal-success-body animate-fade-in" style={{ padding: '30px 10px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px' }}>
            <div className="success-icon-wrapper" style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '10px', border: '1px solid rgba(16, 185, 129, 0.3)', animation: 'pulse 2s infinite ease-in-out' }}>
              <Check size={36} color="#10b981" />
            </div>
            <h4 style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>새로운 성찰 별자리 탄생!</h4>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', lineHeight: '1.6', margin: '0 20px', maxWidth: '360px' }}>
              핵심 가치 키워드 <strong style={{ color: 'var(--accent-secondary)' }}>'{keyword}'</strong>가 나만의 성찰 은하에 노드로 훌륭히 매핑되었습니다.
            </p>

            {/* 깨달음을 행동으로 - 선택적 다짐(insight→action 루프) */}
            <div style={{ width: '100%', maxWidth: '420px', marginTop: '6px', padding: '16px', borderRadius: '12px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-glass)', textAlign: 'left' }}>
              {intentionSaved ? (
                <div style={{ textAlign: 'center', color: 'var(--text-main)' }}>
                  <div style={{ fontSize: '1.4rem', marginBottom: '6px' }}>🌱</div>
                  <p style={{ margin: 0, fontSize: '0.88rem', lineHeight: 1.6, color: 'var(--text-muted)' }}>
                    다짐을 담아두었어요. 며칠 뒤 <strong>변화 추이</strong> 화면에 들르면
                    "그 선택, 해보니 어땠나요?"를 함께 돌아볼 수 있어요.
                  </p>
                </div>
              ) : (
                <>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
                    💪 이 깨달음을 작은 행동으로? <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>(선택)</span>
                  </label>
                  <p style={{ margin: '0 0 8px', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                    이번 주에 시도해 볼 한 가지 다짐을 적어두면, 나중에 그 결과를 돌아볼 수 있어요.
                  </p>
                  <textarea
                    value={intentionText}
                    onChange={(e) => setIntentionText(e.target.value)}
                    disabled={intentionSaving}
                    placeholder="예: 이번 주엔 부탁을 한 번 정중히 거절해 보겠다."
                    rows={2}
                    style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', padding: '8px 10px', borderRadius: '8px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-glass)', color: 'var(--text-main)', fontFamily: 'inherit', fontSize: '0.86rem' }}
                  />
                  <button
                    type="button"
                    onClick={handleSaveIntention}
                    disabled={intentionSaving || !intentionText.trim()}
                    style={{ marginTop: '8px', width: '100%', padding: '9px', borderRadius: '8px', border: '1px solid rgba(99,102,241,0.35)', background: 'rgba(99,102,241,0.12)', color: 'var(--accent-primary, #6366f1)', fontWeight: 600, fontSize: '0.84rem', fontFamily: 'inherit', cursor: intentionText.trim() ? 'pointer' : 'not-allowed', opacity: intentionText.trim() ? 1 : 0.5 }}
                  >
                    {intentionSaving ? '저장 중...' : '다짐 담아두기'}
                  </button>
                </>
              )}
            </div>
            <div className="success-actions" style={{ display: 'flex', gap: '12px', marginTop: '15px', width: '100%', justifyContent: 'center', flexWrap: 'wrap' }}>
              <button 
                type="button" 
                className="success-download-btn"
                onClick={exportCardAsImage}
                style={{ background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '12px 20px', borderRadius: '8px', color: '#10b981', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.9rem', fontFamily: 'inherit', transition: 'all 0.25s' }}
              >
                📥 카드 소장하기
              </button>
              <button 
                type="button" 
                className="success-nav-btn"
                onClick={() => {
                  if (onNavigateToNetwork) onNavigateToNetwork();
                  onClose();
                }}
                style={{ background: 'var(--accent-gradient)', border: 'none', padding: '12px 20px', borderRadius: '8px', color: 'white', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.9rem', boxShadow: '0 4px 15px rgba(99, 102, 241, 0.25)', fontFamily: 'inherit' }}
              >
                🌌 3D 은하수 보러가기
              </button>
              <button 
                type="button" 
                className="success-close-btn"
                onClick={onClose}
                style={{ background: 'rgba(255, 255, 255, 0.05)', border: '1px solid var(--border-glass)', padding: '12px 20px', borderRadius: '8px', color: 'var(--text-main)', fontWeight: '600', cursor: 'pointer', fontSize: '0.9rem', fontFamily: 'inherit' }}
              >
                대화 계속하기
              </button>
            </div>
          </div>
        ) : isLoading ? (
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
    </div>,
    document.body
  );
};

export default ValueCardModal;
