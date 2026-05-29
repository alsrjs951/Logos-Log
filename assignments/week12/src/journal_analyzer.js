'use strict';

const STOPWORDS = new Set(['the', 'and', 'a', 'an', 'of', 'in', 'to', 'for', 'with', 'on', 'at', 'by', 'this', 'that', 'it', 'is', 'was', 'were', 'be', 'are']);

// 1. Validate journal entry structure and content length
function validateEntry(entry) {
  if (!entry) {
    return { valid: false, reason: 'Entry is null or undefined' };
  }
  const required = ['id', 'title', 'content', 'timestamp'];
  for (const field of required) {
    if (entry[field] === undefined || entry[field] === null || entry[field] === '') {
      return { valid: false, reason: `Missing or empty required field: ${field}` };
    }
  }
  if (typeof entry.content !== 'string' || entry.content.trim().length < 5) {
    return { valid: false, reason: 'Content must be a string of at least 5 characters' };
  }
  return { valid: true };
}

// 2. Extract keywords from journal content (ignoring short words and stopwords)
function extractKeywords(text) {
  if (!text || typeof text !== 'string') return [];
  
  const words = text
    .toLowerCase()
    .replace(/[.,\/#!$%\^&\*;:{}=\-_`~()?"']/g, '') // remove punctuation
    .split(/\s+/);
    
  const freq = {};
  for (const word of words) {
    if (word.length >= 3 && !STOPWORDS.has(word)) {
      freq[word] = (freq[word] || 0) + 1;
    }
  }
  
  return Object.keys(freq)
    .map(word => ({ word, count: freq[word] }))
    .sort((a, b) => b.count - a.count || a.word.localeCompare(b.word));
}

// 3. Score sentiment based on positive and negative keywords count
function analyzeSentiment(text) {
  if (!text || typeof text !== 'string') {
    return { score: 0, sentiment: 'neutral' };
  }
  
  const positiveWords = ['happy', 'glad', 'good', 'great', 'awesome', 'love', 'perfect', 'beautiful', 'excellent'];
  const negativeWords = ['sad', 'bad', 'worst', 'hate', 'angry', 'sorry', 'disappointed', 'terrible', 'fail'];
  
  const words = text.toLowerCase().split(/\s+/);
  let score = 0;
  
  for (const word of words) {
    const cleanWord = word.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()?"']/g, '');
    if (positiveWords.includes(cleanWord)) score++;
    if (negativeWords.includes(cleanWord)) score--;
  }
  
  const sentiment = score > 0 ? 'positive' : (score < 0 ? 'negative' : 'neutral');
  return { score, sentiment };
}

// 4. Find related journals based on shared keyword intersection
function findRelatedJournals(entry, allEntries = []) {
  const validation = validateEntry(entry);
  if (!validation.valid) return [];
  
  const entryKeywords = new Set(extractKeywords(entry.content).map(k => k.word));
  if (entryKeywords.size === 0) return [];
  
  const related = [];
  for (const item of allEntries) {
    if (item.id === entry.id) continue;
    
    const itemKeywords = extractKeywords(item.content).map(k => k.word);
    let matchCount = 0;
    for (const kw of itemKeywords) {
      if (entryKeywords.has(kw)) matchCount++;
    }
    
    if (matchCount > 0) {
      related.push({
        id: item.id,
        title: item.title,
        score: matchCount
      });
    }
  }
  
  return related.sort((a, b) => b.score - a.score || a.title.localeCompare(b.title));
}

// 5. Format and export the journal entry to JSON, Markdown, or Plain Text
function formatExport(entry, format = 'json') {
  const validation = validateEntry(entry);
  if (!validation.valid) {
    throw new Error(`Invalid entry: ${validation.reason}`);
  }
  
  const cleanFormat = format.toLowerCase();
  if (cleanFormat === 'json') {
    return JSON.stringify(entry, null, 2);
  } else if (cleanFormat === 'markdown') {
    return `# ${entry.title}\n\n*Date: ${entry.timestamp}*\n\n${entry.content}`;
  } else if (cleanFormat === 'text') {
    return `Title: ${entry.title}\nDate: ${entry.timestamp}\n\n${entry.content}`;
  } else {
    throw new Error(`Unsupported export format: ${format}`);
  }
}

module.exports = {
  validateEntry,
  extractKeywords,
  analyzeSentiment,
  findRelatedJournals,
  formatExport
};
