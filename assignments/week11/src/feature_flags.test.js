'use strict';

const fs = require('fs');
const { evaluateFeatureFlag, assignABTestVariant, trackEvent, LOG_FILE_PATH } = require('./feature_flags');

describe('Week 11 Feature Flags & A/B Testing Suite', () => {
  
  // Clean up logs after tests
  afterAll(() => {
    if (fs.existsSync(LOG_FILE_PATH)) {
      fs.unlinkSync(LOG_FILE_PATH);
    }
  });

  describe('Feature Flags Evaluation', () => {
    
    test('should return true when global env var is enabled', () => {
      process.env.FEATURE_ENABLE_AI_CHAT = 'true';
      expect(evaluateFeatureFlag('enable-ai-chat')).toBe(true);
      delete process.env.FEATURE_ENABLE_AI_CHAT;
    });

    test('should return false when global env var is disabled', () => {
      process.env.FEATURE_ENABLE_AI_CHAT = 'false';
      expect(evaluateFeatureFlag('enable-ai-chat')).toBe(false);
      delete process.env.FEATURE_ENABLE_AI_CHAT;
    });

    test('should evaluate enable-ai-chat for beta users or internal staff', () => {
      // Normal user: false
      expect(evaluateFeatureFlag('enable-ai-chat', { isBetaUser: false })).toBe(false);
      
      // Beta user: true
      expect(evaluateFeatureFlag('enable-ai-chat', { isBetaUser: true })).toBe(true);
      
      // Staff email: true
      expect(evaluateFeatureFlag('enable-ai-chat', { email: 'test@logos-log.com' })).toBe(true);
    });

    test('should evaluate experimental-dark-mode for whitelisted users or admins', () => {
      expect(evaluateFeatureFlag('experimental-dark-mode', { id: 'user-999' })).toBe(false);
      expect(evaluateFeatureFlag('experimental-dark-mode', { id: 'user-001' })).toBe(true);
      expect(evaluateFeatureFlag('experimental-dark-mode', { role: 'admin' })).toBe(true);
    });

    test('should evaluate use-advanced-model for premium tiers', () => {
      expect(evaluateFeatureFlag('use-advanced-model', { tier: 'free' })).toBe(false);
      expect(evaluateFeatureFlag('use-advanced-model', { tier: 'premium' })).toBe(true);
    });
  });

  describe('Consistent A/B Test Variant Assignment', () => {
    
    test('should assign variant deterministically (same user ID always gets same variant)', () => {
      const expName = 'test-button-experiment';
      const userId = 'user-abc-123';
      
      const variant1 = assignABTestVariant(userId, expName);
      const variant2 = assignABTestVariant(userId, expName);
      const variant3 = assignABTestVariant(userId, expName);
      
      expect(variant1).toBe(variant2);
      expect(variant2).toBe(variant3);
    });

    test('should assign different variants for different users (distribution check)', () => {
      const expName = 'test-button-experiment';
      const assignments = new Set();
      
      // Map 100 users, check if both A and B are assigned
      for (let i = 0; i < 100; i++) {
        assignments.add(assignABTestVariant(`user-${i}`, expName));
      }
      
      expect(assignments.has('A')).toBe(true);
      expect(assignments.has('B')).toBe(true);
      expect(assignments.size).toBe(2);
    });
  });

  describe('Event Tracking & Log Auditing', () => {
    
    test('should track events and write them to logs file', () => {
      if (fs.existsSync(LOG_FILE_PATH)) {
        fs.unlinkSync(LOG_FILE_PATH);
      }
      
      const log = trackEvent('user-999', 'layout-test', 'B', 'click_convert', { price: 500 });
      
      expect(log.userId).toBe('user-999');
      expect(log.variant).toBe('B');
      expect(log.eventName).toBe('click_convert');
      expect(log.attributes.price).toBe(500);
      
      expect(fs.existsSync(LOG_FILE_PATH)).toBe(true);
      const fileContent = JSON.parse(fs.readFileSync(LOG_FILE_PATH, 'utf8'));
      expect(fileContent.length).toBe(1);
      expect(fileContent[0].userId).toBe('user-999');
    });
  });
});
