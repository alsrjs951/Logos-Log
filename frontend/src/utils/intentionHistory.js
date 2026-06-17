const STATUS_META = {
  open: {
    label: '진행 중',
    tone: 'open',
  },
  reflected: {
    label: '회고 완료',
    tone: 'reflected',
  },
  dismissed: {
    label: '접어둠',
    tone: 'dismissed',
  },
};

const parseDate = (value) => {
  const timestamp = Date.parse(value || '');
  return Number.isNaN(timestamp) ? 0 : timestamp;
};

export const intentionActivityAt = (intention) => (
  intention?.outcome_logged_at
  || intention?.dismissed_at
  || intention?.created_at
);

export const getIntentionStatusMeta = (status) => (
  STATUS_META[status] || {
    label: '기록됨',
    tone: 'unknown',
  }
);

export const summarizeIntentions = (intentionsInput) => {
  const intentions = Array.isArray(intentionsInput)
    ? intentionsInput.filter(Boolean)
    : [];

  const sorted = [...intentions].sort((a, b) => {
    const primary = parseDate(intentionActivityAt(b))
      - parseDate(intentionActivityAt(a));
    if (primary !== 0) return primary;
    return String(a.id || '').localeCompare(String(b.id || ''));
  });

  const counts = sorted.reduce((acc, intention) => {
    const status = intention.status || 'unknown';
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, { open: 0, reflected: 0, dismissed: 0 });

  const helpful = sorted
    .filter((intention) => (
      intention.status === 'reflected'
      && typeof intention.helpfulness === 'number'
    ))
    .sort((a, b) => b.helpfulness - a.helpfulness);

  return {
    total: sorted.length,
    counts,
    recent: sorted.slice(0, 5),
    mostHelpful: helpful.slice(0, 3),
  };
};

export const formatIntentionDate = (value) => {
  const timestamp = parseDate(value);
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return `${date.getMonth() + 1}/${date.getDate()}`;
};

export const formatIntentionRate = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-';
  const bounded = Math.max(0, Math.min(1, value));
  return `${Math.round(bounded * 100)}%`;
};

export const formatReviewQueue = (stats) => {
  const dueCount = Number(stats?.due_count || 0);
  if (dueCount > 0) return `${dueCount}개 가능`;

  const nextReviewDate = formatIntentionDate(stats?.next_review_available_at);
  return nextReviewDate ? `${nextReviewDate} 예정` : '-';
};

export const describeReviewTiming = (intention) => {
  if (!intention || intention.status !== 'open') return '';
  if (intention.is_due) return '돌아보기 가능';

  const reviewDate = formatIntentionDate(intention.review_available_at);
  return reviewDate ? `${reviewDate}부터 돌아보기` : '';
};

export const describeSavedIntention = (intention) => {
  const prefix = intention?.was_duplicate
    ? '이미 담긴 실험입니다.'
    : '실험을 담아두었습니다.';

  if (intention?.is_due) {
    return `${prefix} 지금 대시보드에서 돌아볼 수 있어요.`;
  }

  const reviewDate = formatIntentionDate(intention?.review_available_at);
  if (reviewDate) {
    return `${prefix} ${reviewDate}부터 대시보드에서 돌아볼 수 있어요.`;
  }

  return `${prefix} 며칠 뒤 대시보드에서 돌아볼 수 있어요.`;
};

export const describeActionLoopCompletion = (action, intention) => {
  if (action === 'reflected') {
    const helpfulness = typeof intention?.helpfulness === 'number'
      ? ` 도움 ${intention.helpfulness}/5도 함께 저장했어요.`
      : '';
    return `회고를 기록했습니다.${helpfulness} 이 선택이 다음 실험의 근거로 남았어요.`;
  }

  if (action === 'dismissed') {
    return '실험을 접어두었습니다. 실패가 아니라 지금은 이어가지 않기로 한 선택으로 남겼어요.';
  }

  return '';
};
