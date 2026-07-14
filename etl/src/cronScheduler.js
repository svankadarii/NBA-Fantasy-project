const cron = require('node-cron');
const path = require('path');
const { execFile } = require('child_process');
const { syncTeams } = require('./syncTeams');
const { syncPlayers } = require('./syncPlayers');
const { syncGames } = require('./syncGames');

function yesterday() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

function runPythonStatsSync() {
  return new Promise((resolve, reject) => {
    const pythonExe = path.join(__dirname, '..', 'python', 'venv', 'Scripts', 'python.exe');
    const script = path.join(__dirname, '..', 'python', 'sync_stats.py');
    execFile(
      pythonExe,
      [script],
      { cwd: path.join(__dirname, '..', 'python') },
      (err, stdout, stderr) => {
        if (stdout) console.log(stdout);
        if (stderr) console.error(stderr);
        if (err) return reject(err);
        resolve();
      }
    );
  });
}

async function runDailyJob() {
  const date = yesterday();
  console.log(`\n[${new Date().toISOString()}] Cron job firing for ${date}...`);
  try {
    await syncTeams();
    await syncPlayers();
    await syncGames(date, date);
    console.log('Node sync done, starting Python stats sync...');
    await runPythonStatsSync();
    console.log(`[${new Date().toISOString()}] Daily job complete for ${date}.`);
  } catch (err) {
    console.error(
      `[${new Date().toISOString()}] Daily job FAILED:`,
      err.response ? err.response.data : err.message
    );
  }
}

// Real cron syntax: "minute hour day month weekday". Defaults to 9:00 AM
// every day — by then, games from the previous night are all "Final".
// Override CRON_EXPRESSION / CRON_TIMEZONE in .env if you want a different time/zone.
const CRON_EXPRESSION = process.env.CRON_EXPRESSION || '0 9 * * *';
const CRON_TIMEZONE = process.env.CRON_TIMEZONE || 'America/New_York';

console.log(
  `Cron scheduler started. Will run the daily job on schedule "${CRON_EXPRESSION}" (${CRON_TIMEZONE}). ` +
    `Keep this process running — closing the terminal stops the scheduler.`
);

cron.schedule(CRON_EXPRESSION, runDailyJob, { timezone: CRON_TIMEZONE });

// Uncomment to fire the job immediately (for testing), without waiting for the schedule:
// runDailyJob();

module.exports = { runDailyJob };
