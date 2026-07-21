INSERT INTO configuracion (
  id,
  correo_reportes,
  token_actual
)
VALUES (
  1,
  'correo@ejemplo.com',
  'pendiente'
)
ON CONFLICT (id) DO NOTHING;