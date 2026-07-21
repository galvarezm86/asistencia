ALTER TABLE asistencias
ADD COLUMN device_id UUID;

ALTER TABLE asistencias
ADD COLUMN ip TEXT;

ALTER TABLE asistencias
ADD COLUMN user_agent TEXT;