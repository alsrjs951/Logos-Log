import { useState, useEffect, useCallback, useRef } from 'react';
import { AlertTriangle, FileText, Loader2, Sparkles, RefreshCw, TrendingUp } from 'lucide-react';
import { fetchWithAuth } from '../api';
import { apiResponseError, responseJsonOrNull } from '../utils/apiErrors';

const EMPTY_REPORT = {
  status: 'empty',
  has_data: false,
  message: '최근 7일간 작성된 일기가 없습니다.',
  summary: null,
  keywords: [],
  next_question: null,
  journal_count: 0,
};

const REPORT_CACHE_TTL_MS = 1000 * 60 * 5;
const reportCache = new Map();
const inFlightReports = new Map();

const cleanReportText = (value) => {
  if (!value) return '';

  return String(value)
    .replace(/[ \t]*[\u2014\u2013\u2015][ \t]*/g, ' ')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
};

const getReportCacheKey = (token) => token || 'anonymous';

const normalizeReport = (data) => (
  data?.has_data === false ? { ...EMPTY_REPORT, ...data } : data
);

const getCachedReport = (cacheKey) => {
  const cached = reportCache.get(cacheKey);
  if (!cached) return null;

  if (Date.now() - cached.savedAt > REPORT_CACHE_TTL_MS) {
    reportCache.delete(cacheKey);
    return null;
  }

  return cached.report;
};

const loadWeeklyReport = async (token, { force = false } = {}) => {
  const cacheKey = getReportCacheKey(token);
  const cached = force ? null : getCachedReport(cacheKey);
  if (cached) return cached;

  const pending = force ? null : inFlightReports.get(cacheKey);
  if (pending) return pending;

  const request = (async () => {
    const res = await fetchWithAuth('/api/journals/weekly-report', { token });

    if (res.status === 204 || res.status === 404) {
      return { ...EMPTY_REPORT };
    }

    if (!res.ok) throw await apiResponseError(res, '리포트를 불러오는 중 문제가 발생했습니다.');
    const data = await responseJsonOrNull(res);
    if (!data) throw new Error('리포트 응답을 읽지 못했습니다.');
    return normalizeReport(data);
  })();

  inFlightReports.set(cacheKey, request);

  try {
    const report = await request;
    if (inFlightReports.get(cacheKey) === request) {
      reportCache.set(cacheKey, { report, savedAt: Date.now() });
    }
    return report;
  } finally {
    if (inFlightReports.get(cacheKey) === request) {
      inFlightReports.delete(cacheKey);
    }
  }
};

