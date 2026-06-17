import test from 'node:test';
import assert from 'node:assert/strict';
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
} from './intentionHistory.js';

test('실험 히스토리를 상태별로 요약하고 최근순으로 정렬한다', () => {
  const summary = summarizeIntentions([
    {
      id: 'old-open',
      status: 'open',
      created_at: '2026-06-01T00:00:00.000Z',
      intention: '오래된 열린 실험',
    },
    {
      id: 'reflected-high',
      status: 'reflected',
      created_at: '2026-06-02T00:00:00.000Z',
      outcome_logged_at: '2026-06-08T00:00:00.000Z',
      helpfulness: 5,
      intention: '도움된 실험',
    },
    {
      id: 'dismissed',
      status: 'dismissed',
      created_at: '2026-06-04T00:00:00.000Z',
      dismissed_at: '2026-06-09T00:00:00.000Z',
      intention: '접어둔 실험',
    },
  ]);

  assert.equal(summary.total, 3);
  assert.equal(summary.counts.open, 1);
  assert.equal(summary.counts.reflected, 1);
  assert.equal(summary.counts.dismissed, 1);
  assert.equal(summary.recent[0].id, 'dismissed');
  assert.equal(summary.recent[1].id, 'reflected-high');
  assert.equal(summary.mostHelpful[0].id, 'reflected-high');
});

test('상태 메타와 날짜 포맷을 반환한다', () => {
  assert.equal(getIntentionStatusMeta('open').label, '진행 중');
  assert.equal(getIntentionStatusMeta('reflected').tone, 'reflected');
  assert.equal(formatIntentionDate('2026-06-14T12:00:00.000Z'), '6/14');
  assert.equal(formatIntentionDate(''), '');
  assert.equal(intentionActivityAt({
    created_at: '2026-06-01T00:00:00.000Z',
    dismissed_at: '2026-06-09T00:00:00.000Z',
  }), '2026-06-09T00:00:00.000Z');
});

test('회고 비율을 부담 없는 표시값으로 변환한다', () => {
  assert.equal(formatIntentionRate(2 / 3), '67%');
  assert.equal(formatIntentionRate(null), '-');
  assert.equal(formatIntentionRate(Number.NaN), '-');
  assert.equal(formatIntentionRate(1.4), '100%');
});

test('돌아볼 실험 상태를 짧게 표시한다', () => {
  assert.equal(formatReviewQueue({ due_count: 2 }), '2개 가능');
  assert.equal(formatReviewQueue({
    due_count: 0,
    next_review_available_at: '2026-06-18T12:00:00.000Z',
  }), '6/18 예정');
  assert.equal(formatReviewQueue({ due_count: 0 }), '-');
});

test('열린 실험의 돌아보기 가능 시점을 설명한다', () => {
  assert.equal(describeReviewTiming({
    status: 'open',
    is_due: true,
    review_available_at: '2026-06-17T12:00:00.000Z',
  }), '돌아보기 가능');
  assert.equal(describeReviewTiming({
    status: 'open',
    is_due: false,
    review_available_at: '2026-06-17T12:00:00.000Z',
  }), '6/17부터 돌아보기');
  assert.equal(describeReviewTiming({ status: 'reflected' }), '');
});

test('저장된 실험의 다음 회고 시점을 안내한다', () => {
  assert.equal(describeSavedIntention({
    was_duplicate: false,
    is_due: false,
    review_available_at: '2026-06-17T12:00:00.000Z',
  }), '실험을 담아두었습니다. 6/17부터 대시보드에서 돌아볼 수 있어요.');

  assert.equal(describeSavedIntention({
    was_duplicate: true,
    is_due: false,
    review_available_at: '2026-06-17T12:00:00.000Z',
  }), '이미 담긴 실험입니다. 6/17부터 대시보드에서 돌아볼 수 있어요.');

  assert.equal(describeSavedIntention({
    was_duplicate: false,
    is_due: true,
  }), '실험을 담아두었습니다. 지금 대시보드에서 돌아볼 수 있어요.');

  assert.equal(
    describeSavedIntention(null),
    '실험을 담아두었습니다. 며칠 뒤 대시보드에서 돌아볼 수 있어요.'
  );
});

test('회고 루프 완료 상태를 부담 없는 문장으로 안내한다', () => {
  assert.equal(
    describeActionLoopCompletion('reflected', { helpfulness: 4 }),
    '회고를 기록했습니다. 도움 4/5도 함께 저장했어요. 이 선택이 다음 실험의 근거로 남았어요.'
  );
  assert.equal(
    describeActionLoopCompletion('reflected', {}),
    '회고를 기록했습니다. 이 선택이 다음 실험의 근거로 남았어요.'
  );
  assert.equal(
    describeActionLoopCompletion('dismissed'),
    '실험을 접어두었습니다. 실패가 아니라 지금은 이어가지 않기로 한 선택으로 남겼어요.'
  );
  assert.equal(describeActionLoopCompletion('unknown'), '');
});
