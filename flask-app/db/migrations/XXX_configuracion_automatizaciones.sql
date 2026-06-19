ALTER TABLE configuracion
ADD COLUMN qr_auto_enabled BOOLEAN NOT NULL DEFAULT 0;

ALTER TABLE configuracion
ADD COLUMN qr_auto_day INTEGER;

ALTER TABLE configuracion
ADD COLUMN qr_auto_time TEXT;

ALTER TABLE configuracion
ADD COLUMN report_auto_enabled BOOLEAN NOT NULL DEFAULT 0;

ALTER TABLE configuracion
ADD COLUMN report_auto_day INTEGER;

ALTER TABLE configuracion
ADD COLUMN report_auto_time TEXT;