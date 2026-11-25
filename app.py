"""
Smart Fit Web Service (backend)
Recibe un REQUEST en XML, lo valida contra solicitud.xsd, ejecuta el stored
procedure correspondiente en MySQL/MariaDB y devuelve un RESPONSE en XML.

Ejecutar:
    pip install -r requirements.txt
    python app.py
End Point:  POST http://127.0.0.1:5000/ws/smartfit   (Content-Type: application/xml)
Cliente:    http://127.0.0.1:5000/
"""
import os

import pymysql
from flask import Flask, Response, request, send_from_directory
from lxml import etree

BASE = os.path.dirname(os.path.abspath(__file__))
NS = "http://smartfit.uadeo.mx/ws"

# Conexión: por defecto XAMPP (root sin contraseña). Cambiable con variables de entorno.
DB_CONFIG = dict(
    host=os.getenv("SMARTFIT_DB_HOST", "127.0.0.1"),
    port=int(os.getenv("SMARTFIT_DB_PORT", "3306")),
    user=os.getenv("SMARTFIT_DB_USER", "root"),
    password=os.getenv("SMARTFIT_DB_PASS", ""),
    database=os.getenv("SMARTFIT_DB_NAME", "smartfit"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # un request XML nunca debería pesar más

XSD_SOLICITUD = etree.XMLSchema(etree.parse(os.path.join(BASE, "xml", "solicitud.xsd")))
XSD_RESPUESTA = etree.XMLSchema(etree.parse(os.path.join(BASE, "xml", "respuesta.xsd")))
# Parser seguro: sin entidades externas ni acceso a red (evita ataques XXE)
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)

# operacion -> (stored procedure, parámetros obligatorios, función que arma los argumentos)
OPERACIONES = {
    "consultarMembresia": ("sp_consultar_membresia", ["userId"],
                           lambda p: [p["userId"]]),
    "registrarUsuario":   ("sp_registrar_usuario", ["userId", "nombre", "plan", "sucursal"],
                           lambda p: [p["userId"], p["nombre"], p["plan"], p["sucursal"]]),
    "registrarAcceso":    ("sp_registrar_acceso", ["userId"],
                           lambda p: [p["userId"]]),
    "reservarClase":      ("sp_reservar_clase", ["userId", "clase"],
                           lambda p: [p["userId"], p["clase"].capitalize()]),
    "completarRutina":    ("sp_completar_rutina", ["userId"],
                           lambda p: [p["userId"]]),
    "consultarHistorial": ("sp_consultar_historial", [],
                           lambda p: [p.get("userId", ""), int(p.get("limite", 20))]),
    # --- Marketing ---
    "consultarPromociones": ("sp_consultar_promociones", ["userId"],
                             lambda p: [p["userId"]]),
    "canjearPromocion":     ("sp_canjear_promocion", ["userId", "codigo"],
                             lambda p: [p["userId"], p["codigo"].upper()]),
    "consultarSegmentos":   ("sp_consultar_segmentos", [],
                             lambda p: []),
}
# tipo de bloque <datos> que produce cada operación cuando tiene éxito
TIPO_DATOS = {"consultarHistorial": "eventos", "consultarPromociones": "marketing",
              "canjearPromocion": "marketing", "consultarSegmentos": "segmentos"}


def q(tag):
    return f"{{{NS}}}{tag}"


def agregar(padre, tag, texto=None):
    e = etree.SubElement(padre, q(tag))
    if texto is not None:
        e.text = str(texto)
    return e


def construir_respuesta(codigo, mensaje, sets=None, tipo_datos=None):
    """Arma el XML de respuesta. sets: result sets del stored procedure (después del de estado).
    tipo_datos: 'socio', 'eventos', 'marketing' o 'segmentos'."""
    datos = sets[0] if sets else ()
    raiz = etree.Element(q("RespuestaSmartFit"), nsmap={None: NS})
    agregar(raiz, "estado", "OK" if codigo < 300 else "ERROR")
    agregar(raiz, "codigo", codigo)
    agregar(raiz, "mensaje", mensaje)

    if tipo_datos == "socio" and datos:
        s = agregar(agregar(raiz, "datos"), "socio")
        f = datos[0]
        agregar(s, "userId", f["user_id"])
        agregar(s, "nombre", f["nombre"])
        agregar(s, "plan", f["plan"])
        agregar(s, "sucursal", f["sucursal"])
        agregar(s, "membresiaActiva", "true" if f["membresia_activa"] else "false")
        agregar(s, "accesos", f["accesos"])
        agregar(s, "rutinasCompletadas", f["rutinas_completadas"])
        clases = agregar(s, "clasesReservadas")
        for c in filter(None, f["clases"].split(",")):
            agregar(clases, "clase", c)
        agregar(s, "segmento", f["segmento"])
    elif tipo_datos == "eventos":
        ev = agregar(agregar(raiz, "datos"), "eventos")
        for f in datos:
            e = agregar(ev, "evento")
            agregar(e, "id", f["id"])
            agregar(e, "userId", f["user_id"])
            agregar(e, "tipo", f["tipo"])
            if f["detalle"] is not None:
                agregar(e, "detalle", f["detalle"])
            agregar(e, "fecha", f["fecha"].strftime("%Y-%m-%dT%H:%M:%S"))
    elif tipo_datos == "marketing":
        m = agregar(agregar(raiz, "datos"), "marketing")
        agregar(m, "segmento", datos[0]["segmento"])
        promos = agregar(m, "promociones")
        for f in sets[1]:
            p = agregar(promos, "promocion")
            agregar(p, "codigo", f["codigo"])
            agregar(p, "titulo", f["titulo"])
            agregar(p, "descripcion", f["descripcion"])
            agregar(p, "descuentoPct", f["descuento_pct"])
            agregar(p, "vigenteHasta", f["vigente_hasta"].strftime("%Y-%m-%d"))
    elif tipo_datos == "segmentos":
        seg = agregar(agregar(raiz, "datos"), "segmentos")
        for f in datos:
            s = agregar(seg, "segmento")
            agregar(s, "nombre", f["segmento"])
            agregar(s, "total", f["total"])
    return raiz


def responder(codigo, mensaje, sets=None, tipo_datos=None):
    raiz = construir_respuesta(codigo, mensaje, sets, tipo_datos)
    if not XSD_RESPUESTA.validate(raiz):  # el propio servicio cumple su contrato
        raiz = construir_respuesta(500, "La respuesta generada no cumple respuesta.xsd")
        codigo = 500
    cuerpo = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return Response(cuerpo, status=codigo, mimetype="application/xml")


def ejecutar_sp(nombre, args):
    """Llama un stored procedure. Devuelve (fila_estado, [result sets de datos])."""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.callproc(nombre, args)
            estado = cur.fetchone()
            sets = []
            while cur.nextset():
                sets.append(cur.fetchall())
        conn.commit()
        return estado, sets
    finally:
        conn.close()


@app.post("/ws/smartfit")
def ws_smartfit():
    # 1. Parsear el XML
    try:
        doc = etree.fromstring(request.get_data(), parser=PARSER)
    except etree.XMLSyntaxError as e:
        return responder(400, f"XML mal formado: {e}")

    # 2. Validar contra el esquema del request
    if not XSD_SOLICITUD.validate(doc):
        return responder(400, f"La solicitud no cumple solicitud.xsd: {XSD_SOLICITUD.error_log.last_error.message}")

    operacion = doc.findtext(q("operacion"))
    params = {etree.QName(h).localname: (h.text or "").strip() for h in doc.find(q("parametros"))}

    # 3. Verificar parámetros obligatorios de la operación
    sp, obligatorios, armar = OPERACIONES[operacion]
    faltan = [p for p in obligatorios if not params.get(p)]
    if faltan:
        return responder(400, f"Falta el parámetro obligatorio: {', '.join(faltan)}")

    # 4. Ejecutar el stored procedure
    try:
        estado, sets = ejecutar_sp(sp, armar(params))
    except pymysql.MySQLError as e:
        app.logger.error("Error de base de datos: %s", e)
        return responder(500, "Error al comunicarse con la base de datos")

    tipo = None
    if estado["codigo"] < 300:
        tipo = TIPO_DATOS.get(operacion, "socio")
    return responder(estado["codigo"], estado["mensaje"], sets, tipo)


@app.errorhandler(413)
def demasiado_grande(_):
    return responder(400, "La solicitud excede el tamaño máximo permitido (64 KB)")


@app.route("/xsd/<nombre>")
def descargar_xsd(nombre):
    """Los esquemas se publican para el equipo de desarrollo del lado del cliente."""
    if nombre not in ("solicitud.xsd", "respuesta.xsd"):
        return Response("No encontrado", status=404)
    return send_from_directory(os.path.join(BASE, "xml"), nombre, mimetype="application/xml")


@app.route("/")
def cliente():
    return send_from_directory(os.path.join(BASE, "cliente"), "index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
