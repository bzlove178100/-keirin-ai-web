const fs = require('node:fs');
const assert = require('node:assert/strict');

const html = fs.readFileSync('index.html','utf8');
assert.match(html,/id="prospective-tools-link"/);
assert.match(html,/href="prospective-tools\.html"/);
assert.match(html,/前向き検証ツール（端末内処理）を開く/);

const tools = fs.readFileSync('prospective-tools.html','utf8');
assert.match(tools,/connect-src 'none'/);
assert.match(tools,/src="prospective-tools-core\.js"/);
assert.match(tools,/src="prospective-tools-ui\.js"/);

console.log('Prospective tools launcher checks: PASS');