const WeeklyReport = ({ token }) => {
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hasLoaded, setHasLoaded] = useState(false);
  const requestIdRef = useRef(0);
  const isMountedRef = useRef(false);

  const fetchReport = useCallback(async ({ force = false } = {}) => {
    if (!token) return;
    const cacheKey = getReportCacheKey(token);
    const cached = force ? null : getCachedReport(cacheKey);
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    if (cached) {
      setReport(cached);
      setError(null);
      setHasLoaded(true);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const nextReport = await loadWeeklyReport(token, { force });
      if (!isMountedRef.current || requestId !== requestIdRef.current) return;
      setReport(nextReport);
    } catch (e) {
      if (!isMountedRef.current || requestId !== requestIdRef.current) return;
      setReport(null);
      setError(e.message || '리포트를 불러오는 중 문제가 발생했습니다.');
    } finally {
      if (isMountedRef.current && requestId === requestIdRef.current) {
        setIsLoading(false);
        setHasLoaded(true);
      }
    }
  }, [token]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const summary = cleanReportText(report?.summary);
  const nextQuestion = cleanReportText(report?.next_question);
  const keywords = Array.isArray(report?.keywords)
    ? report.keywords.map(cleanReportText).filter(Boolean)
    : [];

  return (
    <div
      className="glass-panel weekly-report-panel"
      style={{
        padding: '24px',
        background: 'linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(16,185,129,0.05) 100%)',
        border: '1px solid rgba(99,102,241,0.2)',
        position: 'relative',
        overflow: 'visible',
        maxWidth: '100%',
      }}
    >
      {/* 헤더 */}
      <div className="weekly-report-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div className="weekly-report-title-row" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            className="weekly-report-icon"
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
          <div className="weekly-report-title-copy">
            <h2 className="weekly-report-title" style={{ fontSize: '1rem', fontWeight: '700', margin: 0 }}>이번 주 성찰 리포트</h2>
            <p className="weekly-report-subtitle" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: 0 }}>
              최근 7일간의 기록에서 반복된 흐름을 정리합니다
            </p>
          </div>
        </div>
        <button
          className="weekly-report-refresh"
          onClick={() => fetchReport({ force: true })}
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
      {isLoading && !report && (
        <div className="weekly-report-state" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', padding: '24px 0' }}>
          <Loader2 size={28} color="var(--accent-primary)" style={{ animation: 'spin 1s linear infinite' }} />
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0 }}>
            이번 주 기록의 흐름을 정리하는 중...
          </p>
        </div>
      )}

      {error && !isLoading && (
        <div
          className="weekly-report-error"
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            background: 'rgba(245,158,11,0.08)',
            border: '1px solid rgba(245,158,11,0.22)',
            borderRadius: '10px',
            padding: '14px',
            color: '#fbbf24',
          }}
        >
          <AlertTriangle size={16} style={{ flex: '0 0 auto', marginTop: '2px' }} />
          <div style={{ minWidth: 0 }}>
            <p style={{ fontSize: '0.82rem', fontWeight: 700, margin: '0 0 4px 0' }}>
              리포트 생성 상태를 확인하지 못했습니다.
            </p>
            <p className="weekly-report-text" style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0 }}>
              {error}
            </p>
          </div>
        </div>
      )}

      {!error && hasLoaded && report && !report.has_data && (
        <div className="weekly-report-state" style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '22px 0', color: 'var(--text-muted)' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flex: '0 0 auto',
            }}
          >
            <FileText size={17} color="var(--accent-primary)" />
          </div>
          <div style={{ minWidth: 0 }}>
            <p style={{ fontSize: '0.88rem', fontWeight: 700, color: '#e2e8f0', margin: '0 0 5px 0' }}>
              아직 이번 주 리포트가 없습니다.
            </p>
            <p className="weekly-report-text" style={{ fontSize: '0.78rem', margin: 0 }}>
              {report.message || '최근 7일 동안 작성한 일기가 생기면 성찰 리포트가 표시됩니다.'}
            </p>
          </div>
        </div>
      )}

      {!error && report && report.has_data && (
        <div className="weekly-report-body" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* 요약 */}
          <div
            className="weekly-report-section"
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
            <p className="weekly-report-text" style={{ margin: 0 }}>{summary}</p>
          </div>

          {/* 핵심 가치 키워드 */}
          {keywords.length > 0 && (
            <div className="weekly-report-keywords-section">
              <p style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                이번 주 핵심 가치
              </p>
              <div className="weekly-report-keywords" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {keywords.map((kw, i) => {
                  const colors = ['rgba(99,102,241,0.2)', 'rgba(16,185,129,0.18)', 'rgba(236,72,153,0.18)'];
                  const borders = ['rgba(99,102,241,0.4)', 'rgba(16,185,129,0.4)', 'rgba(236,72,153,0.4)'];
                  const textColors = ['#a5b4fc', '#6ee7b7', '#f9a8d4'];
                  return (
                    <span
                      key={i}
                      className="weekly-report-keyword"
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
          {nextQuestion && (
            <div
              className="weekly-report-section"
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
              <p className="weekly-report-text" style={{ margin: 0, fontSize: '0.88rem', color: '#e2e8f0', lineHeight: '1.6', fontStyle: 'italic' }}>
                "{nextQuestion}"
              </p>
            </div>
          )}

          <p className="weekly-report-footnote" style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: 0, textAlign: 'right' }}>
            이번 주 일기 {report.journal_count}편 기반
          </p>
        </div>
      )}
    </div>
  );
};

export default WeeklyReport;
