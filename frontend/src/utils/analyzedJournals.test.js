import assert from 'node:assert/strict';
import test from 'node:test';
import {
  addAnalyzedJournalId,
  getAnalyzedJournalIds,
  hasAnalyzedJournalId,
  removeAnalyzedJournalId,
  setAnalyzedJournalIds,
} from './analyzedJournals.js';

const createStorage = () => {
  const data = new Map();
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
  };
};

test('손상된 analyzed journal storage는 빈 목록으로 복구한다', () => {
  const storage = createStorage();
  storage.setItem('analyzed_journal_ids', '{not-json');

  assert.deepEqual(getAnalyzedJournalIds(storage), []);
  assert.equal(storage.getItem('analyzed_journal_ids'), null);
});

test('저장할 때 문자열 ID만 중복 없이 보존한다', () => {
  const storage = createStorage();

  const ids = setAnalyzedJournalIds(['journal-1', 'journal-1', '  journal-2  ', '', null], storage);

  assert.deepEqual(ids, ['journal-1', 'journal-2']);
  assert.deepEqual(JSON.parse(storage.getItem('analyzed_journal_ids')), ['journal-1', 'journal-2']);
});

test('분석 완료 ID를 추가하고 조회한다', () => {
  const storage = createStorage();

  addAnalyzedJournalId('journal-1', storage);
  addAnalyzedJournalId('journal-1', storage);

  assert.equal(hasAnalyzedJournalId('journal-1', storage), true);
  assert.deepEqual(getAnalyzedJournalIds(storage), ['journal-1']);
});

test('삭제된 일기 ID는 분석 완료 목록에서도 제거한다', () => {
  const storage = createStorage();
  setAnalyzedJournalIds(['journal-1', 'journal-2'], storage);

  assert.deepEqual(removeAnalyzedJournalId('journal-1', storage), ['journal-2']);
  assert.equal(hasAnalyzedJournalId('journal-1', storage), false);
  assert.equal(hasAnalyzedJournalId('journal-2', storage), true);
});

test('storage 접근이 실패해도 호출자는 안전한 값을 받는다', () => {
  const storage = {
    getItem: () => {
      throw new Error('storage blocked');
    },
    setItem: () => {
      throw new Error('storage blocked');
    },
    removeItem: () => {
      throw new Error('storage blocked');
    },
  };

  assert.deepEqual(getAnalyzedJournalIds(storage), []);
  assert.deepEqual(setAnalyzedJournalIds(['journal-1'], storage), ['journal-1']);
  assert.deepEqual(addAnalyzedJournalId('journal-1', storage), ['journal-1']);
});
