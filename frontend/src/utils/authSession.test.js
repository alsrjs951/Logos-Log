import assert from 'node:assert/strict';
import test from 'node:test';

import {
  REQUEST_ID_HEADER,
  clearAuthSession,
  fetchApi,
  fetchWithAuth,
  getStoredAccessToken,
  getStoredUserEmail,
  requestIdFromHeaders,
  storeAuthSession,
} from '../api.js';

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

test('auth session keeps access token in memory and clears legacy storage', (t) => {
  const previousWindow = globalThis.window;
  t.after(() => {
    if (previousWindow === undefined) {
      delete globalThis.window;
    } else {
      globalThis.window = previousWindow;
    }
  });

  const localStorage = createStorage();
  localStorage.setItem('access_token', 'legacy-token');
  localStorage.setItem('user_email', 'legacy@example.com');
  globalThis.window = {
    localStorage,
    dispatchEvent: () => {},
  };

  storeAuthSession('memory-token', 'user@example.com');

  assert.equal(getStoredAccessToken(), 'memory-token');
  assert.equal(getStoredUserEmail(), 'user@example.com');
  assert.equal(localStorage.getItem('access_token'), null);
  assert.equal(localStorage.getItem('user_email'), null);

  clearAuthSession();

  assert.equal(getStoredAccessToken(), null);
  assert.equal(getStoredUserEmail(), null);
});

test('fetchApi attaches request ID header and exposes it on the response', async (t) => {
  const previousFetch = globalThis.fetch;
  let observedHeaders = null;
  t.after(() => {
    globalThis.fetch = previousFetch;
  });

  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'http://localhost:8000/api/ping');
    observedHeaders = new Headers(options.headers);
    return new Response(null, { status: 204 });
  };

  const response = await fetchApi('/api/ping', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  const requestId = observedHeaders.get(REQUEST_ID_HEADER);
  assert.match(requestId, /^web:/);
  assert.equal(observedHeaders.get('Content-Type'), 'application/json');
  assert.equal(response.logosRequestId, requestId);
});

test('fetchApi adds request ID to network errors', async (t) => {
  const previousFetch = globalThis.fetch;
  let observedRequestId = null;
  t.after(() => {
    globalThis.fetch = previousFetch;
  });

  globalThis.fetch = async (_url, options) => {
    observedRequestId = requestIdFromHeaders(options.headers);
    throw new TypeError('network down');
  };

  await assert.rejects(
    () => fetchApi('/api/ping'),
    (error) => {
      assert.equal(error.logosRequestId, observedRequestId);
      return true;
    },
  );
});

test('fetchWithAuth keeps the original request ID on unauthorized retry', async (t) => {
  const previousFetch = globalThis.fetch;
  const calls = [];
  t.after(() => {
    globalThis.fetch = previousFetch;
    clearAuthSession();
  });

  globalThis.fetch = async (url, options) => {
    calls.push({ url, headers: new Headers(options.headers) });

    if (calls.length === 1) {
      return new Response(null, { status: 401 });
    }

    if (url.endsWith('/api/auth/refresh')) {
      return new Response(JSON.stringify({
        access_token: 'new-access-token',
        user: { email: 'user@example.com' },
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  const response = await fetchWithAuth('/api/private', { token: 'old-access-token' });

  assert.equal(response.status, 200);
  assert.equal(calls.length, 3);
  const originalRequestId = calls[0].headers.get(REQUEST_ID_HEADER);
  assert.match(originalRequestId, /^web:/);
  assert.match(calls[1].headers.get(REQUEST_ID_HEADER), /^web:/);
  assert.equal(calls[2].headers.get(REQUEST_ID_HEADER), originalRequestId);
  assert.equal(calls[0].headers.get('Authorization'), 'Bearer old-access-token');
  assert.equal(calls[2].headers.get('Authorization'), 'Bearer new-access-token');
});
