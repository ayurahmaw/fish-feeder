-- ============================================================================
-- feeder_db — User MySQL khusus aplikasi backend (jangan pakai root)
-- Jalankan: mysql -u root -p < database/app_user.sql
-- Catatan: password di bawah hanya untuk local development.
-- ============================================================================

CREATE USER IF NOT EXISTS 'feeder_app'@'localhost' IDENTIFIED BY 'feeder_dev_123';

GRANT SELECT, INSERT, UPDATE, DELETE ON feeder_db.* TO 'feeder_app'@'localhost';

FLUSH PRIVILEGES;

-- Verifikasi:
--   mysql -u feeder_app -pfeeder_dev_123 feeder_db -e "SELECT device_code, name FROM devices;"
