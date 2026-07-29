CREATE TABLE IF NOT EXISTS personas (

    id SERIAL PRIMARY KEY,

    nombre TEXT NOT NULL UNIQUE,

    activo INTEGER NOT NULL DEFAULT 1

);

CREATE TABLE IF NOT EXISTS asistencias (

    id SERIAL PRIMARY KEY,

    persona_id INTEGER NOT NULL,

    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    device_id UUID,

    ip TEXT,

    user_agent TEXT,    

    FOREIGN KEY (persona_id)
        REFERENCES personas(id)
        ON DELETE RESTRICT

);

CREATE UNIQUE INDEX IF NOT EXISTS idx_asistencia_unica
ON asistencias (
    persona_id,
    (DATE(fecha_hora))
);

CREATE TABLE IF NOT EXISTS configuracion (

    id INTEGER PRIMARY KEY CHECK (id = 1),

    correo_reportes TEXT NOT NULL,

    token_actual TEXT NOT NULL,

    qr_updated_at TIMESTAMP

);

CREATE TABLE IF NOT EXISTS usuarios (

    id SERIAL PRIMARY KEY,

    username VARCHAR(50) NOT NULL UNIQUE,

    password_hash TEXT NOT NULL,

    rol VARCHAR(20) NOT NULL,

    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,

    restauracion_pendiente BOOLEAN NOT NULL DEFAULT FALSE,

    activo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

);
