import React, { useState, useEffect } from 'react';
import { Loader2, Sparkles, RefreshCw, TrendingUp } from 'lucide-react';

const WeeklyReport = ({ token }) => {
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  const fetchReport = async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('http://localhost:8000/api/journals/weekly-report', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('리포트를 불러오지 못했습니다.');
      const data = await res.json();
      setReport(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
      setHasLoaded(true);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [token]);

  return (
    <div
      className="glass-panel"
      style={{
        padding: '24px',
        background: 'linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(16,185,129,0.05) 100%)',
        border: '1px solid rgba(99,102,241,0.2)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* 배경 장식 */}
      <div
        style={{
          position: 'absolute',
          top: '-30px',
          right: '-30px',
          width: '120px',
          height: '120px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }}
      />

      {/* 헤더 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '10px',
              background: 'rgba(99,102,241,0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <TrendingUp size={16} color="var(--accent-primary)" />
          </div>
          <div>
            <h2 style={{ fontSize: '1rem', fontWeight: '700', margin: 0 }}>이번 주 성찰 리포트</h2>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: 0 }}>
              최근 7일간의 기록을 AI가 분석했습니다
            </p>
          </div>
        </div>
        <button
          onClick={fetchReport}
          disabled={isLoading}
          title="리포트 새로고침"
          style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid var(--border-glass)',
            borderRadius: '8px',
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: 'var(--text-muted)',
            transition: 'all 0.2s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; }}
        >
          <RefreshCw size={14} style={{ animation: isLoading ? 'spin 1s linear infinite' : 'none' }} />
        </button>
      </div>

      {/* 콘텐츠 */}
      {isLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', padding: '24px 0' }}>
          <Loader2 size={28} color="var(--accent-primary)" style={{ animation: 'spin 1s linear infinite' }} />
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0 }}>
            AI가 이번 주 성찰을 분석하는 중...
          </p>
        </div>
      )}

      {error && !isLoading && (
        <div
          style={{
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: '10px',
            padding: '14px',
            fontSize: '0.82rem',
            color: '#ef4444',
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {!isLoading && !error && hasLoaded && report && !report.has_data && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '0.88rem', margin: '0 0 6px 0' }}>이번 주 작성된 일기가 없습니다.</p>
          <p style={{ fontSize: '0.78rem', margin: 0 }}>일기를 작성하면 AI 성찰 리포트가 생성됩니다 ✨</p>
        </div>
      )}

      {!isLoading && !error && report && report.has_data && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* 요약 */}
          <div
            style={{
              background: 'rgba(255,255,255,0.03)',
              borderRadius: '12px',
              padding: '16px',
              border: '1px solid rgba(255,255,255,0.05)',
              lineHeight: '1.75',
              fontSize: '0.88rem',
              color: '#e2e8f0',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
              <Sparkles size={13} color="var(--accent-primary)" />
              <span style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--accent-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                이번 주 흐름
              </span>
            </div>
            <p style={{ margin: 0 }}>{report.summary}</p>
          </div>

          {/* 핵심 가치 키워드 */}
          {report.keywords && report.keywords.length > 0 && (
            <div>
              <p style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                이번 주 핵심 가치
              </p>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {report.keywords.map((kw, i) => {
                  const colors = ['rgba(99,102,241,0.2)', 'rgba(16,185,129,0.18)', 'rgba(236,72,153,0.18)'];
                  const borders = ['rgba(99,102,241,0.4)', 'rgba(16,185,129,0.4)', 'rgba(236,72,153,0.4)'];
                  const textColors = ['#a5b4fc', '#6ee7b7', '#f9a8d4'];
                  return (
                    <span
                      key={i}
                      style={{
                        padding: '6px 14px',
                        borderRadius: '100px',
                        background: colors[i % colors.length],
                        border: `1px solid ${borders[i % borders.length]}`,
                        fontSize: '0.8rem',
                        fontWeight: '700',
                        color: textColors[i % textColors.length],
                        letterSpacing: '0.02em',
                      }}
                    >
                      {kw}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* 추천 질문 */}
          {report.next_question && (
            <div
              style={{
                background: 'linear-gradient(135deg, rgba(99,102,241,0.1), rgba(16,185,129,0.08))',
                border: '1px solid rgba(99,102,241,0.25)',
                borderRadius: '12px',
                padding: '16px',
              }}
            >
              <p style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--accent-primary)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                🔍 다음 주 탐구 질문
              </p>
              <p style={{ margin: 0, fontSize: '0.88rem', color: '#e2e8f0', lineHeight: '1.6', fontStyle: 'italic' }}>
                "{report.next_question}"
              </p>
            </div>
          )}

          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: 0, textAlign: 'right' }}>
            이번 주 일기 {report.journal_count}편 기반
          </p>
        </div>
      )}
    </div>
  );
};

export default WeeklyReport;
