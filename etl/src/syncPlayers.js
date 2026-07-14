const { pool } = require('./db');
const { fetchAllPages } = require('./balldontlieClient');

async function syncPlayers() {
  console.log('Syncing players...');
  const players = await fetchAllPages('/players');

  for (const p of players) {
    await pool.query(
      `INSERT INTO players
         (id, first_name, last_name, position, height, weight, jersey_number,
          college, country, draft_year, draft_round, draft_number, team_id, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13, NOW())
       ON CONFLICT (id) DO UPDATE SET
         first_name = EXCLUDED.first_name,
         last_name = EXCLUDED.last_name,
         position = EXCLUDED.position,
         height = EXCLUDED.height,
         weight = EXCLUDED.weight,
         jersey_number = EXCLUDED.jersey_number,
         college = EXCLUDED.college,
         country = EXCLUDED.country,
         draft_year = EXCLUDED.draft_year,
         draft_round = EXCLUDED.draft_round,
         draft_number = EXCLUDED.draft_number,
         team_id = EXCLUDED.team_id,
         updated_at = NOW()`,
      [
        p.id,
        p.first_name,
        p.last_name,
        p.position || null,
        p.height || null,
        p.weight ? Number(p.weight) : null,
        p.jersey_number || null,
        p.college || null,
        p.country || null,
        p.draft_year || null,
        p.draft_round || null,
        p.draft_number || null,
        p.team ? p.team.id : null,
      ]
    );
  }

  console.log(`Synced ${players.length} players.`);
  return players.length;
}

module.exports = { syncPlayers };
