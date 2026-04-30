'use strict';

const { add, subtract, multiply, divide } = require('./calculator');

const APP_ENV = process.env.APP_ENV || 'development';

console.log(`[${APP_ENV}] Week7 CI/CD Demo`);
console.log(`add(10, 5)      = ${add(10, 5)}`);
console.log(`subtract(10, 5) = ${subtract(10, 5)}`);
console.log(`multiply(10, 5) = ${multiply(10, 5)}`);
console.log(`divide(10, 5)   = ${divide(10, 5)}`);
