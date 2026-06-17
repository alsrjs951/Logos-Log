import assert from 'node:assert/strict';
import test from 'node:test';
import { apiErrorMessage, apiResponseError, responseJsonOrNull } from './apiErrors.js';

test('서버 detail 문자열을 우선 오류 메시지로 사용한다', async () => {
  const response = new Response(JSON.stringify({
    detail: '이미 처리된 실험입니다. 행동 루프를 새로고침해 주세요.',
  }), {
    status: 409,
    headers: { 'Content-Type': 'application/json' },
  });

  assert.equal(
    await apiErrorMessage(response, '기본 오류'),
    '이미 처리된 실험입니다. 행동 루프를 새로고침해 주세요.',
  );
});

test('검증 오류 배열에서는 첫 메시지를 사용한다', async () => {
  const response = new Response(JSON.stringify({
    detail: [{ msg: '결과 내용이 비어 있습니다.' }],
  }), {
    status: 422,
    headers: { 'Content-Type': 'application/json' },
  });

  assert.equal(await apiErrorMessage(response, '기본 오류'), '결과 내용이 비어 있습니다.');
});

test('본문이 비었거나 JSON이 아니면 fallback을 반환한다', async () => {
  const response = new Response('temporarily unavailable', { status: 503 });

  assert.equal(await apiErrorMessage(response, '잠시 후 다시 시도해 주세요.'), '잠시 후 다시 시도해 주세요.');
});

test('apiResponseError는 메시지와 상태 코드, 요청 ID를 함께 보존한다', async () => {
  const response = new Response(JSON.stringify({ detail: '이미 처리된 실험입니다.' }), {
    status: 409,
    headers: { 'Content-Type': 'application/json' },
  });
  response.logosRequestId = 'web:test-request';

  const error = await apiResponseError(response, '기본 오류');

  assert.equal(error.message, '이미 처리된 실험입니다.');
  assert.equal(error.status, 409);
  assert.equal(error.requestId, 'web:test-request');
});

test('responseJsonOrNull은 JSON 본문만 객체로 반환한다', async () => {
  const response = new Response(JSON.stringify({ ok: true }), {
    headers: { 'Content-Type': 'application/json' },
  });

  assert.deepEqual(await responseJsonOrNull(response), { ok: true });
});

test('responseJsonOrNull은 비어 있거나 JSON이 아닌 본문에서 null을 반환한다', async () => {
  assert.equal(await responseJsonOrNull(new Response(null, { status: 204 })), null);
  assert.equal(await responseJsonOrNull(new Response('not json')), null);
});
