-- Schema v21: bind wxzt login to its browser window and per-login origin.
ALTER TABLE sso_login_states ADD COLUMN IF NOT EXISTS wxzt_origin TEXT DEFAULT NULL;
ALTER TABLE sso_login_states ADD COLUMN IF NOT EXISTS wxzt_mode TEXT DEFAULT NULL;
ALTER TABLE sso_login_states ADD COLUMN IF NOT EXISTS wxzt_browser_challenge TEXT DEFAULT NULL;
UPDATE sso_providers SET dashboard_origin = NULL WHERE kind = 'wxzt';
UPDATE _schema_version SET version = 21;
