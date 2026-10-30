-- Agro Asistente PMV1
-- Esquema reproducible de la base MySQL real (tablas en español, IDs INT AUTO_INCREMENT).
-- Collation unicode para compatibilidad con MySQL 8 y MariaDB de desarrollo local.

CREATE DATABASE IF NOT EXISTS agro_asistente
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE agro_asistente;

CREATE TABLE IF NOT EXISTS agricultores (
    id INT NOT NULL AUTO_INCREMENT,
    nombre_completo VARCHAR(150) NOT NULL,
    correo VARCHAR(150) NOT NULL,
    contrasena_hash VARCHAR(255) NOT NULL,
    fecha_creacion TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY correo (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contextos_agricolas (
    id INT NOT NULL AUTO_INCREMENT,
    agricultor_id INT NOT NULL,
    nombre_parcela VARCHAR(150) NOT NULL,
    cultivo VARCHAR(100) NOT NULL,
    region VARCHAR(100) NOT NULL,
    observaciones TEXT NULL,
    esta_seleccionado TINYINT(1) DEFAULT 0,
    fecha_creacion TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY fk_contexto_agricultor (agricultor_id),
    CONSTRAINT fk_contexto_agricultor
        FOREIGN KEY (agricultor_id) REFERENCES agricultores (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS consultas (
    id INT NOT NULL AUTO_INCREMENT,
    agricultor_id INT NOT NULL,
    contexto_id INT NOT NULL,
    pregunta TEXT NOT NULL,
    fecha_creacion TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY fk_consulta_agricultor (agricultor_id),
    KEY fk_consulta_contexto (contexto_id),
    CONSTRAINT fk_consulta_agricultor
        FOREIGN KEY (agricultor_id) REFERENCES agricultores (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_consulta_contexto
        FOREIGN KEY (contexto_id) REFERENCES contextos_agricolas (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS respuestas (
    id INT NOT NULL AUTO_INCREMENT,
    consulta_id INT NOT NULL,
    respuesta TEXT NOT NULL,
    metodo_generacion VARCHAR(50) NULL,
    fecha_creacion TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY fk_respuesta_consulta (consulta_id),
    CONSTRAINT fk_respuesta_consulta
        FOREIGN KEY (consulta_id) REFERENCES consultas (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS documentos_conocimiento (
    id INT NOT NULL AUTO_INCREMENT,
    ruta_origen VARCHAR(500) NOT NULL,
    hash_contenido VARCHAR(64) NOT NULL,
    fecha_creacion TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY hash_contenido (hash_contenido)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evidencias (
    id INT NOT NULL AUTO_INCREMENT,
    consulta_id INT NOT NULL,
    respuesta_id INT NULL,
    documento_id INT NOT NULL,
    titulo_documento VARCHAR(200) NOT NULL DEFAULT '',
    texto_fragmento TEXT NOT NULL,
    puntuacion_similitud DECIMAL(10,6) NULL,
    fecha_creacion TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY fk_evidencia_consulta (consulta_id),
    KEY fk_evidencia_respuesta (respuesta_id),
    KEY fk_evidencia_documento (documento_id),
    CONSTRAINT fk_evidencia_consulta
        FOREIGN KEY (consulta_id) REFERENCES consultas (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_evidencia_documento
        FOREIGN KEY (documento_id) REFERENCES documentos_conocimiento (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_evidencia_respuesta
        FOREIGN KEY (respuesta_id) REFERENCES respuestas (id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bases ya creadas: agrega el título sin recrear la tabla.
-- Las evidencias anteriores quedan con título vacío.
SET @columna_titulo := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'evidencias'
      AND COLUMN_NAME = 'titulo_documento'
);
SET @sql_titulo := IF(
    @columna_titulo = 0,
    'ALTER TABLE evidencias ADD COLUMN titulo_documento VARCHAR(200) NOT NULL DEFAULT '''' AFTER documento_id',
    'SELECT 1'
);
PREPARE stmt_titulo FROM @sql_titulo;
EXECUTE stmt_titulo;
DEALLOCATE PREPARE stmt_titulo;
