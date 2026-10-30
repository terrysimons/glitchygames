// The viewer-request CloudFront Function of both distributions (CloudFront Functions JavaScript
// runtime 2.0; docs/specs/2026-10-27-glitchy-games-website-design.md, Address map).
//
// - Any host but play.glitchy.games (glitchy.games, www.glitchy.games, glitchygames.ai,
//   www.glitchygames.ai) gets a 301 to https://play.glitchy.games with its path and query kept,
//   so the site has one origin (browser storage, the Arcade's saves, is per origin).
// - On play.glitchy.games, a directory URL fetches its index.html: the bucket is reached through
//   Origin Access Control, where S3 has no directory index of its own. A directory URL without
//   its trailing slash first gets a 301 to the slashed URL, so the page's relative URLs resolve
//   inside its directory (as GitHub Pages does).
//
// Runtime 2.0 is ES 5.1 plus a listed few later features (const, let, arrow functions, template
// literals; https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/functions-javascript-runtime-20.html):
// no for...of, so loops are forEach. Node runs more than the runtime does, so the tests also
// refuse unlisted statements by name.
//
// Each distribution needs its own Function resource built from this file: a function already
// associated with another distribution can't be used on a flat-rate plan's distribution.
// CloudFront Functions have no module system; the runtime calls the top-level handler.
// Tests: infra/tests/functions/redirect_to_play.test.mjs.

const CANONICAL_HOST = 'play.glitchy.games';

// The query string as the viewer sent it: CloudFront passes each value still percent-encoded,
// so it is joined back unchanged (encoding it again would turn %20 into %2520)
function queryStringOf(querystring) {
  const pairs = [];
  Object.keys(querystring).forEach((name) => {
    const parameter = querystring[name];
    const values = parameter.multiValue
      ? parameter.multiValue.map((entry) => entry.value)
      : [parameter.value];
    values.forEach((value) => {
      pairs.push(value === '' ? name : `${name}=${value}`);
    });
  });
  return pairs.length > 0 ? `?${pairs.join('&')}` : '';
}

// The host without its port, lowercased: host names are case-insensitive
function hostOf(request) {
  const host = request.headers.host ? request.headers.host.value : '';
  return host.split(':')[0].toLowerCase();
}

function movedPermanently(location) {
  return {
    statusCode: 301,
    statusDescription: 'Moved Permanently',
    headers: { location: { value: location } },
  };
}

// A last path segment without a dot names a directory ('/games'), not a file
function namesDirectoryWithoutSlash(uri) {
  const lastSegment = uri.slice(uri.lastIndexOf('/') + 1);
  return lastSegment !== '' && !lastSegment.includes('.');
}

function handler(event) {
  const request = event.request;
  const query = queryStringOf(request.querystring);
  if (hostOf(request) !== CANONICAL_HOST) {
    return movedPermanently(`https://${CANONICAL_HOST}${request.uri}${query}`);
  }
  if (namesDirectoryWithoutSlash(request.uri)) {
    return movedPermanently(`https://${CANONICAL_HOST}${request.uri}/${query}`);
  }
  if (request.uri.endsWith('/')) {
    request.uri = `${request.uri}index.html`;
  }
  return request;
}
