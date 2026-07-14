const { syncTeams } = require('./syncTeams');
const { syncPlayers } = require('./syncPlayers');
const { syncGames } = require('./syncGames');
const { pool } = require('./db');

// This is the entry point the daily cron/Task Scheduler job will call (step 3).
// Syncs teams (catches trades), players (catches roster moves), and yesterday's games.
function yesterday() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

async function main() {
  const date = yesterday();
  try {
    await syncTeams();
    await syncPlayers();
    await syncGames(date, date);
    console.log(`Daily ETL complete for ${date}.`);
  } catch (err) {
    console.error('Daily ETL failed:', err.response ? err.response.data : err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

main();
