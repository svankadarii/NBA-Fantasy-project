const { pool } = require('./db');
const { fetchOnce } = require('./balldontlieClient');

async function syncTeams() {
  console.log('Syncing teams...');
  const teams = await fetchOnce('/teams');

  for (const t of teams) {
    await pool.query(
      `INSERT INTO teams (id, abbreviation, city, conference, division, full_name, name)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       ON CONFLICT (id) DO UPDATE SET
         abbreviation = EXCLUDED.abbreviation,
         city = EXCLUDED.city,
         conference = EXCLUDED.conference,
         division = EXCLUDED.division,
         full_name = EXCLUDED.full_name,
         name = EXCLUDED.name`,
      [t.id, t.abbreviation, t.city, t.conference, t.division, t.full_name, t.name]
    );
  }

  console.log(`Synced ${teams.length} teams.`);
  return teams.length;
}

module.exports = { syncTeams };
