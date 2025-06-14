-- Table des sessions vocales
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_seconds INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_sessions_end_time ON sessions(end_time);

-- Table des streaks
CREATE TABLE IF NOT EXISTS streaks (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_active_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour les streaks
CREATE INDEX IF NOT EXISTS idx_streaks_user_id ON streaks(user_id);
CREATE INDEX IF NOT EXISTS idx_streaks_last_active_date ON streaks(last_active_date);

-- Table des rôles utilisateurs
CREATE TABLE IF NOT EXISTS user_roles (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    role_name TEXT NOT NULL,
    hours_required REAL NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour les rôles
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);

-- Table de la discipline
CREATE TABLE IF NOT EXISTS user_discipline (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    discipline_level INTEGER DEFAULT 0,
    best_discipline_level INTEGER DEFAULT 0,
    last_check TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour la discipline
CREATE INDEX IF NOT EXISTS idx_user_discipline_user_id ON user_discipline(user_id);
CREATE INDEX IF NOT EXISTS idx_user_discipline_last_check ON user_discipline(last_check);

-- Table des statistiques mensuelles
CREATE TABLE IF NOT EXISTS monthly_stats (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    month DATE NOT NULL,
    total_seconds INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, month)
);

-- Index pour les statistiques mensuelles
CREATE INDEX IF NOT EXISTS idx_monthly_stats_user_id ON monthly_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_monthly_stats_month ON monthly_stats(month);

-- Fonction pour mettre à jour updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Procédure pour agréger les anciennes sessions
CREATE OR REPLACE PROCEDURE aggregate_old_sessions()
LANGUAGE plpgsql
AS $$
BEGIN
    -- Agréger les anciennes sessions
    INSERT INTO monthly_stats (user_id, month, total_seconds)
    SELECT 
        user_id,
        DATE_TRUNC('month', start_time)::date,
        SUM(duration_seconds)
    FROM sessions
    WHERE start_time < NOW() - INTERVAL '6 months'
    GROUP BY user_id, DATE_TRUNC('month', start_time)
    ON CONFLICT (user_id, month) 
    DO UPDATE SET 
        total_seconds = EXCLUDED.total_seconds;

    -- Supprimer les anciennes sessions
    DELETE FROM sessions 
    WHERE start_time < NOW() - INTERVAL '6 months';
END;
$$;

-- Suppression des anciens triggers s'ils existent
DROP TRIGGER IF EXISTS update_streaks_updated_at ON streaks;
DROP TRIGGER IF EXISTS update_user_roles_updated_at ON user_roles;
DROP TRIGGER IF EXISTS update_user_discipline_updated_at ON user_discipline;

-- Création des triggers
CREATE TRIGGER update_streaks_updated_at
    BEFORE UPDATE ON streaks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_roles_updated_at
    BEFORE UPDATE ON user_roles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_discipline_updated_at
    BEFORE UPDATE ON user_discipline
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 