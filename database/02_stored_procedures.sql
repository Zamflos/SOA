-- ============================================================
-- Smart Fit Web Service - Función, vista y Stored Procedures
-- Convención: cada procedimiento devuelve
--   1er result set: (codigo, mensaje)   -> estado de la operación
--   2do result set: datos (socio o eventos), solo si codigo es 2xx
-- Los códigos coinciden con HTTP: 200, 201, 403, 404, 409, 422
-- ============================================================
SET NAMES utf8mb4;
USE smartfit;

DROP PROCEDURE IF EXISTS sp_consultar_membresia;
DROP PROCEDURE IF EXISTS sp_registrar_usuario;
DROP PROCEDURE IF EXISTS sp_registrar_acceso;
DROP PROCEDURE IF EXISTS sp_reservar_clase;
DROP PROCEDURE IF EXISTS sp_completar_rutina;
DROP PROCEDURE IF EXISTS sp_consultar_historial;
DROP PROCEDURE IF EXISTS sp_consultar_promociones;
DROP PROCEDURE IF EXISTS sp_canjear_promocion;
DROP PROCEDURE IF EXISTS sp_consultar_segmentos;
DROP VIEW IF EXISTS v_socios;
DROP FUNCTION IF EXISTS fn_segmento;

DELIMITER $$

-- 0. MARKETING: función que clasifica al socio en un segmento -----------------
--    Inactivo  : membresía inactiva
--    Nuevo     : se registró hace 30 días o menos
--    En riesgo : sin accesos, o su último acceso fue hace más de 30 días
--    Frecuente : 10 o más accesos
--    Activo    : cualquier otro socio con membresía activa
CREATE FUNCTION fn_segmento(p_user_id VARCHAR(12)) RETURNS VARCHAR(20)
READS SQL DATA
BEGIN
    DECLARE v_activa  BOOLEAN;
    DECLARE v_accesos INT;
    DECLARE v_creado  DATETIME;
    DECLARE v_ultimo  DATETIME;

    SELECT membresia_activa, accesos, creado INTO v_activa, v_accesos, v_creado
      FROM usuarios WHERE user_id = p_user_id;

    IF v_activa IS NULL THEN RETURN NULL; END IF;
    IF v_activa = FALSE THEN RETURN 'Inactivo'; END IF;
    IF DATEDIFF(NOW(), v_creado) <= 30 THEN RETURN 'Nuevo'; END IF;

    SELECT MAX(fecha) INTO v_ultimo FROM historial
     WHERE user_id = p_user_id AND tipo = 'qr_scan_entry';
    IF v_accesos = 0 OR v_ultimo IS NULL OR v_ultimo < DATE_SUB(NOW(), INTERVAL 30 DAY) THEN
        RETURN 'En riesgo';
    END IF;
    IF v_accesos >= 10 THEN RETURN 'Frecuente'; END IF;
    RETURN 'Activo';
END$$

DELIMITER ;

-- Vista auxiliar: un socio con sus clases reservadas y su segmento en una fila
CREATE VIEW v_socios AS
SELECT u.user_id, u.nombre, u.plan, u.sucursal, u.membresia_activa,
       u.accesos, u.rutinas_completadas,
       COALESCE((SELECT GROUP_CONCAT(r.clase ORDER BY r.clase SEPARATOR ',')
                   FROM reservas r WHERE r.user_id = u.user_id), '') AS clases,
       fn_segmento(u.user_id) AS segmento
FROM usuarios u;

DELIMITER $$

-- 1. Consultar membresía y actividad de un socio ---------------------------
CREATE PROCEDURE sp_consultar_membresia(IN p_user_id VARCHAR(12))
BEGIN
    IF NOT EXISTS (SELECT 1 FROM usuarios WHERE user_id = p_user_id) THEN
        SELECT 404 AS codigo, 'Usuario no encontrado' AS mensaje;
    ELSE
        SELECT 200 AS codigo, 'Consulta exitosa' AS mensaje;
        SELECT * FROM v_socios WHERE user_id = p_user_id;
    END IF;
END$$

-- 2. Registrar un socio nuevo ------------------------------------------------
CREATE PROCEDURE sp_registrar_usuario(
    IN p_user_id  VARCHAR(12),
    IN p_nombre   VARCHAR(80),
    IN p_plan     VARCHAR(10),
    IN p_sucursal VARCHAR(40))
