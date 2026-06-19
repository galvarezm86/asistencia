CREATE TABLE IF NOT EXISTS personas (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    nombre TEXT NOT NULL UNIQUE,

    activo INTEGER NOT NULL DEFAULT 1

);

CREATE TABLE IF NOT EXISTS asistencias (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    persona_id INTEGER NOT NULL,

    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (persona_id)
        REFERENCES personas(id)
        ON DELETE RESTRICT

);

CREATE UNIQUE INDEX IF NOT EXISTS idx_asistencia_unica
ON asistencias (
    persona_id,
    date(fecha_hora)
);

CREATE TABLE IF NOT EXISTS configuracion (

    id INTEGER PRIMARY KEY CHECK (id = 1),

    correo_reportes TEXT NOT NULL,
    
    token_actual TEXT NOT NULL,

    qr_updated_at TIMESTAMP

);

