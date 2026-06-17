export async function apiErrorMessage(response, fallback = '요청을 처리하지 못했습니다.') {
  if (!response) return fallback;

  try {
    const data = await response.json();
    const detail = data?.detail;

    if (typeof detail === 'string' && detail.trim()) {
      return detail.trim();
    }

    if (Array.isArray(detail) && detail.length > 0) {
      const firstMessage = detail
        .map((item) => item?.msg || item?.message)
        .find((message) => typeof message === 'string' && message.trim());
      if (firstMessage) return firstMessage.trim();
    }

    if (typeof data?.message === 'string' && data.message.trim()) {
      return data.message.trim();
    }
  } catch {
    // Keep the UI calm when the server returns an empty or non-JSON body.
  }

  return fallback;
}

export async function apiResponseError(response, fallback = '요청을 처리하지 못했습니다.') {
  const error = new Error(await apiErrorMessage(response, fallback));
  error.status = response?.status;
  error.requestId = response?.logosRequestId;
  return error;
}

export async function responseJsonOrNull(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
