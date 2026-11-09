#!/usr/bin/env node
// Lance toutes les suites jsdom (*.test.js) de ce dossier ; code de sortie non nul si une suite échoue.
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const suites = fs.readdirSync(__dirname).filter((f) => f.endsWith('.test.js')).sort();
let failed = 0;
for (const suite of suites) {
  console.log(`\n▶ ${suite}`);
  const res = spawnSync(process.execPath, [path.join(__dirname, suite)], { stdio: 'inherit' });
  if (res.status !== 0) failed += 1;
}
console.log(`\n${suites.length - failed}/${suites.length} suite(s) réussie(s)`);
process.exit(failed ? 1 : 0);
