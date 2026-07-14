const { pool } = require('./db');
const { fetchAllPages } = require('./balldontlieClient');

// Fetches games in [startDate, endDate] (inclusive, "YYYY-MM-DD" strings) and upserts them.
async function syncGames(startDate, endDate) {
  console.log(`Syncing games from ${startDate} to ${endDate}...`);
  const games = await fetchAllPages('/games', { start_date: startDate, end_date: endDate });

  for (const g of games) {
    await pool.query(
      `INSERT INTO games
         (id, date, season, status, period, time, postseason,
          home_team_id, visitor_team_id, home_team_score, visitor_team_score)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
       ON CONFLICT (id) DO UPDATE SET
         date = EXCLUDED.date,
         season = EXCLUDED.season,
         status = EXCLUDED.status,
         period = EXCLUDED.period,
         time = EXCLUDED.time,
         postseason = EXCLUDED.postseason,
         home_team_id = EXCLUDED.home_team_id,
         visitor_team_id = EXCLUDED.visitor_team_id,
         home_team_score = EXCLUDED.home_team_score,
         visitor_team_score = EXCLUDED.visitor_team_score`,
      [
        g.id,
        g.date,
        g.season,
        g.status,
        g.period,
        g.time,
        g.postseason,
        g.home_team.id,
        g.visitor_team.id,
        g.home_team_score,
        g.visitor_team_score,
      ]
    );
  }

  console.log(`Synced ${games.length} games.`);
  return games.length;
}

module.exports = { syncGames };
