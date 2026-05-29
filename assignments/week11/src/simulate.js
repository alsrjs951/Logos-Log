'use strict';

const fs = require('fs');
const { evaluateFeatureFlag, assignABTestVariant, trackEvent, LOG_FILE_PATH } = require('./feature_flags');

// Clean existing logs before starting simulation
if (fs.existsSync(LOG_FILE_PATH)) {
  fs.unlinkSync(LOG_FILE_PATH);
}

const TOTAL_USERS = 1000;
const EXPERIMENT_NAME = 'new-chat-ui';

console.log(`🚀 Starting DevOps A/B Test & Feature Flag Simulation for ${TOTAL_USERS} users...`);

// Stats trackers
let flagStats = {
  'enable-ai-chat': 0,
  'experimental-dark-mode': 0,
  'use-advanced-model': 0
};

let abStats = {
  A: { exposures: 0, conversions: 0 },
  B: { exposures: 0, conversions: 0 }
};

// Generate and simulate users
for (let i = 1; i <= TOTAL_USERS; i++) {
  const userId = `user-${String(i).padStart(3, '0')}`;
  
  // 1. Create randomized mock user attributes
  const user = {
    id: userId,
    isBetaUser: Math.random() < 0.15, // 15% beta users
    email: Math.random() < 0.1 ? `staff-${i}@logos-log.com` : `user-${i}@gmail.com`,
    tier: Math.random() < 0.2 ? 'premium' : 'free', // 20% premium
    role: Math.random() < 0.02 ? 'admin' : 'member' // 2% admins
  };

  // 2. Evaluate Feature Flags for this user
  const aiChat = evaluateFeatureFlag('enable-ai-chat', user);
  const darkMode = evaluateFeatureFlag('experimental-dark-mode', user);
  const advModel = evaluateFeatureFlag('use-advanced-model', user);

  if (aiChat) flagStats['enable-ai-chat']++;
  if (darkMode) flagStats['experimental-dark-mode']++;
  if (advModel) flagStats['use-advanced-model']++;

  // 3. Assign A/B Test Variant
  const variant = assignABTestVariant(userId, EXPERIMENT_NAME);
  abStats[variant].exposures++;

  // Always track the initial exposure event
  trackEvent(userId, EXPERIMENT_NAME, variant, 'exposure', { userTier: user.tier });

  // 4. Simulate user conversion (clicking the chat button)
  // Baseline conversion rate for Variant A = 15%
  // Optimized conversion rate for Variant B = 26%
  const conversionRate = variant === 'A' ? 0.15 : 0.26;
  const converted = Math.random() < conversionRate;

  if (converted) {
    abStats[variant].conversions++;
    // Track conversion event
    trackEvent(userId, EXPERIMENT_NAME, variant, 'chat_click', {
      clickDurationMs: Math.floor(Math.random() * 800) + 100
    });
  }
}

// Write a neat simulation summary report to console (and later to markdown summary)
console.log('\n==================================================');
console.log('📊 Feature Flags Activation Rates:');
Object.keys(flagStats).forEach(flag => {
  const percentage = ((flagStats[flag] / TOTAL_USERS) * 100).toFixed(1);
  console.log(`- ${flag}: ${flagStats[flag]}/${TOTAL_USERS} (${percentage}%)`);
});

const rateA = ((abStats.A.conversions / abStats.A.exposures) * 100).toFixed(2);
const rateB = ((abStats.B.conversions / abStats.B.exposures) * 100).toFixed(2);
const improvement = (((rateB - rateA) / rateA) * 100).toFixed(1);

console.log('\n🎯 A/B Test Results Summary (new-chat-ui):');
console.log(`- Variant A (Control): ${abStats.A.conversions}/${abStats.A.exposures} clicks (${rateA}%)`);
console.log(`- Variant B (Treatment): ${abStats.B.conversions}/${abStats.B.exposures} clicks (${rateB}%)`);
console.log(`- Improvement Rate: +${improvement}%`);
console.log('==================================================');
console.log(`💾 Logs written to: ${LOG_FILE_PATH}\n`);
