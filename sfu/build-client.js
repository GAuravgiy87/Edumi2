/**
 * Builds a browser-ready mediasoup-client bundle and copies it to static/js/
 * Run once: node sfu/build-client.js
 */
const { execSync } = require('child_process');
const fs   = require('fs');
const path = require('path');

const ROOT   = path.join(__dirname, '..');
const OUT    = path.join(ROOT, 'static', 'js', 'mediasoup-client.min.js');
const TMPDIR = path.join(__dirname, '_build_tmp');

console.log('Building mediasoup-client browser bundle...');

// Install browserify if not present
try { execSync('npx browserify --version', { stdio: 'ignore' }); } catch (_) {
    execSync('npm install -g browserify', { stdio: 'inherit' });
}

fs.mkdirSync(TMPDIR, { recursive: true });

// Entry point
const entry = path.join(TMPDIR, 'entry.js');
fs.writeFileSync(entry, `
const mediasoupClient = require('mediasoup-client');
window.mediasoupClient = mediasoupClient;
`);

execSync(
    `npx browserify "${entry}" -o "${OUT}" --node`,
    { cwd: __dirname, stdio: 'inherit' }
);

fs.rmSync(TMPDIR, { recursive: true, force: true });
console.log(`Done → ${OUT} (${(fs.statSync(OUT).size / 1024).toFixed(0)} KB)`);
