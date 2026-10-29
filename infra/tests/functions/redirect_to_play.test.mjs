// The viewer-request CloudFront Function both distributions run
// (infra/src/glitchy_site/functions/redirect_to_play.js): every host but play.glitchy.games is
// sent there with a 301, path and query kept; on play.glitchy.games, directory URLs fetch their
// index.html. Run with `node --test infra/tests/functions` (nox -s infra-test).

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

// CloudFront Functions have no module system: the file only defines a top-level handler. Load it
// the same way, as a plain script, and take the handler it defines
const functionPath = new URL(
  '../../src/glitchy_site/functions/redirect_to_play.js',
  import.meta.url,
);
const functionSource = readFileSync(functionPath, 'utf8');
const handler = vm.runInNewContext(`${functionSource}\n;handler`);

// Node runs more of JavaScript than CloudFront Functions' runtime 2.0 does, so a test passing
// here does not prove the code runs there. Statements the runtime does not list
// (https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/functions-javascript-runtime-20.html)
// are refused by name: for...of, classes, generators, destructuring and spread
test('the function uses only statements CloudFront Functions runtime 2.0 supports', () => {
  const unsupported = {
    'for...of': /\bfor\s*\([^)]*\sof\s/,
    class: /\bclass\s+\w/,
    generator: /\bfunction\s*\*/,
    'destructuring declaration': /\b(?:const|let|var)\s*[[{]/,
    spread: /\.\.\.\w/,
  };
  // The code only: the file's comments may name the features it avoids
  const code = functionSource.replace(/^\s*\/\/.*$/gm, '');
  for (const [feature, pattern] of Object.entries(unsupported)) {
    assert.doesNotMatch(code, pattern, feature);
  }
});

function requestFor({ host, uri, querystring = {} }) {
  return { request: { uri, querystring, headers: { host: { value: host } } } };
}

test('another host is sent to the canonical host with its path', () => {
  const response = handler(requestFor({ host: 'glitchy.games', uri: '/paddleslap/' }));

  assert.equal(response.statusCode, 301);
  assert.equal(response.statusDescription, 'Moved Permanently');
  assert.equal(response.headers.location.value, 'https://play.glitchy.games/paddleslap/');
});

test('every non-canonical host redirects', () => {
  for (const host of ['www.glitchy.games', 'glitchygames.ai', 'www.glitchygames.ai']) {
    const response = handler(requestFor({ host, uri: '/' }));

    assert.equal(response.statusCode, 301, host);
    assert.equal(response.headers.location.value, 'https://play.glitchy.games/', host);
  }
});

test('the query string survives, repeated keys and encoding included', () => {
  const response = handler(
    requestFor({
      host: 'glitchygames.ai',
      uri: '/',
      querystring: {
        a: { value: '1', multiValue: [{ value: '1' }, { value: '2' }] },
        q: { value: 'hello%20world' },
      },
    }),
  );

  assert.equal(
    response.headers.location.value,
    'https://play.glitchy.games/?a=1&a=2&q=hello%20world',
  );
});

test('a query key without a value keeps its bare form', () => {
  const response = handler(
    requestFor({ host: 'glitchy.games', uri: '/x', querystring: { debug: { value: '' } } }),
  );

  assert.equal(response.headers.location.value, 'https://play.glitchy.games/x?debug');
});

test('the canonical host is recognised in any case and with a port', () => {
  for (const host of ['Play.Glitchy.Games', 'play.glitchy.games:443']) {
    const result = handler(requestFor({ host, uri: '/arcade-mockup.png' }));

    assert.equal(result.statusCode, undefined, host);
    assert.equal(result.uri, '/arcade-mockup.png', host);
  }
});

test('a directory URL without its slash gets one, so its relative URLs resolve inside it', () => {
  // Serving /paddleslap/index.html at /paddleslap would make the page's relative URLs
  // (engine.js) resolve against / instead of /paddleslap/ (GitHub Pages answers the same way)
  const response = handler(
    requestFor({
      host: 'play.glitchy.games',
      uri: '/paddleslap',
      querystring: { level: { value: '2' } },
    }),
  );

  assert.equal(response.statusCode, 301);
  assert.equal(response.headers.location.value, 'https://play.glitchy.games/paddleslap/?level=2');
});

test('directory URLs on the canonical host fetch their index', () => {
  const expectations = {
    '/': '/index.html',
    '/paddleslap/': '/paddleslap/index.html',
    '/arcade-mockup.png': '/arcade-mockup.png',
    '/games/v1.2/': '/games/v1.2/index.html',
  };
  for (const [uri, expected] of Object.entries(expectations)) {
    const result = handler(requestFor({ host: 'play.glitchy.games', uri }));

    assert.equal(result.uri, expected, uri);
  }
});
