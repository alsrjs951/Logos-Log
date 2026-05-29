'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// 3 Feature Flags definitions
function evaluateFeatureFlag(flagName, user = {}) {
  const envVarName = `FEATURE_${flagName.toUpperCase().replace(/-/g, '_')}`;
  
  // 1. Check Global Environment Variable Toggle
  if (process.env[envVarName] === 'true') {
    return true;
  }
  if (process.env[envVarName] === 'false') {
    return false;
  }

  // 2. Evaluate Specific Target User Rules
  switch (flagName) {
    case 'enable-ai-chat':
      // Target: Beta users or enterprise domain emails
      return !!(user.isBetaUser || (user.email && user.email.endsWith('@logos-log.com')));
      
    case 'experimental-dark-mode':
      // Target: Tester user list or internal staff
      const testerUserIds = ['user-001', 'user-002', 'user-003', 'admin-user'];
      return !!((user.id && testerUserIds.includes(user.id)) || user.role === 'admin');
      
    case 'use-advanced-model':
      // Target: Premium tier users
      return !!(user.tier === 'premium' || user.isVip);
      
    default:
      return false;
  }
}

// A/B Testing: Deterministic Bucket Assignment using Cryptographic Hash
function assignABTestVariant(userId, experimentName) {
  if (!userId) {
    // If no user ID, randomly assign (or default to control)
    return 'A';
  }
  
  // Create salt combining userId and experimentName to avoid correlation between different experiments
  const hashKey = `${userId}:${experimentName}`;
  const hashHex = crypto.createHash('md5').update(hashKey).digest('hex');
  
  // Convert first 8 characters of MD5 hex to a 32-bit integer and get percentage bucket (0-99)
  const bucket = parseInt(hashHex.substring(0, 8), 16) % 100;
  
  // 50% split: 0-49 maps to Variant A (Control), 50-99 maps to Variant B (Treatment)
  return bucket < 50 ? 'A' : 'B';
}

// Event Tracking Logic: Record experiment events to a JSON file
const LOG_FILE_PATH = path.join(__dirname, '../experiment_logs.json');

function trackEvent(userId, experimentName, variant, eventName, attributes = {}) {
  const eventLog = {
    timestamp: new Date().toISOString(),
    userId,
    experimentName,
    variant,
    eventName,
    attributes
  };

  try {
    let logs = [];
    if (fs.existsSync(LOG_FILE_PATH)) {
      const fileData = fs.readFileSync(LOG_FILE_PATH, 'utf8');
      if (fileData.trim()) {
        logs = JSON.parse(fileData);
      }
    }
    logs.push(eventLog);
    fs.writeFileSync(LOG_FILE_PATH, JSON.stringify(logs, null, 2), 'utf8');
  } catch (error) {
    console.error('Failed to log experiment event:', error);
  }
  
  return eventLog;
}

module.exports = {
  evaluateFeatureFlag,
  assignABTestVariant,
  trackEvent,
  LOG_FILE_PATH
};
