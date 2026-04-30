'use strict';

const { mean, median, variance } = require('./stats');

describe('mean', () => {
  test('basic', () => expect(mean([1, 2, 3, 4, 5])).toBe(3));
  test('single element', () => expect(mean([7])).toBe(7));
  test('empty throws', () => expect(() => mean([])).toThrow('Empty array'));
  test('decimals', () => expect(mean([1.5, 2.5])).toBeCloseTo(2.0));
});

describe('median', () => {
  test('odd count', () => expect(median([3, 1, 4, 1, 5])).toBe(3));
  test('even count', () => expect(median([1, 2, 3, 4])).toBe(2.5));
  test('single element', () => expect(median([9])).toBe(9));
  test('empty throws', () => expect(() => median([])).toThrow('Empty array'));
});

describe('variance', () => {
  test('identical values returns 0', () => expect(variance([5, 5, 5])).toBe(0));
  test('basic variance', () => expect(variance([2, 4, 4, 4, 5, 5, 7, 9])).toBeCloseTo(4.0));
});
