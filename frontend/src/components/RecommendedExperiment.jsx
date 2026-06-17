import { useEffect, useRef, useState } from 'react';
import { Check, Loader2, RotateCcw, Sparkles } from 'lucide-react';
import { fetchWithAuth } from '../api';
import { apiResponseError, responseJsonOrNull } from '../utils/apiErrors';
import { describeSavedIntention } from '../utils/intentionHistory';

const MAX_VISIBLE_CARDS = 5;

const RecommendedExperiment = ({
  token,
  recommendation,
  selectedNode,
  onSelectCard,
  onSaved,
  onRefresh,
  isRefreshing = false,
  title = '지금 해볼 작은 실험',
  kicker = '의미 네트워크가 제안하는 다음 선택',
  showEvidence = true,
  source = 'unknown',
}) => {
  const [draft, setDraft] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [saveResult, setSaveResult] = useState(null);
  const [saveMessage, setSaveMessage] = useState('');
  const [error, setError] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const recommendationKeyRef = useRef('');

  useEffect(() => {
    const nextKey = recommendation?.anchorCard?.id || '';
    const anchorChanged = recommendationKeyRef.current !== nextKey;
    recommendationKeyRef.current = nextKey;

    if (anchorChanged || !isDirty) {
      setDraft(recommendation?.experiment || '');
      setIsDirty(false);
    }
    setIsSaved(false);
    setSaveResult(null);
    setSaveMessage('');
    setError('');
  }, [isDirty, recommendation?.anchorCard?.id, recommendation?.experiment]);

  if (!recommendation || recommendation.status !== 'ready') {
    return null;
  }

  const { anchorCard, relatedCards, reason, reflectionQuestion } = recommendation;
  const visibleCards = relatedCards.slice(0, MAX_VISIBLE_CARDS);
  const hiddenCount = Math.max(0, relatedCards.length - visibleCards.length);

  const handleSave = async () => {
    if (!anchorCard?.id || !draft.trim()) return;

    setIsSaving(true);
    setError('');
    try {
      const response = await fetchWithAuth('/api/intentions', {
        method: 'POST',
        token,
        headers: {
          'Content-Type': 'application/json',
          'X-Logos-Action-Source': source,
        },
        body: JSON.stringify({
          card_id: anchorCard.id,
          intention: draft.trim(),
          source,
        }),
      });

      if (!response.ok) {
        throw await apiResponseError(response, '작은 실험을 담아두지 못했습니다.');
      }

      const savedIntention = await responseJsonOrNull(response);
      setIsSaved(true);
      setSaveResult(savedIntention?.was_duplicate ? 'duplicate' : 'saved');
      setSaveMessage(describeSavedIntention(savedIntention));
      onSaved && onSaved(savedIntention);
    } catch (err) {
      console.error('Error saving recommended experiment:', err);
      setError(err.message || '저장 중 오류가 발생했습니다.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRefresh = () => {
    if (!onRefresh || isRefreshing || isSaving) return;
    setIsDirty(false);
    setIsSaved(false);
    setSaveResult(null);
    setSaveMessage('');
    setError('');
    onRefresh();
  };

  return (
    <section
      className="recommended-experiment-panel glass-panel animate-fade-in"
      aria-label="지금 해볼 작은 실험"
    >
      <div className="recommended-experiment-copy">
        <div className="recommended-experiment-kicker">
          <Sparkles size={16} />
          <span>{kicker}</span>
        </div>
        <h2>{title}</h2>
        <p className="recommended-experiment-reason">{reason}</p>
      </div>

      <div className="recommended-experiment-editor">
        <label htmlFor="recommended-experiment-draft">이번 주 실험</label>
        <textarea
          id="recommended-experiment-draft"
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setIsDirty(true);
            if (isSaved) {
              setIsSaved(false);
              setSaveResult(null);
              setSaveMessage('');
            }
          }}
          disabled={isSaving}
          rows={2}
        />
        <p className="recommended-experiment-question">{reflectionQuestion}</p>
      </div>

      {showEvidence && visibleCards.length > 0 && (
        <div className="recommended-experiment-evidence" aria-label="관련 가치 카드">
          {visibleCards.map((card) => {
            const isActive = selectedNode?.id === card.id;
            return (
              <button
                key={card.id}
                type="button"
                className={`recommended-experiment-chip ${isActive ? 'active' : ''}`}
                onClick={() => onSelectCard && onSelectCard(card)}
                aria-pressed={isActive}
              >
                {card.keyword}
              </button>
            );
          })}
          {hiddenCount > 0 && (
            <span className="recommended-experiment-more">+{hiddenCount}</span>
          )}
        </div>
      )}

      {error && (
        <p className="recommended-experiment-error" role="alert">{error}</p>
      )}

      {saveMessage && (
        <p className="recommended-experiment-success" role="status" aria-live="polite">
          {saveMessage}
        </p>
      )}

      <div className="recommended-experiment-actions">
        {onRefresh && (
          <button
            type="button"
            className="recommended-experiment-refresh"
            onClick={handleRefresh}
            disabled={isRefreshing || isSaving}
            title="같은 가치 카드 흐름으로 다른 실험을 제안받기"
          >
            <RotateCcw className={isRefreshing ? 'animate-spin' : ''} size={15} />
            {isRefreshing ? '제안 중' : '다시 제안'}
          </button>
        )}

        <button
          type="button"
          className="recommended-experiment-save"
          onClick={handleSave}
          disabled={isSaving || isSaved || !draft.trim() || isRefreshing}
        >
          {isSaving ? (
            <>
              <Loader2 className="animate-spin" size={16} />
              담는 중
            </>
          ) : (
            <>
              <Check size={16} />
              {isSaved
                ? (saveResult === 'duplicate' ? '이미 담긴 실험입니다' : '담아두었습니다')
                : '이번 주 실험으로 담기'}
            </>
          )}
        </button>
      </div>
    </section>
  );
};

export default RecommendedExperiment;
