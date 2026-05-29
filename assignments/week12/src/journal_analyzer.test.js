'use strict';

const {
  validateEntry,
  extractKeywords,
  analyzeSentiment,
  findRelatedJournals,
  formatExport
} = require('./journal_analyzer');

describe('Week 12 — Journal Analyzer Unit Tests (TDD Logic)', () => {
  
  const validEntry = {
    id: 'entry-1',
    title: 'My First Journal',
    content: 'Today was an awesome day, I felt very happy and loved the experience.',
    timestamp: '2026-05-29T12:00:00Z'
  };

  describe('validateEntry()', () => {
    test('should fail when entry is null or undefined', () => {
      expect(validateEntry(null)).toEqual({ valid: false, reason: 'Entry is null or undefined' });
      expect(validateEntry(undefined)).toEqual({ valid: false, reason: 'Entry is null or undefined' });
    });

    test('should fail when required fields are missing or empty', () => {
      const missingId = { title: 'T', content: 'C', timestamp: 'TS' };
      expect(validateEntry(missingId)).toEqual({ valid: false, reason: 'Missing or empty required field: id' });

      const emptyTitle = { id: 'I', title: '', content: 'C', timestamp: 'TS' };
      expect(validateEntry(emptyTitle)).toEqual({ valid: false, reason: 'Missing or empty required field: title' });
    });

    test('should fail when content is not a string or too short', () => {
      const nonString = { id: 'I', title: 'T', content: 12345, timestamp: 'TS' };
      expect(validateEntry(nonString)).toEqual({ valid: false, reason: 'Content must be a string of at least 5 characters' });

      const tooShort = { id: 'I', title: 'T', content: 'abc', timestamp: 'TS' };
      expect(validateEntry(tooShort)).toEqual({ valid: false, reason: 'Content must be a string of at least 5 characters' });
    });

    test('should pass for a valid entry structure', () => {
      expect(validateEntry(validEntry)).toEqual({ valid: true });
    });
  });

  describe('extractKeywords()', () => {
    test('should return empty array for invalid text input', () => {
      expect(extractKeywords(null)).toEqual([]);
      expect(extractKeywords(123)).toEqual([]);
      expect(extractKeywords('')).toEqual([]);
    });

    test('should extract keywords and strip punctuation and stopwords', () => {
      const text = 'The quick brown fox jumps over a lazy dog, that dog was beautiful!';
      const keywords = extractKeywords(text);
      
      const wordsOnly = keywords.map(k => k.word);
      expect(wordsOnly).toContain('quick');
      expect(wordsOnly).toContain('brown');
      expect(wordsOnly).toContain('beautiful');
      expect(wordsOnly).not.toContain('the');
      expect(wordsOnly).not.toContain('that');
      expect(wordsOnly).not.toContain('a');
    });

    test('should sort keywords by frequency in descending order, then alphabetically', () => {
      const text = 'apple banana banana cherry cherry cherry';
      const keywords = extractKeywords(text);
      
      expect(keywords).toEqual([
        { word: 'cherry', count: 3 },
        { word: 'banana', count: 2 },
        { word: 'apple', count: 1 }
      ]);
    });
  });

  describe('analyzeSentiment()', () => {
    test('should return neutral for empty or invalid input', () => {
      expect(analyzeSentiment(null)).toEqual({ score: 0, sentiment: 'neutral' });
      expect(analyzeSentiment(123)).toEqual({ score: 0, sentiment: 'neutral' });
    });

    test('should calculate positive sentiment score', () => {
      const text = 'Today was a great, beautiful and happy day!';
      expect(analyzeSentiment(text)).toEqual({ score: 3, sentiment: 'positive' });
    });

    test('should calculate negative sentiment score', () => {
      const text = 'Today was a terrible and worst experience, feeling very sad.';
      expect(analyzeSentiment(text)).toEqual({ score: -3, sentiment: 'negative' });
    });

    test('should calculate neutral sentiment for mixed or neutral text', () => {
      const text = 'Today was happy but also sad.';
      expect(analyzeSentiment(text)).toEqual({ score: 0, sentiment: 'neutral' });
    });
  });

  describe('findRelatedJournals()', () => {
    const list = [
      { id: 'entry-1', title: 'T1', content: 'apple banana cherry' },
      { id: 'entry-2', title: 'T2', content: 'apple banana dog' },
      { id: 'entry-3', title: 'T3', content: 'apple elephant fox' },
      { id: 'entry-4', title: 'T4', content: 'giraffe hippo' }
    ];

    test('should return empty array for invalid input', () => {
      expect(findRelatedJournals(null, list)).toEqual([]);
      expect(findRelatedJournals({ content: '' }, list)).toEqual([]);
    });

    test('should return list of related journals sorted by match score, skipping self', () => {
      const source = { id: 'entry-1', title: 'T1', content: 'apple banana cherry', timestamp: '2026' };
      const related = findRelatedJournals(source, list);
      
      expect(related.length).toBe(2);
      expect(related[0]).toEqual({ id: 'entry-2', title: 'T2', score: 2 }); // matches apple, banana
      expect(related[1]).toEqual({ id: 'entry-3', title: 'T3', score: 1 }); // matches apple
      // does not match entry-4 (no shared keywords) and skips entry-1 (self)
    });
  });

  describe('formatExport()', () => {
    test('should throw error for invalid entry input', () => {
      expect(() => formatExport(null, 'json')).toThrow();
    });

    test('should export JSON correctly', () => {
      const result = formatExport(validEntry, 'json');
      expect(JSON.parse(result)).toEqual(validEntry);
    });

    test('should export Markdown correctly', () => {
      const result = formatExport(validEntry, 'markdown');
      expect(result).toContain('# My First Journal');
      expect(result).toContain('*Date: 2026-05-29T12:00:00Z*');
      expect(result).toContain('Today was an awesome day');
    });

    test('should export plain text correctly', () => {
      const result = formatExport(validEntry, 'text');
      expect(result).toContain('Title: My First Journal');
      expect(result).toContain('Date: 2026-05-29T12:00:00Z');
    });

    test('should throw error for unsupported format', () => {
      expect(() => formatExport(validEntry, 'xml')).toThrow('Unsupported export format: xml');
    });
  });
});
