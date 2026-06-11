INSERT into personas (id, nombre) VALUES (1, 'AARON FLORES ROJAS');
INSERT into personas (id, nombre) VALUES (2, 'ALEXI ARAYA ALCAYAGA');
INSERT into personas (id, nombre) VALUES (3, 'ANAIS ROZAS ESCOBAR');
INSERT into personas (id, nombre) VALUES (4, 'FELIPE ROZAS ESCOBAR');
INSERT into personas (id, nombre) VALUES (5, 'JONATHAN GUTIERREZ CHIRINO');
INSERT into personas (id, nombre) VALUES (6, 'MAITTE MARDONES DIAZ');
INSERT into personas (id, nombre) VALUES (7, 'MARIA JOSE GALVEZ');
INSERT into personas (id, nombre) VALUES (8, 'MAXIMO SALAZAR GUTIERREZ');
INSERT into personas (id, nombre) VALUES (9, 'MICHAEL ARAVENA BETANCOURT');
INSERT into personas (id, nombre) VALUES (10, 'MILUSKA NUÑEZ');
INSERT into personas (id, nombre) VALUES (11, 'SEBASTIAN PRADENA ROJAS');

INSERT into asistencias (persona_id, fecha_hora) VALUES (2, '2026-05-09 19:49:18');
INSERT into asistencias (persona_id, fecha_hora) VALUES (6, '2026-05-09 19:49:46');
INSERT into asistencias (persona_id, fecha_hora) VALUES (1, '2026-05-09 19:49:55');
INSERT into asistencias (persona_id, fecha_hora) VALUES (8, '2026-05-09 19:51:12');
INSERT into asistencias (persona_id, fecha_hora) VALUES (2, '2026-05-16 19:49:25');
INSERT into asistencias (persona_id, fecha_hora) VALUES (1, '2026-05-16 19:49:36');
INSERT into asistencias (persona_id, fecha_hora) VALUES (4, '2026-05-16 19:49:37');
INSERT into asistencias (persona_id, fecha_hora) VALUES (6, '2026-05-16 19:50:11');
INSERT into asistencias (persona_id, fecha_hora) VALUES (8, '2026-05-16 19:50:21');
INSERT into asistencias (persona_id, fecha_hora) VALUES (3, '2026-05-16 19:50:21');
INSERT into asistencias (persona_id, fecha_hora) VALUES (5, '2026-05-16 19:50:41');
INSERT into asistencias (persona_id, fecha_hora) VALUES (6, '2026-05-23 14:44:08');
INSERT into asistencias (persona_id, fecha_hora) VALUES (8, '2026-05-23 14:44:15');
INSERT into asistencias (persona_id, fecha_hora) VALUES (4, '2026-05-23 14:44:18');
INSERT into asistencias (persona_id, fecha_hora) VALUES (3, '2026-05-23 14:44:28');
INSERT into asistencias (persona_id, fecha_hora) VALUES (11, '2026-05-23 14:44:38');
INSERT into asistencias (persona_id, fecha_hora) VALUES (1, '2026-05-23 14:44:40');

SELECT setval(
    pg_get_serial_sequence('personas', 'id'),
    COALESCE((SELECT MAX(id) FROM personas), 1)
);

SELECT setval(
    pg_get_serial_sequence('asistencias', 'id'),
    COALESCE((SELECT MAX(id) FROM asistencias), 1)
);
