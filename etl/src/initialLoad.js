const { syncTeams } = require('./syncTeams');
const { syncPlayers } = require('./syncPlayers');
const { syncGames } = require('./syncGames');
const { pool } = require('./db');

// One-time backfill. Run manually:
//   node src/initialLoad.js 2025-10-21 2026-07-13
async function main() {
  const [, , startDate, endDate] = process.argv;
  if (!startDate || !endDate) {
    console.error('Usage: node src/initialLoad.js <start_date YYYY-MM-DD> <end_date YYYY-MM-DD>');
    process.exitCode = 1;
    return;
  }

  try {
    await syncTeams();
    await syncPlayers();
    await syncGames(startDate, endDate);
    console.log('Initial load complete.');
  } catch (err) {
    console.error('Initial load failed:', err.response ? err.response.data : err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

main();
