import {
  applyRecommendedExperimentOverride,
  buildRecommendedExperiment,
} from './recommendedExperiment.js';

export const buildActionLoopState = ({
  dueIntentions = [],
  cards = [],
  recommendationOverride = null,
} = {}) => {
  const due = Array.isArray(dueIntentions) ? dueIntentions.filter(Boolean) : [];

  if (due.length > 0) {
    return {
      status: 'review',
      dueIntentions: due,
      activeIntention: due[0],
      recommendation: null,
    };
  }

  const baseRecommendation = buildRecommendedExperiment(cards);
  const recommendation = applyRecommendedExperimentOverride(
    baseRecommendation,
    recommendationOverride,
    cards
  );
  if (recommendation.status === 'ready') {
    return {
      status: 'recommendation',
      dueIntentions: [],
      activeIntention: null,
      recommendation,
    };
  }

  return {
    status: 'empty',
    dueIntentions: [],
    activeIntention: null,
    recommendation,
  };
};
