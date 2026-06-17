import assert from 'node:assert/strict';
import test from 'node:test';
import { hasCompletedOnboarding, markOnboardingComplete } from './onboardingState.js';

const createStorage = () => {
  const data = new Map();
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, String(value)),
  };
};

test('온보딩 완료 상태를 저장하고 읽는다', () => {
  const storage = createStorage();

  assert.equal(hasCompletedOnboarding(storage), false);
  assert.equal(markOnboardingComplete(storage), true);
  assert.equal(hasCompletedOnboarding(storage), true);
});

test('storage 읽기가 실패하면 온보딩 미완료로 안전하게 처리한다', () => {
  const storage = {
    getItem: () => {
      throw new Error('storage blocked');
    },
    setItem: () => {},
  };

  assert.equal(hasCompletedOnboarding(storage), false);
});

test('storage 쓰기가 실패해도 완료 처리 호출은 앱 흐름을 깨지 않는다', () => {
  const storage = {
    getItem: () => null,
    setItem: () => {
      throw new Error('storage blocked');
    },
  };

  assert.equal(markOnboardingComplete(storage), false);
});