BEGIN
    IF EXISTS (SELECT 1 FROM usuarios WHERE user_id = p_user_id) THEN
        SELECT 409 AS codigo, 'Ya existe un socio con ese userId' AS mensaje;
    ELSEIF p_plan NOT IN ('Smart','Black') THEN
        SELECT 422 AS codigo, 'Plan inválido (Smart o Black)' AS mensaje;
    ELSE
        INSERT INTO usuarios (user_id, nombre, plan, sucursal)
        VALUES (p_user_id, p_nombre, p_plan, p_sucursal);
        SELECT 201 AS codigo, 'Socio registrado correctamente' AS mensaje;
        SELECT * FROM v_socios WHERE user_id = p_user_id;
    END IF;
END$$

-- 3. Registrar acceso (evento qr_scan_entry) ---------------------------------
CREATE PROCEDURE sp_registrar_acceso(IN p_user_id VARCHAR(12))
BEGIN
    DECLARE v_activa BOOLEAN;
    SELECT membresia_activa INTO v_activa FROM usuarios WHERE user_id = p_user_id;

    IF v_activa IS NULL THEN
        SELECT 404 AS codigo, 'Usuario no encontrado' AS mensaje;
    ELSEIF v_activa = FALSE THEN
        SELECT 403 AS codigo, 'Membresía inactiva' AS mensaje;
    ELSE
        UPDATE usuarios SET accesos = accesos + 1 WHERE user_id = p_user_id;
        INSERT INTO historial (user_id, tipo) VALUES (p_user_id, 'qr_scan_entry');
        SELECT 200 AS codigo, 'Acceso registrado correctamente (qr_scan_entry)' AS mensaje;
        SELECT * FROM v_socios WHERE user_id = p_user_id;
    END IF;
END$$

-- 4. Reservar clase (evento class_booked) ------------------------------------
CREATE PROCEDURE sp_reservar_clase(IN p_user_id VARCHAR(12), IN p_clase VARCHAR(30))
BEGIN
    DECLARE v_activa BOOLEAN;
    SELECT membresia_activa INTO v_activa FROM usuarios WHERE user_id = p_user_id;

    IF v_activa IS NULL THEN
        SELECT 404 AS codigo, 'Usuario no encontrado' AS mensaje;
    ELSEIF v_activa = FALSE THEN
        SELECT 403 AS codigo, 'Membresía inactiva' AS mensaje;
    ELSEIF NOT EXISTS (SELECT 1 FROM clases WHERE nombre = p_clase) THEN
        SELECT 422 AS codigo, 'La clase no existe en el catálogo' AS mensaje;
    ELSEIF EXISTS (SELECT 1 FROM reservas WHERE user_id = p_user_id AND clase = p_clase) THEN
        SELECT 409 AS codigo, 'Ya tienes reservada esa clase' AS mensaje;
    ELSE
        INSERT INTO reservas (user_id, clase) VALUES (p_user_id, p_clase);
        INSERT INTO historial (user_id, tipo, detalle) VALUES (p_user_id, 'class_booked', p_clase);
        SELECT 201 AS codigo, 'Clase reservada correctamente (class_booked)' AS mensaje;
        SELECT * FROM v_socios WHERE user_id = p_user_id;
    END IF;
END$$

-- 5. Completar rutina (evento workout_routine_completed) --------------------
CREATE PROCEDURE sp_completar_rutina(IN p_user_id VARCHAR(12))
BEGIN
    DECLARE v_activa BOOLEAN;
    SELECT membresia_activa INTO v_activa FROM usuarios WHERE user_id = p_user_id;

    IF v_activa IS NULL THEN
        SELECT 404 AS codigo, 'Usuario no encontrado' AS mensaje;
    ELSEIF v_activa = FALSE THEN
        SELECT 403 AS codigo, 'Membresía inactiva' AS mensaje;
    ELSE
        UPDATE usuarios SET rutinas_completadas = rutinas_completadas + 1 WHERE user_id = p_user_id;
        INSERT INTO historial (user_id, tipo) VALUES (p_user_id, 'workout_routine_completed');
        SELECT 200 AS codigo, 'Rutina completada (workout_routine_completed)' AS mensaje;
        SELECT * FROM v_socios WHERE user_id = p_user_id;
    END IF;
END$$

