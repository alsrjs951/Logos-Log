const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
export const AUTH_TOKEN_REFRESHED_EVENT = 'logos_auth_token_refreshed';
export const AUTH_SESSION_EXPIRED_EVENT = 'logos_auth_session_expired';
export const REQUEST_ID_HEADER = 'X-Request-ID';

let memoryAccessToken = null;
let memoryUserEmail = null;

export function apiUrl(path) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

export function createRequestId() {
  if (globalThis.crypto?.randomUUID) {
    return `web:${globalThis.crypto.randomUUID()}`;
  }

  const randomPart = globalThis.crypto?.getRandomValues
    ? Array.from(globalThis.crypto.getRandomValues(new Uint32Array(2)), (value) => value.toString(36)).join('')
    : Math.random().toString(36).slice(2);

  return `web:${Date.now().toString(36)}:${randomPart}`;
}

function headersWithRequestId(headers, requestId = createRequestId()) {
  const nextHeaders = new Headers(headers || {});
  if (!nextHeaders.has(REQUEST_ID_HEADER)) {
    nextHeaders.set(REQUEST_ID_HEADER, requestId);
  }
  return nextHeaders;
}

async function trackedFetch(url, options, requestId) {
  try {
    const response = await fetch(url, options);
    response.logosRequestId = requestId;
    return response;
  } catch (error) {
    error.logosRequestId = requestId;
    throw error;
  }
}

export function requestIdFromHeaders(headers) {
  return new Headers(headers || {}).get(REQUEST_ID_HEADER);
}

export async function fetchApi(path, options = {}) {
  const headers = headersWithRequestId(options.headers);
  const requestId = requestIdFromHeaders(headers);
  return trackedFetch(apiUrl(path), {
    ...options,
    headers,
    credentials: options.credentials || 'include',
  }, requestId);
}

const getStorage = () => {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

const dispatchAuthEvent = (eventName, detail = {}) => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(eventName, { detail }));
};

export function getStoredAccessToken() {
  return memoryAccessToken;
}

export function getStoredUserEmail() {
  return memoryUserEmail;
}

export function clearPersistedAuthCredentials() {
  const storage = getStorage();
  storage?.removeItem('access_token');
  storage?.removeItem('user_email');
}

export function clearTransientAuthSession() {
  memoryAccessToken = null;
  memoryUserEmail = null;
}

export function storeAuthSession(accessToken, email, { emit = false } = {}) {
  if (!accessToken) return;
  memoryAccessToken = accessToken;
  if (email) {
    memoryUserEmail = email;
  }
  clearPersistedAuthCredentials();

  if (emit) {
    dispatchAuthEvent(AUTH_TOKEN_REFRESHED_EVENT, { accessToken, email });
  }
}

export function clearAuthSession() {
  clearTransientAuthSession();
  const storage = getStorage();
  clearPersistedAuthCredentials();
  storage?.removeItem('analyzed_journal_ids');
}

export async function refreshAccessToken({ emit = true } = {}) {
  const response = await fetchApi('/api/auth/refresh', {
    method: 'POST',
  });
  if (!response.ok) {
    clearTransientAuthSession();
    return null;
  }

  const data = await response.json().catch(() => null);
  if (!data?.access_token) {
    clearTransientAuthSession();
    return null;
  }

  storeAuthSession(data.access_token, data.user?.email, { emit });
  return data;
}

export async function fetchWithAuth(path, options = {}) {
  const {
    token,
    onToken,
    onUnauthorized,
    retryOnUnauthorized = true,
    ...fetchOptions
  } = options;
  const authToken = getStoredAccessToken() || token;

  const headers = headersWithRequestId(fetchOptions.headers);
  const requestId = requestIdFromHeaders(headers);
  if (authToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }

  const response = await trackedFetch(apiUrl(path), {
    ...fetchOptions,
    headers,
    credentials: fetchOptions.credentials || 'include',
  }, requestId);

  if (response.status !== 401 || !retryOnUnauthorized) {
    return response;
  }

  const refreshed = await refreshAccessToken();
  if (!refreshed?.access_token) {
    if (onUnauthorized) {
      onUnauthorized();
    } else {
      dispatchAuthEvent(AUTH_SESSION_EXPIRED_EVENT);
    }
    return response;
  }

  onToken && onToken(refreshed.access_token, refreshed.user?.email);
  const retryHeaders = headersWithRequestId(fetchOptions.headers, requestId);
  retryHeaders.set('Authorization', `Bearer ${refreshed.access_token}`);
  return trackedFetch(apiUrl(path), {
    ...fetchOptions,
    headers: retryHeaders,
    credentials: fetchOptions.credentials || 'include',
  }, requestId);
}
