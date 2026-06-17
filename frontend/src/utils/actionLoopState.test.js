import test from 'node:test';
import assert from 'node:assert/strict';
import { buildActionLoopState } from './actionLoopState.js';

const card = (patch) => ({
  id: patch.id,
  keyword: patch.keyword,
  insight: patch.insight || '',
  canonical_value: patch.canonical_value,
  created_at: patch.created_at || '2026-06-01T00:00:00.000Z',
});

test('due intention이 있으면 추천보다 회고 상태가 우선된다', () => {
  const result = buildActionLoopState({
    dueIntentions: [{ id: 'due-1', intention: '작은 선택을 직접 해본다.' }],
    cards: [
      card({ id: 'card-1', keyword: '자율성', canonical_value: 'self_direction' }),
    ],
  });

  assert.equal(result.status, 'review');
  assert.equal(result.activeIntention.id, 'due-1');
  assert.equal(result.recommendation, null);
});

test('due가 없고 가치 카드가 있으면 추천 실험 상태가 된다', () => {
  const result = buildActionLoopState({
    dueIntentions: [],
    cards: [
      card({ id: 'card-1', keyword: '성취', canonical_value: 'achievement' }),
    ],
  });

  assert.equal(result.status, 'recommendation');
  assert.equal(result.recommendation.status, 'ready');
  assert.equal(result.recommendation.anchorCard.id, 'card-1');
});

test('due가 없고 LLM 추천이 있으면 추천 문구가 LLM 응답으로 대체된다', () => {
  const result = buildActionLoopState({
    dueIntentions: [],
    cards: [
      card({ id: 'card-1', keyword: '성취', canonical_value: 'achievement' }),
    ],
    recommendationOverride: {
      status: 'ready',
      anchor_card_id: 'card-1',
      related_card_ids: ['card-1'],
      reason: '최근 성취 카드에서 완성보다 시작이 중요해 보입니다.',
      experiment: '이번 주에 15분짜리 작업 하나를 끝까지 완성하지 않아도 시작만 해보세요.',
      reflection_question: '작게 시작한 경험이 부담을 낮췄나요?',
      source: 'llm',
    },
  });

  assert.equal(result.status, 'recommendation');
  assert.equal(result.recommendation.source, 'llm');
  assert.match(result.recommendation.experiment, /15분짜리 작업/);
});

test('due도 카드도 없으면 empty 안내 상태가 된다', () => {
  const result = buildActionLoopState({ dueIntentions: [], cards: [] });

  assert.equal(result.status, 'empty');
  assert.equal(result.activeIntention, null);
  assert.equal(result.recommendation.status, 'empty');
});
