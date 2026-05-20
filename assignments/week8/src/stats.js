'use strict';

function mean(arr) {
  if (!arr.length) throw new Error('Empty array');
  return arr.reduce((sum, x) => sum + x, 0) / arr.length;
}

function median(arr) {
  if (!arr.length) throw new Error('Empty array');
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function variance(arr) {
  const m = mean(arr);
  return mean(arr.map(x => (x - m) ** 2));
}

module.exports = { mean, median, variance };
