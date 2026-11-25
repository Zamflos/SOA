-- ============================================================
-- Smart Fit Web Service - Esquema de base de datos
-- Compatible con MySQL 5.7+ / MariaDB 10.3+ (XAMPP)
-- ============================================================
SET NAMES utf8mb4;
DROP DATABASE IF EXISTS smartfit;
CREATE DATABASE smartfit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smartfit;

CREATE TABLE clases (
    nombre VARCHAR(30) PRIMARY KEY
) ENGINE=InnoDB;

CREATE TABLE usuarios (
    user_id             VARCHAR(12)  PRIMARY KEY,
    nombre              VARCHAR(80)  NOT NULL,
    plan                ENUM('Smart','Black') NOT NULL,
    sucursal            VARCHAR(40)  NOT NULL,
    membresia_activa    BOOLEAN      NOT NULL DEFAULT TRUE,
    accesos             INT          NOT NULL DEFAULT 0,
    rutinas_completadas INT          NOT NULL DEFAULT 0,
    creado              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE reservas (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    user_id   VARCHAR(12) NOT NULL,
    clase     VARCHAR(30) NOT NULL,
    fecha     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_usuario_clase (user_id, clase),
    FOREIGN KEY (user_id) REFERENCES usuarios(user_id) ON DELETE CASCADE,
    FOREIGN KEY (clase)   REFERENCES clases(nombre)
) ENGINE=InnoDB;

CREATE TABLE historial (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id  VARCHAR(12) NOT NULL,
    tipo     VARCHAR(40) NOT NULL,      -- qr_scan_entry, class_booked, workout_routine_completed
    detalle  VARCHAR(60) NULL,
    fecha    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES usuarios(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Marketing: catálogo de promociones y registro de canjes
CREATE TABLE promociones (
    codigo          VARCHAR(20)  PRIMARY KEY,
    titulo          VARCHAR(60)  NOT NULL,
    descripcion     VARCHAR(160) NOT NULL,
    descuento_pct   TINYINT      NOT NULL DEFAULT 0,
    segmentos       SET('Nuevo','Activo','Frecuente','En riesgo','Inactivo') NOT NULL,
    plan_requerido  ENUM('Smart','Black') NULL,       -- NULL = aplica a cualquier plan
    activa          BOOLEAN      NOT NULL DEFAULT TRUE,
    vigente_hasta   DATE         NOT NULL
) ENGINE=InnoDB;

CREATE TABLE canjes (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id  VARCHAR(12) NOT NULL,
    codigo   VARCHAR(20) NOT NULL,
    fecha    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_canje (user_id, codigo),
    FOREIGN KEY (user_id) REFERENCES usuarios(user_id) ON DELETE CASCADE,
    FOREIGN KEY (codigo)  REFERENCES promociones(codigo)
) ENGINE=InnoDB;

-- Datos iniciales
INSERT INTO clases (nombre) VALUES
    ('Spinning'),('Zumba'),('Yoga'),('Funcional'),('Box'),('Pilates');

INSERT INTO usuarios (user_id, nombre, plan, sucursal, membresia_activa) VALUES
    ('23050292', 'Malcom Flores',  'Black', 'Mazatlán Centro', TRUE),
    ('23050293', 'Isaac Rosales',  'Smart', 'Mazatlán Norte',  TRUE);

INSERT INTO promociones (codigo, titulo, descripcion, descuento_pct, segmentos, plan_requerido, vigente_hasta) VALUES
 ('BIENVENIDA20', 'Bienvenida',        '20% de descuento en tu primera sesión de entrenamiento personalizado', 20, 'Nuevo',               NULL,    DATE_ADD(CURDATE(), INTERVAL 90 DAY)),
 ('TRAEAMIGO',    'Trae a un amigo',   'Invita a un amigo y ambos reciben 10% en la mensualidad',               10, 'Nuevo,Activo',       NULL,    DATE_ADD(CURDATE(), INTERVAL 90 DAY)),
 ('UPGRADEBLACK', 'Pásate a Black',    '25% de descuento en tu primer mes si cambias al plan Black',            25, 'Activo,Frecuente',   'Smart', DATE_ADD(CURDATE(), INTERVAL 90 DAY)),
 ('FRECUENTE15',  'Premio a tu constancia', '15% de descuento en la tienda de suplementos y accesorios',         15, 'Frecuente',          NULL,    DATE_ADD(CURDATE(), INTERVAL 90 DAY)),
 ('INVITADOBLACK','Pase de invitado',  'Un pase de invitado gratis cada mes para tu acompañante',                0, 'Activo,Frecuente',   'Black', DATE_ADD(CURDATE(), INTERVAL 90 DAY)),
 ('VUELVE30',     'Vuelve a entrenar', '30% de descuento en una clase especial si regresas esta semana',        30, 'En riesgo',          NULL,    DATE_ADD(CURDATE(), INTERVAL 90 DAY)),
 ('REACTIVA50',   'Reactiva tu membresía', '50% de descuento en tu primer mes al reactivar tu membresía',        50, 'Inactivo',           NULL,    DATE_ADD(CURDATE(), INTERVAL 90 DAY));
