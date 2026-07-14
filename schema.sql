-- NBA Fantasy App schema
-- Uses balldontlie.io IDs directly as primary keys (no separate mapping table needed)

CREATE TABLE teams (
    id              INTEGER PRIMARY KEY,        -- balldontlie team id
    abbreviation    VARCHAR(10) NOT NULL,
    city            VARCHAR(50),
    conference      VARCHAR(10),
    division        VARCHAR(20),
    full_name       VARCHAR(100) NOT NULL,
    name            VARCHAR(50) NOT NULL
);

CREATE TABLE players (
    id              INTEGER PRIMARY KEY,        -- balldontlie player id
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    position        VARCHAR(10),
    height          VARCHAR(10),                -- e.g. "6-8" as returned by API
    weight          INTEGER,
    jersey_number   VARCHAR(10),
    college         VARCHAR(100),
    country         VARCHAR(50),
    draft_year      INTEGER,
    draft_round     INTEGER,
    draft_number    INTEGER,
    team_id         INTEGER REFERENCES teams(id),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE games (
    id                  INTEGER PRIMARY KEY,    -- balldontlie game id
    date                DATE NOT NULL,
    season              INTEGER NOT NULL,
    status              VARCHAR(20),
    period              INTEGER,
    time                VARCHAR(20),
    postseason          BOOLEAN DEFAULT FALSE,
    home_team_id        INTEGER REFERENCES teams(id),
    visitor_team_id     INTEGER REFERENCES teams(id),
    home_team_score     INTEGER,
    visitor_team_score  INTEGER
);

CREATE TABLE player_game_stats (
    id              SERIAL PRIMARY KEY,
    player_id       INTEGER NOT NULL REFERENCES players(id),
    game_id         INTEGER NOT NULL REFERENCES games(id),
    team_id         INTEGER REFERENCES teams(id),
    min             VARCHAR(10),                -- API returns "34:12" style string
    pts             INTEGER,
    ast             INTEGER,
    reb             INTEGER,
    oreb            INTEGER,
    dreb            INTEGER,
    stl             INTEGER,
    blk             INTEGER,
    turnover        INTEGER,
    pf              INTEGER,
    fgm             INTEGER,
    fga             INTEGER,
    fg_pct          NUMERIC(5,3),
    fg3m            INTEGER,
    fg3a            INTEGER,
    fg3_pct         NUMERIC(5,3),
    ftm             INTEGER,
    fta             INTEGER,
    ft_pct          NUMERIC(5,3),
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (player_id, game_id)
);

CREATE TABLE predictions (
    id                          SERIAL PRIMARY KEY,
    player_id                   INTEGER NOT NULL REFERENCES players(id),
    game_id                     INTEGER NOT NULL REFERENCES games(id),
    model_version               VARCHAR(50) NOT NULL,
    predicted_pts               NUMERIC(6,2),
    predicted_reb               NUMERIC(6,2),
    predicted_ast               NUMERIC(6,2),
    predicted_stl               NUMERIC(6,2),
    predicted_blk               NUMERIC(6,2),
    predicted_turnover          NUMERIC(6,2),
    predicted_fantasy_points    NUMERIC(6,2),
    actual_fantasy_points       NUMERIC(6,2),    -- backfilled once the game is played, for accuracy tracking
    prediction_date             TIMESTAMP DEFAULT NOW(),
    UNIQUE (player_id, game_id, model_version)
);

-- Helpful indexes for ETL upserts and prediction lookups
CREATE INDEX idx_players_team_id ON players(team_id);
CREATE INDEX idx_games_date ON games(date);
CREATE INDEX idx_games_season ON games(season);
CREATE INDEX idx_pgs_player_id ON player_game_stats(player_id);
CREATE INDEX idx_pgs_game_id ON player_game_stats(game_id);
CREATE INDEX idx_predictions_player_id ON predictions(player_id);
CREATE INDEX idx_predictions_game_id ON predictions(game_id);