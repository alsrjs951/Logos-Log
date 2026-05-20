'use strict';

const { add, subtract, multiply, divide } = require('./calculator');

describe('add', () => {
  test('two positives', () => expect(add(2, 3)).toBe(5));
  test('with negative', () => expect(add(-1, 4)).toBe(3));
  test('with zero', () => expect(add(5, 0)).toBe(5));
});

describe('subtract', () => {
  test('basic', () => expect(subtract(10, 4)).toBe(6));
  test('negative result', () => expect(subtract(3, 7)).toBe(-4));
});

describe('multiply', () => {
  test('basic', () => expect(multiply(3, 4)).toBe(12));
  test('by zero', () => expect(multiply(9, 0)).toBe(0));
  test('negatives', () => expect(multiply(-2, 3)).toBe(-6));
});

describe('divide', () => {
  test('basic', () => expect(divide(10, 2)).toBe(5));
  test('decimal', () => expect(divide(7, 2)).toBeCloseTo(3.5));
  test('throws on zero', () => expect(() => divide(5, 0)).toThrow('Division by zero'));
});
