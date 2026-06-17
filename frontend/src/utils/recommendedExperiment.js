const VALUE_LABELS_KR = {
  self_direction: '자기주도',
  stimulation: '자극',
  hedonism: '쾌락',
  achievement: '성취',
  power: '권력',
  security: '안전',
  conformity: '순응',
  tradition: '전통',
  benevolence: '박애',
  universalism: '보편주의',
};

const VALUE_TEMPLATES = {
  self_direction: {
    experiment: '이번 주에 남의 기대와 내가 원하는 선택을 한 줄씩 분리해 적고, 부담이 낮은 작은 선택 하나를 직접 골라보세요.',
    reflectionQuestion: '그 선택은 “내가 원해서 고른 것”이라는 감각을 조금 더 선명하게 만들었나요?',
  },
  achievement: {
    experiment: '이번 주에 해야 할 일 하나를 30분 안에 끝낼 수 있는 가장 작은 기준으로 낮춰 완료해보세요.',
    reflectionQuestion: '작게 끝낸 경험이 성취감을 압박이 아니라 움직임으로 느끼게 했나요?',
  },
  benevolence: {
    experiment: '이번 주에 가까운 사람 한 명에게 고마움이나 도움 요청을 짧게 표현해보세요.',
    reflectionQuestion: '그 표현이 관계 안에서 혼자 버티는 느낌을 조금 덜어주었나요?',
  },
  security: {
    experiment: '이번 주에 불안을 줄여줄 지원 자원 하나를 확인해 적어두세요. 사람, 일정, 정보 중 하나면 충분합니다.',
    reflectionQuestion: '확인해 둔 지원 자원이 마음의 여유를 조금 만들어주었나요?',
  },
  conformity: {
    experiment: '이번 주에 타인의 기대와 내 선택을 구분해 적고, 부담이 낮은 요청 하나를 정중히 거절해보세요.',
    reflectionQuestion: '그 거절은 관계를 끊는 일이 아니라 내 경계를 설명하는 일처럼 느껴졌나요?',
  },
  universalism: {
    experiment: '이번 주에 나 밖의 대상에게 작은 기여 하나를 해보세요. 공유, 도움, 정리, 배려 중 하나면 충분합니다.',
    reflectionQuestion: '그 작은 기여가 내 삶이 더 넓은 맥락과 연결되어 있다는 감각을 주었나요?',
  },
};

const AUTONOMY_WORDS = ['자율성', '자유', '선택', '독립', '주도'];
const SELF_UNDERSTANDING_WORDS = ['자기 이해', '자기이해', '나를 이해', '내 마음', '내가 원하는', '무엇을 원하는', '원하는지'];

const normalizeKeyword = (value) => String(value || '').trim().toLowerCase();

export const cardGroupKey = (card) => card?.canonical_value || normalizeKeyword(card?.keyword);

const parseDate = (card) => {
  const timestamp = Date.parse(card?.created_at || '');
  return Number.isNaN(timestamp) ? 0 : timestamp;
};

const newestFirst = (cards) => [...cards].sort((a, b) => parseDate(b) - parseDate(a));

const includesAny = (text, words) => {
  const source = normalizeKeyword(text);
  return words.some((word) => source.includes(normalizeKeyword(word)));
};

const cardText = (card) => `${card?.keyword || ''} ${card?.insight || ''}`;

const hasAutonomyAndSelfUnderstanding = (cards) => {
  const hasAutonomy = cards.some((card) => includesAny(cardText(card), AUTONOMY_WORDS));
  const hasSelfUnderstanding = cards.some((card) => includesAny(cardText(card), SELF_UNDERSTANDING_WORDS));
  return hasAutonomy && hasSelfUnderstanding;
};

const fallbackTemplate = (anchorCard) => {
  const keyword = anchorCard?.keyword || '이 가치';
  return {
    experiment: `이번 주에 ‘${keyword}’이라는 가치를 드러내는 작은 행동 하나를 직접 정해 실행해보세요.`,
    reflectionQuestion: `그 행동이 ‘${keyword}’을 말이 아니라 실제 선택으로 느끼게 했나요?`,
  };
};

