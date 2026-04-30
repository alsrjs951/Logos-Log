'use strict';

const { add, divide } = require('./calculator');
const { mean, median } = require('./stats');

const APP_ENV = process.env.APP_ENV || 'development';

console.log(`[${APP_ENV}] Week8 CI/CD Demo`);
console.log(`add(10, 5)        = ${add(10, 5)}`);
console.log(`divide(10, 5)     = ${divide(10, 5)}`);
console.log(`mean([1,2,3,4,5]) = ${mean([1, 2, 3, 4, 5])}`);
console.log(`median([1,2,3,4]) = ${median([1, 2, 3, 4])}`);