-- 6. Consultar historial (de un socio o de todos si p_user_id es vacío) ----
CREATE PROCEDURE sp_consultar_historial(IN p_user_id VARCHAR(12), IN p_limite INT)
BEGIN
    IF p_user_id <> '' AND NOT EXISTS (SELECT 1 FROM usuarios WHERE user_id = p_user_id) THEN
        SELECT 404 AS codigo, 'Usuario no encontrado' AS mensaje;
    ELSE
        SELECT 200 AS codigo, 'Consulta exitosa' AS mensaje;
        SELECT id, user_id, tipo, detalle, fecha
          FROM historial
         WHERE p_user_id = '' OR user_id = p_user_id
         ORDER BY id DESC
         LIMIT p_limite;
    END IF;
END$$

-- 7. MARKETING: promociones disponibles para un socio -----------------------
CREATE PROCEDURE sp_consultar_promociones(IN p_user_id VARCHAR(12))
BEGIN
    DECLARE v_plan VARCHAR(10);
    DECLARE v_seg  VARCHAR(20);
    SELECT plan INTO v_plan FROM usuarios WHERE user_id = p_user_id;

    IF v_plan IS NULL THEN
        SELECT 404 AS codigo, 'Usuario no encontrado' AS mensaje;
    ELSE
        SET v_seg = fn_segmento(p_user_id);
        SELECT 200 AS codigo, CONCAT('Promociones para el segmento ', v_seg) AS mensaje;
        SELECT v_seg AS segmento;
        SELECT p.codigo, p.titulo, p.descripcion, p.descuento_pct, p.vigente_hasta
          FROM promociones p
         WHERE p.activa AND p.vigente_hasta >= CURDATE()
           AND FIND_IN_SET(v_seg, p.segmentos) > 0
           AND (p.plan_requerido IS NULL OR p.plan_requerido = v_plan)
           AND NOT EXISTS (SELECT 1 FROM canjes c
                            WHERE c.user_id = p_user_id AND c.codigo = p.codigo)
         ORDER BY p.descuento_pct DESC, p.codigo;
    END IF;
END$$

-- 8. MARKETING: canjear una promoción (evento promo_redeemed) ---------------
CREATE PROCEDURE sp_canjear_promocion(IN p_user_id VARCHAR(12), IN p_codigo VARCHAR(20))
BEGIN
    DECLARE v_plan VARCHAR(10);
    DECLARE v_seg  VARCHAR(20);
    SELECT plan INTO v_plan FROM usuarios WHERE user_id = p_user_id;

    IF v_plan IS NULL THEN
        SELECT 404 AS codigo, 'Usuario no encontrado' AS mensaje;
    ELSEIF NOT EXISTS (SELECT 1 FROM promociones
                        WHERE codigo = p_codigo AND activa AND vigente_hasta >= CURDATE()) THEN
        SELECT 404 AS codigo, 'Promoción no encontrada o vencida' AS mensaje;
    ELSEIF EXISTS (SELECT 1 FROM canjes WHERE user_id = p_user_id AND codigo = p_codigo) THEN
        SELECT 409 AS codigo, 'Ya canjeaste esta promoción' AS mensaje;
    ELSE
        SET v_seg = fn_segmento(p_user_id);
        IF NOT EXISTS (SELECT 1 FROM promociones p
                        WHERE p.codigo = p_codigo
                          AND FIND_IN_SET(v_seg, p.segmentos) > 0
                          AND (p.plan_requerido IS NULL OR p.plan_requerido = v_plan)) THEN
            SELECT 422 AS codigo, 'No eres elegible para esta promoción' AS mensaje;
        ELSE
            INSERT INTO canjes (user_id, codigo) VALUES (p_user_id, p_codigo);
            INSERT INTO historial (user_id, tipo, detalle) VALUES (p_user_id, 'promo_redeemed', p_codigo);
            SELECT 201 AS codigo, 'Promoción canjeada correctamente (promo_redeemed)' AS mensaje;
            SELECT v_seg AS segmento;
            SELECT codigo, titulo, descripcion, descuento_pct, vigente_hasta
              FROM promociones WHERE codigo = p_codigo;
        END IF;
    END IF;
END$$

-- 9. MARKETING: cuántos socios hay en cada segmento (para campañas) ---------
CREATE PROCEDURE sp_consultar_segmentos()
BEGIN
    SELECT 200 AS codigo, 'Consulta exitosa' AS mensaje;
    SELECT s.segmento, COUNT(*) AS total
      FROM (SELECT fn_segmento(user_id) AS segmento FROM usuarios) s
     GROUP BY s.segmento
     ORDER BY total DESC, s.segmento;
END$$

DELIMITER ;
