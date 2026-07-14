# NBA Fantasy ETL

Two pieces, both writing to the same Postgres database:

- **Node.js** (`src/`) — pulls teams, players, and games from balldontlie.io (Free tier).
- **Python** (`python/`) — pulls player box score stats from `nba_api` (unofficial stats.nba.com wrapper), matched to the games the Node side already loaded, and writes `player_game_stats`.

balldontlie's Free tier doesn't include the stats endpoint (that requires their paid ALL-STAR tier), so stats come from `nba_api` instead. This means: **always run the Node sync for a date before the Python stats sync for that same date** — the Python script looks up games in Postgres to match against nba_api's game IDs.

## Setup

**Node side:**
```powershell
cd etl
npm install
copy .env.example .env
# edit .env: set DATABASE_URL and BALLDONTLIE_API_KEY
```

**Python side:**
```powershell
cd etl/python
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
(Python reads the same `../.env` file — no separate Python `.env` needed.)

## One-time backfill

Loads teams, all players, and games for a date range, then stats for each date in that range:

```powershell
cd etl
node src/initialLoad.js 2025-10-21 2026-07-13

cd python
venv\Scripts\activate
for /L %d in (0,1,X) do python sync_stats.py --date <date>   # or loop with a small script if the range is long
```

For a big backfill, it's easier to loop dates in PowerShell:
```powershell
$start = Get-Date "2025-10-21"
$end = Get-Date "2026-07-13"
for ($d = $start; $d -le $end; $d = $d.AddDays(1)) {
    python sync_stats.py --date $($d.ToString("yyyy-MM-dd"))
}
```

## Daily run (what cron/Task Scheduler will call — step 3)

```powershell
node src/dailyEtl.js
python python/sync_stats.py
```

Both default to "yesterday" when no date is given, so a single daily run keeps the DB current.

## Known limitation

Player matching between balldontlie and nba_api is done by normalized name (lowercased, accents stripped, suffixes like Jr./III removed), not a shared ID — the two APIs use different player ID systems. Rare edge cases (unusual name formatting, mid-season trades) may fail to match and get logged as "Skipping unmatched player" rather than silently miscounted. Check the console output after each run.
