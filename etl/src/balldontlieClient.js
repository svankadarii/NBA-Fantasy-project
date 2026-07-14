require('dotenv').config();
const axios = require('axios');

const API_KEY = process.env.BALLDONTLIE_API_KEY;
const REQUEST_DELAY_MS = Number(process.env.BALLDONTLIE_REQUEST_DELAY_MS || 13000); // Free tier = 5 req/min

if (!API_KEY) {
  throw new Error('BALLDONTLIE_API_KEY is not set. Copy .env.example to .env and fill it in.');
}

const client = axios.create({
  baseURL: 'https://api.balldontlie.io/v1',
  headers: { Authorization: API_KEY },
  timeout: 15000,
});

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Retries a single API call on transient network errors or 429s.
async function getWithRetry(path, params, maxRetries = 5) {
  let delay = REQUEST_DELAY_MS;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await client.get(path, { params });
    } catch (err) {
      const status = err.response && err.response.status;
      const isRetryable =
        status === 429 ||
        !err.response; // network-level errors: ENOTFOUND, ECONNRESET, ETIMEDOUT, etc.

      if (!isRetryable || attempt === maxRetries) throw err;

      console.warn(`  [balldontlie] ${status || err.code} on ${path} — retry ${attempt}/${maxRetries - 1} in ${delay / 1000}s`);
      await sleep(delay);
      delay = Math.min(delay * 2, 120000); // cap at 2 min
    }
  }
}

// Fetches every page of a cursor-paginated endpoint, waiting between requests
// to stay under the Free tier's 5 requests/minute limit. Bump
// BALLDONTLIE_REQUEST_DELAY_MS in .env if you still see 429s, or lower it if
// you upgrade tiers later.
async function fetchAllPages(path, params = {}) {
  let cursor;
  const results = [];
  let page = 0;

  do {
    // Sleep before every request (including page 1) so back-to-back sync
    // functions don't burst past the Free tier's 5 req/min limit.
    await sleep(REQUEST_DELAY_MS);

    const query = { ...params, per_page: params.per_page || 100 };
    if (cursor) query.cursor = cursor;

    const { data } = await getWithRetry(path, query);
    results.push(...data.data);
    cursor = data.meta && data.meta.next_cursor;
    page += 1;

    console.log(`  [balldontlie] ${path} page ${page} -> ${data.data.length} rows (next_cursor=${cursor ?? 'none'})`);
  } while (cursor);

  return results;
}

async function fetchOnce(path, params = {}) {
  const { data } = await getWithRetry(path, params);
  return data.data;
}

module.exports = { fetchAllPages, fetchOnce, sleep, REQUEST_DELAY_MS };
