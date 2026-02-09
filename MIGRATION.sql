-- Выполните этот запрос в Railway -> PostgreSQL -> Data -> Query
-- Это добавит недостающие колонки для админки

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_by BIGINT;

CREATE INDEX IF NOT EXISTS ix_users_is_blocked ON users (is_blocked);
