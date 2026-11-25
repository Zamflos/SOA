"""
Smart Fit Web Service - SOA
Servicio web en Flask con interfaz web (templates/index.html).

Ejecutar:
    pip install flask
    python smartfit_service.py
Abrir: http://127.0.0.1:5000
"""
import json
import os
import threading
from collections import Counter
from datetime import datetime

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.json.ensure_ascii = False          # respeta acentos en las respuestas JSON
app.json.sort_keys = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "datos.json")
LOCK = threading.Lock()

PLANES = ["Smart", "Black"]
SUCURSALES = ["Mazatlán Centro", "Mazatlán Norte", "Mazatlán Marina"]
CLASES = ["Spinning", "Zumba", "Yoga", "Funcional", "Box", "Pilates"]

# Nombres de eventos (los mismos que usa la app real)
EVT_ACCESO = "qr_scan_entry"
EVT_RESERVA = "class_booked"
EVT_CANCELA = "class_cancelled"
EVT_RUTINA = "workout_routine_completed"


# ----------------------------------------------------------------------------
# Persistencia
# ----------------------------------------------------------------------------
def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def usuario_nuevo(nombre, plan, sucursal, activa=True):
    return {
        "nombre": nombre,
        "membresia_activa": activa,
        "plan": plan,
        "sucursal": sucursal,
        "accesos": 0,
        "clases_reservadas": [],
        "rutinas_completadas": 0,
        "creado": ahora(),
    }


def datos_semilla():
    return {
        "usuarios": {
            "23050292": usuario_nuevo("Malcom Flores", "Black", "Mazatlán Centro"),
            "23050293": usuario_nuevo("Isaac Rosales", "Smart", "Mazatlán Norte"),
        },
        "historial": [],
    }


def cargar():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return datos_semilla()


