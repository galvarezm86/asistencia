ALTER TABLE configuracion
ADD COLUMN qr_auto_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE configuracion
ADD COLUMN qr_auto_day INTEGER;

ALTER TABLE configuracion
ADD COLUMN qr_auto_time VARCHAR(5);

ALTER TABLE configuracion
ADD COLUMN report_auto_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE configuracion
ADD COLUMN report_auto_day INTEGER;

ALTER TABLE configuracion
ADD COLUMN report_auto_time VARCHAR(5);