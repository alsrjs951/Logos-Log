'use strict';

const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, '..', 'src');
const distDir = path.join(__dirname, '..', 'dist');

if (!fs.existsSync(distDir)) fs.mkdirSync(distDir, { recursive: true });

const files = fs.readdirSync(srcDir).filter(f => f.endsWith('.js') && !f.endsWith('.test.js'));
files.forEach(file => {
  fs.copyFileSync(path.join(srcDir, file), path.join(distDir, file));
  console.log(`Copied: src/${file} → dist/${file}`);
});

const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
fs.writeFileSync(path.join(distDir, 'build-info.json'), JSON.stringify({
  name: pkg.name,
  version: pkg.version,
  builtAt: new Date().toISOString(),
  files,
}, null, 2));
console.log('Build complete →', distDir);