def guardar():
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(DB, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


DB = cargar()


def registrar_evento(user_id, tipo, detalle=None):
    evento = {
        "id": len(DB["historial"]) + 1,
        "user_id": user_id,
        "tipo": tipo,
        "detalle": detalle,
        "fecha": ahora(),
    }
    DB["historial"].append(evento)
    return evento


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def error(mensaje, codigo):
    return jsonify({"error": mensaje}), codigo


def cuerpo():
    """Devuelve el JSON del request o {} si no viene o es inválido."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def validar_usuario(data, parcial=False):
    """Valida y limpia los campos de un usuario. Devuelve (datos, errores)."""
    limpio, errores = {}, []

    if not parcial or "nombre" in data:
        nombre = str(data.get("nombre", "")).strip()
        if len(nombre) < 3:
            errores.append("El nombre debe tener al menos 3 caracteres")
        limpio["nombre"] = nombre

    if not parcial or "plan" in data:
        plan = str(data.get("plan", "")).strip().capitalize()
        if plan not in PLANES:
            errores.append(f"Plan inválido. Opciones: {', '.join(PLANES)}")
        limpio["plan"] = plan

    if not parcial or "sucursal" in data:
        sucursal = str(data.get("sucursal", "")).strip()
        if not sucursal:
            errores.append("La sucursal es obligatoria")
        limpio["sucursal"] = sucursal

    if "membresia_activa" in data:
        if not isinstance(data["membresia_activa"], bool):
            errores.append("membresia_activa debe ser true o false")
        limpio["membresia_activa"] = data["membresia_activa"]

    return limpio, errores


def usuario_activo(user_id):
    """Devuelve (usuario, respuesta_de_error). Una de las dos es None."""
    user = DB["usuarios"].get(user_id)
    if user is None:
        return None, error("Usuario no encontrado", 404)
    if not user["membresia_activa"]:
        return None, error("Membresía inactiva", 403)
    return user, None


# ----------------------------------------------------------------------------
# Interfaz web e información del servicio
# ----------------------------------------------------------------------------
@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/api")
def info_api():
    return jsonify({
        "servicio": "Smart Fit Web Service - SOA",
        "version": "2.0",
        "endpoints": [
            "GET    /usuarios            (filtros: plan, sucursal, activa)",
            "POST   /usuarios",
            "GET    /usuarios/<user_id>",
            "PUT    /usuarios/<user_id>",
            "DELETE /usuarios/<user_id>",
            "GET    /membresia/<user_id>",
            "POST   /acceso              (qr_scan_entry)",
            "POST   /reservar_clase      (class_booked)",
            "DELETE /reservar_clase      (class_cancelled)",
            "POST   /completar_rutina    (workout_routine_completed)",
            "GET    /clases",
            "GET    /historial           (filtros: user_id, tipo, limite)",
            "GET    /estadisticas",
        ],
    })


@app.route("/clases", methods=["GET"])
def listar_clases():
    return jsonify({"clases": CLASES, "planes": PLANES, "sucursales": SUCURSALES})


# ----------------------------------------------------------------------------
# CRUD de usuarios
# ----------------------------------------------------------------------------
@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    plan = request.args.get("plan")
    sucursal = request.args.get("sucursal")
    activa = request.args.get("activa")

    resultado = []
    for uid, u in DB["usuarios"].items():
        if plan and u["plan"].lower() != plan.lower():
            continue
        if sucursal and u["sucursal"].lower() != sucursal.lower():
            continue
        if activa in ("true", "false") and u["membresia_activa"] != (activa == "true"):
            continue
        resultado.append({"user_id": uid, **u})
    return jsonify({"total": len(resultado), "usuarios": resultado})


@app.route("/usuarios", methods=["POST"])
def crear_usuario():
    data = cuerpo()
    user_id = str(data.get("user_id", "")).strip()

    limpio, errores = validar_usuario(data)
    if not user_id.isdigit() or not 4 <= len(user_id) <= 12:
        errores.insert(0, "user_id debe ser numérico (entre 4 y 12 dígitos)")
    if errores:
        return jsonify({"error": "Datos inválidos", "detalles": errores}), 400

    with LOCK:
        if user_id in DB["usuarios"]:
            return error("Ya existe un usuario con ese user_id", 409)
        DB["usuarios"][user_id] = usuario_nuevo(
            limpio["nombre"], limpio["plan"], limpio["sucursal"],
            limpio.get("membresia_activa", True),
        )
        guardar()

    return jsonify({"mensaje": "Usuario creado", "user_id": user_id,
                    **DB["usuarios"][user_id]}), 201


@app.route("/usuarios/<user_id>", methods=["GET"])
def obtener_usuario(user_id):
    user = DB["usuarios"].get(user_id)
    if user is None:
        return error("Usuario no encontrado", 404)
    return jsonify({"user_id": user_id, **user})


@app.route("/usuarios/<user_id>", methods=["PUT"])
def actualizar_usuario(user_id):
    data = cuerpo()
    limpio, errores = validar_usuario(data, parcial=True)
    if not limpio:
        errores.append("No se envió ningún campo para actualizar")
    if errores:
        return jsonify({"error": "Datos inválidos", "detalles": errores}), 400

    with LOCK:
        user = DB["usuarios"].get(user_id)
        if user is None:
            return error("Usuario no encontrado", 404)
        user.update(limpio)
        guardar()

    return jsonify({"mensaje": "Usuario actualizado", "user_id": user_id, **user})


@app.route("/usuarios/<user_id>", methods=["DELETE"])
def eliminar_usuario(user_id):
    with LOCK:
        if user_id not in DB["usuarios"]:
            return error("Usuario no encontrado", 404)
        del DB["usuarios"][user_id]
        guardar()
    return jsonify({"mensaje": "Usuario eliminado", "user_id": user_id})


# ----------------------------------------------------------------------------
# Operaciones (las del servicio original, ahora con validación e historial)
# ----------------------------------------------------------------------------
@app.route("/membresia/<user_id>", methods=["GET"])
def verificar_membresia(user_id):
    user = DB["usuarios"].get(user_id)
    if user is None:
        return error("Usuario no encontrado", 404)
    return jsonify({
        "user_id": user_id,
        "nombre": user["nombre"],
        "membresia_activa": user["membresia_activa"],
        "plan": user["plan"],
        "sucursal": user["sucursal"],
    })


@app.route("/acceso", methods=["POST"])
def registrar_acceso():
    user_id = str(cuerpo().get("user_id", "")).strip()
    with LOCK:
        user, err = usuario_activo(user_id)
        if err:
            return err
        user["accesos"] += 1
        evento = registrar_evento(user_id, EVT_ACCESO)
        guardar()
    return jsonify({
        "mensaje": f"Acceso registrado correctamente ({EVT_ACCESO})",
        "user_id": user_id,
        "total_accesos": user["accesos"],
        "fecha": evento["fecha"],
    })


@app.route("/reservar_clase", methods=["POST"])
def reservar_clase():
    data = cuerpo()
    user_id = str(data.get("user_id", "")).strip()
    clase = str(data.get("clase", "")).strip().capitalize()

    if not clase:
        return error("Debes indicar el nombre de la clase", 400)
    if clase not in CLASES:
        return error(f"Clase no disponible. Opciones: {', '.join(CLASES)}", 400)

    with LOCK:
        user, err = usuario_activo(user_id)
        if err:
            return err
        if clase in user["clases_reservadas"]:
            return error(f"Ya tienes reservada la clase {clase}", 409)
        user["clases_reservadas"].append(clase)
        registrar_evento(user_id, EVT_RESERVA, clase)
        guardar()

    return jsonify({
        "mensaje": f"Clase reservada correctamente ({EVT_RESERVA})",
        "user_id": user_id,
        "clase": clase,
        "clases_reservadas": user["clases_reservadas"],
    }), 201


@app.route("/reservar_clase", methods=["DELETE"])
def cancelar_clase():
    data = cuerpo()
    user_id = str(data.get("user_id", "")).strip()
    clase = str(data.get("clase", "")).strip().capitalize()

    with LOCK:
        user = DB["usuarios"].get(user_id)
        if user is None:
            return error("Usuario no encontrado", 404)
        if clase not in user["clases_reservadas"]:
            return error("Esa clase no está reservada", 404)
        user["clases_reservadas"].remove(clase)
        registrar_evento(user_id, EVT_CANCELA, clase)
        guardar()

    return jsonify({
        "mensaje": f"Reserva cancelada ({EVT_CANCELA})",
        "user_id": user_id,
        "clase": clase,
        "clases_reservadas": user["clases_reservadas"],
    })


@app.route("/completar_rutina", methods=["POST"])
def completar_rutina():
    user_id = str(cuerpo().get("user_id", "")).strip()
    with LOCK:
        user, err = usuario_activo(user_id)
        if err:
            return err
        user["rutinas_completadas"] += 1
        registrar_evento(user_id, EVT_RUTINA)
        guardar()
    return jsonify({
        "mensaje": f"Rutina completada ({EVT_RUTINA})",
        "user_id": user_id,
        "total_rutinas": user["rutinas_completadas"],
    })


# ----------------------------------------------------------------------------
# Consultas: historial y estadísticas
# ----------------------------------------------------------------------------
@app.route("/historial", methods=["GET"])
def historial():
    user_id = request.args.get("user_id")
    tipo = request.args.get("tipo")
    try:
        limite = max(1, min(int(request.args.get("limite", 50)), 500))
    except ValueError:
        return error("limite debe ser un número", 400)

    eventos = [
        e for e in reversed(DB["historial"])
        if (not user_id or e["user_id"] == user_id)
        and (not tipo or e["tipo"] == tipo)
    ]
    return jsonify({"total": len(eventos), "eventos": eventos[:limite]})


@app.route("/estadisticas", methods=["GET"])
def estadisticas():
    usuarios = DB["usuarios"].values()
    clases = Counter(c for u in usuarios for c in u["clases_reservadas"])
    return jsonify({
        "total_usuarios": len(DB["usuarios"]),
        "membresias_activas": sum(u["membresia_activa"] for u in usuarios),
        "usuarios_por_plan": dict(Counter(u["plan"] for u in usuarios)),
        "total_accesos": sum(u["accesos"] for u in usuarios),
        "total_rutinas": sum(u["rutinas_completadas"] for u in usuarios),
        "total_reservas": sum(clases.values()),
        "clase_mas_reservada": clases.most_common(1)[0][0] if clases else None,
        "eventos_por_tipo": dict(Counter(e["tipo"] for e in DB["historial"])),
    })


# ----------------------------------------------------------------------------
# Manejo de errores en JSON
# ----------------------------------------------------------------------------
@app.errorhandler(404)
def no_encontrado(_):
    return error("Ruta no encontrada", 404)


@app.errorhandler(405)
def metodo_no_permitido(_):
    return error("Método no permitido para esta ruta", 405)


@app.errorhandler(500)
def error_interno(_):
    return error("Error interno del servidor", 500)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
