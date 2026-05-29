'use strict';

const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

// Exportable functions for the npm package
function greet(name) {
  return `Hello, ${name}! Welcome to Logos-Log Week 9 DevOps Demo.`;
}

function getSystemInfo() {
  return {
    platform: process.platform,
    nodeVersion: process.version,
    uptime: process.uptime(),
  };
}

// Server endpoints
app.get('/', (req, res) => {
  res.json({
    status: 'ok',
    message: greet('Guest'),
    version: require('../package.json').version,
    environment: process.env.NODE_ENV || 'development'
  });
});

app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    system: getSystemInfo()
  });
});

// Run server only when executed directly (not when required as a module)
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
  });
}

module.exports = {
  greet,
  getSystemInfo
};
