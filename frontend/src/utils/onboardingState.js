const ONBOARDING_DONE_KEY = 'onboarding_done';

const storageFrom = (storage) => {
  if (storage) return storage;
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

export const hasCompletedOnboarding = (storage) => {
  const target = storageFrom(storage);
  if (!target) return false;

  try {
    return target.getItem(ONBOARDING_DONE_KEY) === 'true';
  } catch {
    return false;
  }
};

export const markOnboardingComplete = (storage) => {
  const target = storageFrom(storage);
  if (!target) return false;

  try {
    target.setItem(ONBOARDING_DONE_KEY, 'true');
    return true;
  } catch {
    return false;
  }
};
