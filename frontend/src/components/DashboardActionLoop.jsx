import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, Check, Clock3, Loader2, RotateCcw, X } from 'lucide-react';
import RecommendedExperiment from './RecommendedExperiment';
import { fetchWithAuth } from '../api';
import { buildActionLoopState } from '../utils/actionLoopState';
import { apiResponseError, responseJsonOrNull } from '../utils/apiErrors';
import {
  describeActionLoopCompletion,
  describeReviewTiming,
  describeSavedIntention,
  formatIntentionDate,
  formatIntentionRate,
  formatReviewQueue,
  getIntentionStatusMeta,
  intentionActivityAt,
  summarizeIntentions,
} from '../utils/intentionHistory';

const DEFAULT_STATS = {
  total: 0,
  open: 0,
  reflected: 0,
  dismissed: 0,
  due_count: 0,
  next_review_available_at: null,
  follow_through_rate: null,
  helpfulness_avg: null,
};

const fetchJson = async (path, token) => {
  const response = await fetchWithAuth(path, { token });
  if (!response.ok) throw await apiResponseError(response, '행동 루프 데이터를 불러오지 못했습니다.');
  return responseJsonOrNull(response);
};

const DashboardActionLoop = ({ token, onNewJournal, onNavigateToNetwork }) => {
  const [cards, setCards] = useState([]);
  const [dueIntentions, setDueIntentions] = useState([]);
  const [intentions, setIntentions] = useState([]);
  const [stats, setStats] = useState(DEFAULT_STATS);
  const [recommendationOverride, setRecommendationOverride] = useState(null);
  const [isRecommendationRefreshing, setIsRecommendationRefreshing] = useState(false);
  const [drafts, setDrafts] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [loopNotice, setLoopNotice] = useState('');
  const [busyId, setBusyId] = useState(null);

  const fetchRecommendationOverride = useCallback(async (refresh = false) => {
    if (!token) return null;
    setIsRecommendationRefreshing(refresh);
    try {
      const suffix = refresh ? '?refresh=true' : '';
      const data = await fetchJson(`/api/value-cards/recommended-experiment${suffix}`, token);
      setRecommendationOverride(data);
      return data;
    } catch (recommendationError) {
      console.warn('LLM experiment recommendation unavailable:', recommendationError);
      setRecommendationOverride(null);
      return null;
    } finally {
      setIsRecommendationRefreshing(false);
    }
  }, [token]);

  const load = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError('');
    try {
      const [cardsData, dueData, statsData, intentionsData] = await Promise.all([
        fetchJson('/api/value-cards', token),
        fetchJson('/api/intentions/due', token),
        fetchJson('/api/intentions/stats', token),
        fetchJson('/api/intentions', token),
      ]);
      setCards(Array.isArray(cardsData) ? cardsData : []);
      setDueIntentions(Array.isArray(dueData) ? dueData : []);
      setStats(statsData || DEFAULT_STATS);
      setIntentions(Array.isArray(intentionsData) ? intentionsData : []);

      if (Array.isArray(cardsData) && cardsData.length > 0) {
        fetchRecommendationOverride(false);
      } else {
        setRecommendationOverride(null);
      }
    } catch (err) {
      console.warn('Dashboard action loop unavailable:', err);
      setError(err.message || '행동 루프 데이터를 불러오는 중 문제가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [token, fetchRecommendationOverride]);

  useEffect(() => {
    let isActive = true;
    const run = async () => {
      if (!isActive) return;
      await load();
    };
    run();
    return () => {
      isActive = false;
    };
  }, [load]);

  const loopState = useMemo(
    () => buildActionLoopState({ dueIntentions, cards, recommendationOverride }),
    [dueIntentions, cards, recommendationOverride]
  );
  const historySummary = useMemo(() => summarizeIntentions(intentions), [intentions]);

  const setDraft = (id, patch) => {
    setLoopNotice('');
    setDrafts((current) => ({
      ...current,
      [id]: { outcome: '', helpfulness: null, ...current[id], ...patch },
    }));
  };

  const clearDraft = (id) => {
    setDrafts((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });
  };

  const refreshLoop = () => {
    setLoopNotice('');
    load();
  };

  const handleExperimentSaved = async (savedIntention) => {
    const notice = describeSavedIntention(savedIntention);
    setLoopNotice('');
    await load();
    setLoopNotice(notice);
  };

  const recoverStaleIntention = async (intention, message) => {
    clearDraft(intention.id);
    await load();
    setLoopNotice(message);
  };

  const reflect = async (intention) => {
    const draft = drafts[intention.id] || {};
    if (!draft.outcome?.trim()) return;

    setBusyId(intention.id);
    setError('');
    setLoopNotice('');
    try {
      const response = await fetchWithAuth(`/api/intentions/${intention.id}/reflect`, {
        method: 'PATCH',
        token,
        headers: {
          'Content-Type': 'application/json',
          'X-Logos-Action-Source': 'dashboard_action_loop',
        },
        body: JSON.stringify({
          outcome: draft.outcome.trim(),
          helpfulness: draft.helpfulness,
          source: 'dashboard_action_loop',
        }),
      });
      if (!response.ok) {
        throw await apiResponseError(response, '실험 회고를 기록하지 못했습니다.');
      }
      const reflectedIntention = await responseJsonOrNull(response);
      await load();
      clearDraft(intention.id);
      setLoopNotice(describeActionLoopCompletion('reflected', reflectedIntention));
    } catch (err) {
      console.warn('Dashboard intention reflection failed:', err);
      if (err.status === 409) {
        await recoverStaleIntention(intention, err.message);
        return;
      }
      setError(err.message || '실험 회고 중 문제가 발생했습니다.');
    } finally {
      setBusyId(null);
    }
  };

  const dismiss = async (intention) => {
    setBusyId(intention.id);
    setError('');
    setLoopNotice('');
    try {
      const response = await fetchWithAuth(`/api/intentions/${intention.id}/dismiss`, {
        method: 'POST',
        token,
        headers: {
          'X-Logos-Action-Source': 'dashboard_action_loop',
        },
      });
      if (!response.ok) {
        throw await apiResponseError(response, '실험을 접어두지 못했습니다.');
      }
      const dismissedIntention = await responseJsonOrNull(response);
      await load();
      clearDraft(intention.id);
      setLoopNotice(describeActionLoopCompletion('dismissed', dismissedIntention));
    } catch (err) {
      console.warn('Dashboard intention dismiss failed:', err);
      if (err.status === 409) {
        await recoverStaleIntention(intention, err.message);
        return;
      }
      setError(err.message || '실험을 접어두는 중 문제가 발생했습니다.');
    } finally {
      setBusyId(null);
    }
  };

  const activeIntention = loopState.activeIntention;
  const activeDraft = activeIntention
    ? drafts[activeIntention.id] || { outcome: '', helpfulness: null }
    : null;

  return (
    <section className="dashboard-action-loop">
      <div className="dashboard-action-loop-heading">
        <div>
          <p>누적 기록을 다음 선택으로</p>
          <h2>오늘의 의미 행동 루프</h2>
        </div>
        <button type="button" onClick={refreshLoop} disabled={isLoading} title="행동 루프 새로고침">
          <RotateCcw size={15} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </div>

      {isLoading ? (
        <div className="dashboard-action-loop-state glass-panel">
          <Loader2 className="animate-spin" size={24} color="var(--accent-primary)" />
          <p>가치 카드와 지난 실험을 확인하는 중...</p>
        </div>
      ) : (
        <>
          {error && (
            <div className="dashboard-action-loop-error" role="alert">
              <AlertTriangle size={16} />
              <span>{error}</span>
            </div>
          )}

          {loopNotice && (
            <div className="dashboard-action-loop-notice" role="status" aria-live="polite">
              <Check size={16} />
              <span>{loopNotice}</span>
            </div>
          )}

          {loopState.status === 'review' && activeIntention && (
            <div className="dashboard-review-panel glass-panel animate-fade-in">
              <div className="dashboard-review-copy">
                <p className="dashboard-review-kicker">먼저 돌아볼 실험</p>
                <h3>그 선택, 실제로 해보니 어땠나요?</h3>
                <p>
                  {activeIntention.card_keyword
                    ? `‘${activeIntention.card_keyword}’에서 이어진 실험입니다.`
                    : '지난 성찰에서 담아둔 실험입니다.'}
                  {dueIntentions.length > 1 ? ` 아직 ${dueIntentions.length}개의 실험이 회고를 기다리고 있어요.` : ''}
                </p>
              </div>

              <blockquote>{activeIntention.intention}</blockquote>

              <textarea
                value={activeDraft.outcome}
                onChange={(event) => setDraft(activeIntention.id, { outcome: event.target.value })}
                disabled={busyId === activeIntention.id}
                placeholder="해보니 무엇이 달라졌나요?"
                rows={3}
              />

              <div className="dashboard-helpfulness-row">
                <span>도움 정도</span>
                {[1, 2, 3, 4, 5].map((score) => (
                  <button
                    key={score}
                    type="button"
                    onClick={() => setDraft(activeIntention.id, { helpfulness: score })}
                    disabled={busyId === activeIntention.id}
                    className={activeDraft.helpfulness === score ? 'active' : ''}
                  >
                    {score}
                  </button>
                ))}
              </div>

              <div className="dashboard-review-actions">
                <button
                  type="button"
                  className="dashboard-review-dismiss"
                  onClick={() => dismiss(activeIntention)}
                  disabled={busyId === activeIntention.id}
                >
                  <X size={14} />
                  접어두기
                </button>
                <button
                  type="button"
                  className="dashboard-review-submit"
                  onClick={() => reflect(activeIntention)}
                  disabled={busyId === activeIntention.id || !activeDraft.outcome.trim()}
                >
                  <Check size={14} />
                  {busyId === activeIntention.id ? '기록 중' : '회고 기록하기'}
                </button>
              </div>
            </div>
          )}

          {loopState.status === 'recommendation' && (
            <RecommendedExperiment
              token={token}
              recommendation={loopState.recommendation}
              title="오늘의 의미 실험"
              kicker="내 기록에서 이어지는 다음 작은 선택"
              showEvidence={false}
              source="dashboard_action_loop"
              onRefresh={() => fetchRecommendationOverride(true)}
              isRefreshing={isRecommendationRefreshing}
              onSaved={handleExperimentSaved}
            />
          )}

          {loopState.status === 'empty' && (
            <div className="dashboard-action-loop-empty glass-panel">
              <div>
                <p>아직 실험으로 바꿀 가치 카드가 없습니다.</p>
                <h3>일기 작성 → 성찰 대화 → 가치 카드 저장으로 첫 행동 루프를 시작해보세요.</h3>
              </div>
              <div className="dashboard-action-loop-empty-actions">
                <button type="button" onClick={onNewJournal}>새 일기 쓰기</button>
                <button type="button" onClick={onNavigateToNetwork}>의미 네트워크 보기</button>
              </div>
            </div>
          )}
        </>
      )}

      <ActionStats stats={stats} />
      <ActionHistory summary={historySummary} />
    </section>
  );
};

const ActionStats = ({ stats }) => {
  const safeStats = stats || DEFAULT_STATS;
  const helpfulness = typeof safeStats.helpfulness_avg === 'number'
    ? safeStats.helpfulness_avg.toFixed(1)
    : '-';
  const reviewRate = formatIntentionRate(safeStats.follow_through_rate);
  const reviewQueue = formatReviewQueue(safeStats);

  return (
    <div className="dashboard-action-stats" aria-label="의미 실험 기록">
      <div>
        <Activity size={14} />
        <span>담은 실험</span>
        <strong>{safeStats.total || 0}</strong>
      </div>
      <div>
        <Check size={14} />
        <span>돌아볼 실험</span>
        <strong>{reviewQueue}</strong>
      </div>
      <div>
        <span className="dashboard-action-stat-dot" />
        <span>돌아본 비율</span>
        <strong>{reviewRate}</strong>
      </div>
      <div>
        <span className="dashboard-action-stat-dot muted" />
        <span>평균 도움</span>
        <strong>{helpfulness}</strong>
      </div>
    </div>
  );
};

const ActionHistory = ({ summary }) => {
  if (!summary || summary.total === 0) return null;

  return (
    <div className="dashboard-action-history glass-panel" aria-label="의미 실험 기록">
      <div className="dashboard-action-history-heading">
        <div>
          <p>실험 기록</p>
          <h3>내 선택이 실제로 도움이 됐는지 쌓아가는 중입니다.</h3>
        </div>
        <div className="dashboard-action-history-counts">
          <span>{summary.counts.open || 0} 진행</span>
          <span>{summary.counts.reflected || 0} 회고</span>
          <span>{summary.counts.dismissed || 0} 접어둠</span>
        </div>
      </div>

      <div className="dashboard-action-history-grid">
        <div className="dashboard-action-history-list">
          <div className="dashboard-action-history-section-title">
            <Clock3 size={13} />
            최근 실험
          </div>
          {summary.recent.map((intention) => (
            <HistoryItem key={intention.id} intention={intention} />
          ))}
        </div>

        <div className="dashboard-action-history-list">
          <div className="dashboard-action-history-section-title">
            <Check size={13} />
            도움이 컸던 실험
          </div>
          {summary.mostHelpful.length > 0 ? (
            summary.mostHelpful.map((intention) => (
              <HistoryItem key={intention.id} intention={intention} compact />
            ))
          ) : (
            <p className="dashboard-action-history-empty">
              회고가 쌓이면 도움 정도가 높았던 실험을 보여드립니다.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

const HistoryItem = ({ intention, compact = false }) => {
  const meta = getIntentionStatusMeta(intention.status);
  const date = formatIntentionDate(intentionActivityAt(intention));
  const reviewTiming = describeReviewTiming(intention);

  return (
    <article className={`dashboard-action-history-item ${compact ? 'compact' : ''}`}>
      <div className="dashboard-action-history-item-top">
        <span className={`dashboard-action-history-status ${meta.tone}`}>{meta.label}</span>
        {date && <time>{date}</time>}
      </div>
      <p>{intention.intention}</p>
      <div className="dashboard-action-history-meta">
        {intention.card_keyword && <span>#{intention.card_keyword}</span>}
        {typeof intention.helpfulness === 'number' && (
          <span>도움 {intention.helpfulness}/5</span>
        )}
        {reviewTiming && <span>{reviewTiming}</span>}
      </div>
      {!compact && intention.outcome && (
        <blockquote>{intention.outcome}</blockquote>
      )}
    </article>
  );
};

export default DashboardActionLoop;