const buildReason = (anchorCard, relatedCards) => {
  const keyword = anchorCard?.keyword || '최근 가치';
  if (relatedCards.length <= 1) {
    return `최근 저장한 ‘${keyword}’ 카드에서 출발한 작은 실험입니다.`;
  }

  const label = VALUE_LABELS_KR[anchorCard?.canonical_value] || keyword;
  return `‘${label}’ 흐름에 묶인 ${relatedCards.length}개의 가치 카드가 반복되어, 이해보다 실행을 먼저 돕는 작은 실험으로 바꿨습니다.`;
};

/**
 * @typedef {Object} RecommendedExperiment
 * @property {'ready'|'empty'} status
 * @property {Object|null} anchorCard
 * @property {Object[]} relatedCards
 * @property {string} reason
 * @property {string} experiment
 * @property {string} reflectionQuestion
 */

export const buildRecommendedExperiment = (cardsInput) => {
  const cards = newestFirst(Array.isArray(cardsInput) ? cardsInput.filter(Boolean) : []);

  if (cards.length === 0) {
    return {
      status: 'empty',
      anchorCard: null,
      relatedCards: [],
      reason: '아직 추천할 가치 카드가 없습니다.',
      experiment: '',
      reflectionQuestion: '',
    };
  }

  const anchorCard = cards.find((card) => card?.canonical_value) || cards[0];
  const anchorGroupKey = cardGroupKey(anchorCard);
  const relatedCards = cards.filter((card) => cardGroupKey(card) === anchorGroupKey);

  const template = hasAutonomyAndSelfUnderstanding(relatedCards)
    ? {
        experiment: '이번 주에 남의 기대와 내가 원하는 선택을 분리해 적고, 부담이 낮은 작은 선택 하나를 직접 골라보세요.',
        reflectionQuestion: '그 선택은 자유롭게 행동하기 전에 “내가 무엇을 원하는지”를 더 분명하게 해주었나요?',
      }
    : VALUE_TEMPLATES[anchorCard?.canonical_value] || fallbackTemplate(anchorCard);

  return {
    status: 'ready',
    anchorCard,
    relatedCards,
    reason: buildReason(anchorCard, relatedCards),
    experiment: template.experiment,
    reflectionQuestion: template.reflectionQuestion,
  };
};

export const applyRecommendedExperimentOverride = (baseRecommendation, apiRecommendation, cardsInput) => {
  if (!baseRecommendation || baseRecommendation.status !== 'ready') return baseRecommendation;
  if (!apiRecommendation || apiRecommendation.status !== 'ready') return baseRecommendation;
  if (!apiRecommendation.experiment || !String(apiRecommendation.experiment).trim()) {
    return baseRecommendation;
  }

  const cards = Array.isArray(cardsInput) ? cardsInput.filter(Boolean) : [];
  const byId = new Map(cards.map((card) => [card.id, card]));
  const anchorCard = byId.get(apiRecommendation.anchor_card_id) || baseRecommendation.anchorCard;
  const relatedCards = Array.isArray(apiRecommendation.related_card_ids)
    ? apiRecommendation.related_card_ids.map((id) => byId.get(id)).filter(Boolean)
    : [];

  return {
    ...baseRecommendation,
    anchorCard,
    relatedCards: relatedCards.length > 0 ? relatedCards : baseRecommendation.relatedCards,
    reason: String(apiRecommendation.reason || baseRecommendation.reason).trim(),
    experiment: String(apiRecommendation.experiment).trim(),
    reflectionQuestion: String(
      apiRecommendation.reflection_question || baseRecommendation.reflectionQuestion
    ).trim(),
    source: apiRecommendation.source || 'llm',
    cacheKey: apiRecommendation.cache_key || null,
  };
};

export const describeCardRecommendationRole = (card, recommendation) => {
  if (!card || !recommendation || recommendation.status !== 'ready') {
    return '아직 이 노드를 바탕으로 제안할 작은 실험이 충분하지 않습니다.';
  }

  if (recommendation.anchorCard?.id === card.id) {
    return '이 노드는 이번 작은 실험을 정할 때 기준으로 삼은 최근 가치 카드입니다.';
  }

  if (recommendation.relatedCards.some((related) => related.id === card.id)) {
    return '이 노드는 같은 가치 흐름에 묶여 이번 작은 실험의 근거로 함께 사용되었습니다.';
  }

  return '이 노드는 현재 추천의 직접 근거는 아니지만, 다음 실험을 조정할 때 함께 참고할 수 있는 별도 성찰입니다.';
};

export const isRecommendationCard = (card, recommendation) => (
  Boolean(card && recommendation?.relatedCards?.some((related) => related.id === card.id))
);
