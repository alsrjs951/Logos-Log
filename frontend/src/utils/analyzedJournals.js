const ANALYZED_JOURNAL_IDS_KEY = 'analyzed_journal_ids';

const storageFrom = (storage) => {
  if (storage) return storage;
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

const normalizeIds = (value) => {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((id) => typeof id === 'string' && id.trim()).map((id) => id.trim()))];
};

export const getAnalyzedJournalIds = (storage) => {
  const target = storageFrom(storage);
  if (!target) return [];

  try {
    return normalizeIds(JSON.parse(target.getItem(ANALYZED_JOURNAL_IDS_KEY) || '[]'));
  } catch {
    try {
      target.removeItem(ANALYZED_JOURNAL_IDS_KEY);
    } catch {
      // Storage can be unavailable or read-only in restricted browser contexts.
    }
    return [];
  }
};

export const setAnalyzedJournalIds = (ids, storage) => {
  const target = storageFrom(storage);
  const normalizedIds = normalizeIds(ids);
  if (!target) return normalizedIds;

  try {
    target.setItem(ANALYZED_JOURNAL_IDS_KEY, JSON.stringify(normalizedIds));
  } catch {
    return normalizedIds;
  }
  return normalizedIds;
};

export const hasAnalyzedJournalId = (journalId, storage) => {
  if (!journalId) return false;
  return getAnalyzedJournalIds(storage).includes(journalId);
};

export const addAnalyzedJournalId = (journalId, storage) => {
  if (!journalId) return getAnalyzedJournalIds(storage);
  const ids = getAnalyzedJournalIds(storage);
  if (ids.includes(journalId)) return ids;
  return setAnalyzedJournalIds([...ids, journalId], storage);
};

export const removeAnalyzedJournalId = (journalId, storage) => {
  if (!journalId) return getAnalyzedJournalIds(storage);
  return setAnalyzedJournalIds(
    getAnalyzedJournalIds(storage).filter((id) => id !== journalId),
    storage,
  );
};
