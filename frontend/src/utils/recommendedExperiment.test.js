import test from 'node:test';
import assert from 'node:assert/strict';
import {
  applyRecommendedExperimentOverride,
  buildRecommendedExperiment,
  cardGroupKey,
} from './recommendedExperiment.js';

const card = (patch) => ({
  id: patch.id,
  keyword: patch.keyword,
  insight: patch.insight || '',
  canonical_value: patch.canonical_value,
  created_at: patch.created_at || '2026-06-01T00:00:00.000Z',
});

test('자율성 + 자기 이해 흐름이면 전용 작은 실험을 반환한다', () => {
  const result = buildRecommendedExperiment([
    card({
      id: 'a',
      keyword: '자율성',
      insight: '나는 남의 기대보다 내가 직접 고르는 선택이 필요하다.',
      canonical_value: 'self_direction',
      created_at: '2026-06-01T00:00:00.000Z',
    }),
    card({
      id: 'b',
      keyword: '자기 이해',
      insight: '내가 무엇을 원하는지 먼저 이해하고 싶다.',
      canonical_value: 'self_direction',
      created_at: '2026-06-03T00:00:00.000Z',
    }),
  ]);

  assert.equal(result.status, 'ready');
  assert.equal(result.relatedCards.length, 2);
  assert.match(result.experiment, /남의 기대와 내가 원하는 선택/);
  assert.match(result.reflectionQuestion, /내가 무엇을 원하는지/);
});

test('카드가 1개뿐이어도 해당 카드 기반 추천을 반환한다', () => {
  const result = buildRecommendedExperiment([
    card({
      id: 'one',
      keyword: '성취',
      canonical_value: 'achievement',
    }),
  ]);

  assert.equal(result.status, 'ready');
  assert.equal(result.anchorCard.id, 'one');
  assert.deepEqual(result.relatedCards.map((item) => item.id), ['one']);
  assert.match(result.experiment, /30분 안에 끝낼 수 있는/);
});

test('canonical 값이 없으면 keyword 기준으로 연결한다', () => {
  const result = buildRecommendedExperiment([
    card({
      id: 'old',
      keyword: '관계',
      created_at: '2026-06-01T00:00:00.000Z',
    }),
    card({
      id: 'new',
      keyword: '관계',
      created_at: '2026-06-04T00:00:00.000Z',
    }),
  ]);

  assert.equal(cardGroupKey(result.anchorCard), '관계');
  assert.deepEqual(result.relatedCards.map((item) => item.id), ['new', 'old']);
  assert.match(result.experiment, /‘관계’이라는 가치를 드러내는 작은 행동/);
});

test('카드가 없으면 empty state를 반환한다', () => {
  const result = buildRecommendedExperiment([]);

  assert.equal(result.status, 'empty');
  assert.equal(result.anchorCard, null);
  assert.deepEqual(result.relatedCards, []);
  assert.equal(result.experiment, '');
});

test('LLM 추천 응답이 있으면 기본 실험 문구를 덮어쓴다', () => {
  const cards = [
    card({
      id: 'card-1',
      keyword: '자율성',
      canonical_value: 'self_direction',
    }),
  ];
  const base = buildRecommendedExperiment(cards);
  const result = applyRecommendedExperimentOverride(base, {
    status: 'ready',
    anchor_card_id: 'card-1',
    related_card_ids: ['card-1'],
    reason: '최근 자율성 카드에서 선택의 감각이 반복됩니다.',
    experiment: '이번 주에 점심 메뉴처럼 작고 안전한 선택 하나를 남의 의견 없이 골라보세요.',
    reflection_question: '직접 고른 선택이 내 하루의 주도감을 조금 바꿨나요?',
    source: 'llm_cache',
    cache_key: 'meaning-action-v2:abc123',
  }, cards);

  assert.equal(result.source, 'llm_cache');
  assert.equal(result.cacheKey, 'meaning-action-v2:abc123');
  assert.equal(result.anchorCard.id, 'card-1');
  assert.match(result.experiment, /점심 메뉴처럼 작고 안전한 선택/);
  assert.match(result.reflectionQuestion, /주도감/);
});
