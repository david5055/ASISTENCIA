import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

auth_bp = Blueprint("auth", __name__)

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

TIEMPO_INACTIVIDAD_SEGUNDOS = 30 * 60
COOKIE_DISPOSITIVO = "davis_device_id"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_USUARIOS = os.path.join(BASE_DIR, "usuarios.json")
ARCHIVO_SESIONES = os.path.join(BASE_DIR, "sesiones_activas.json")

LOCK_USUARIOS = threading.RLock()
LOCK_SESIONES = threading.RLock()

# LOCAL:
# Cada vez que ejecutas python app.py se genera un ID nuevo.
#
# RAILWAY:
# Todos los procesos del mismo deployment comparten
# RAILWAY_DEPLOYMENT_ID. Al hacer un deployment nuevo,
# las sesiones anteriores dejan de ser válidas.

RAILWAY_DEPLOYMENT_ID = str(
    os.getenv("RAILWAY_DEPLOYMENT_ID", "") or ""
).strip()

if RAILWAY_DEPLOYMENT_ID:
    ID_ARRANQUE_DAVIS = "railway-" + RAILWAY_DEPLOYMENT_ID
else:
    ID_ARRANQUE_DAVIS = "local-" + secrets.token_hex(32)


# ==========================================================
# UTILIDADES JSON
# ==========================================================

def fecha_iso(timestamp=None):

    if timestamp is None:
        timestamp = time.time()

    return datetime.fromtimestamp(
        float(timestamp),
        tz=timezone.utc
    ).isoformat()


def guardar_json_atomico(ruta, datos):

    temporal = ruta + ".tmp"

    with open(
        temporal,
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            datos,
            archivo,
            ensure_ascii=False,
            indent=4
        )

    os.replace(
        temporal,
        ruta
    )


# ==========================================================
# USUARIOS
# ==========================================================

def cargar_usuarios():

    if not os.path.exists(
        ARCHIVO_USUARIOS
    ):
        return []

    try:

        with LOCK_USUARIOS:

            with open(
                ARCHIVO_USUARIOS,
                "r",
                encoding="utf-8"
            ) as archivo:

                datos = json.load(
                    archivo
                )

        if isinstance(
            datos,
            list
        ):
            return datos

        return []

    except Exception as error:

        print(
            "ERROR LEYENDO usuarios.json:",
            error
        )

        return []


def guardar_usuarios(
    usuarios
):

    with LOCK_USUARIOS:

        guardar_json_atomico(
            ARCHIVO_USUARIOS,
            usuarios
        )


# ==========================================================
# CONTRASEÑAS
# ==========================================================

def crear_password_hash(
    password,
    iteraciones=310000
):

    salt = secrets.token_bytes(
        16
    )

    hash_password = hashlib.pbkdf2_hmac(
        "sha256",
        str(
            password
            or
            ""
        ).encode(
            "utf-8"
        ),
        salt,
        iteraciones
    )

    return (
        "pbkdf2_sha256"
        f"${iteraciones}"
        f"${base64.b64encode(salt).decode('ascii')}"
        f"${base64.b64encode(hash_password).decode('ascii')}"
    )


def verificar_password_hash(
    password,
    password_hash
):

    try:

        partes = str(
            password_hash
            or
            ""
        ).split(
            "$"
        )

        if len(partes) != 4:
            return False

        if partes[0] != "pbkdf2_sha256":
            return False

        iteraciones = int(
            partes[1]
        )

        salt = base64.b64decode(
            partes[2]
        )

        hash_guardado = base64.b64decode(
            partes[3]
        )

        hash_calculado = hashlib.pbkdf2_hmac(
            "sha256",
            str(
                password
                or
                ""
            ).encode(
                "utf-8"
            ),
            salt,
            iteraciones
        )

        return hmac.compare_digest(
            hash_calculado,
            hash_guardado
        )

    except Exception:

        return False


def verificar_credenciales(
    nombre_usuario,
    password
):

    nombre_usuario = str(
        nombre_usuario
        or
        ""
    ).strip().lower()

    if not nombre_usuario:
        return None

    usuarios = cargar_usuarios()

    for usuario in usuarios:

        if not isinstance(
            usuario,
            dict
        ):
            continue

        actual = str(
            usuario.get(
                "usuario",
                ""
            )
            or
            ""
        ).strip().lower()

        if actual != nombre_usuario:
            continue

        # ==================================================
        # USUARIO INACTIVO
        # ==================================================

        if not usuario.get(
            "activo",
            True
        ):
            return None

        # ==================================================
        # CONTRASEÑA YA PROTEGIDA
        # ==================================================

        password_hash = str(
            usuario.get(
                "password_hash",
                ""
            )
            or
            ""
        ).strip()

        if password_hash:

            if verificar_password_hash(
                password,
                password_hash
            ):
                return usuario

            return None

        # ==================================================
        # CONTRASEÑA MANUAL
        # ==================================================

        password_plano = str(
            usuario.get(
                "password",
                ""
            )
            or
            ""
        )

        if not password_plano:
            return None

        if not hmac.compare_digest(
            str(
                password
            ),
            password_plano
        ):
            return None

        # ==================================================
        # CONVERTIR A HASH AUTOMÁTICAMENTE
        # ==================================================

        usuario[
            "password_hash"
        ] = crear_password_hash(
            password_plano
        )

        usuario.pop(
            "password",
            None
        )

        try:

            guardar_usuarios(
                usuarios
            )

            print(
                "✅ Contraseña protegida automáticamente para:",
                usuario.get(
                    "usuario",
                    ""
                )
            )

        except Exception as error:

            print(
                "⚠️ No se pudo actualizar usuarios.json:",
                error
            )

        return usuario

    return None


# ==========================================================
# SESIONES ACTIVAS
# ==========================================================

def leer_sesiones():

    if not os.path.exists(
        ARCHIVO_SESIONES
    ):
        return {}

    try:

        with open(
            ARCHIVO_SESIONES,
            "r",
            encoding="utf-8"
        ) as archivo:

            datos = json.load(
                archivo
            )

        if isinstance(
            datos,
            dict
        ):
            return datos

        return {}

    except Exception as error:

        print(
            "ERROR LEYENDO sesiones_activas.json:",
            error
        )

        return {}


def guardar_sesiones(
    sesiones
):

    guardar_json_atomico(
        ARCHIVO_SESIONES,
        sesiones
    )


# ==========================================================
# ELIMINAR SESIONES VENCIDAS
# ==========================================================

def limpiar_sesiones_vencidas(
    sesiones
):

    ahora = time.time()

    hubo_cambios = False

    for nombre_usuario in list(
        sesiones.keys()
    ):

        registro = sesiones.get(
            nombre_usuario
        )

        if not isinstance(
            registro,
            dict
        ):

            sesiones.pop(
                nombre_usuario,
                None
            )

            hubo_cambios = True

            continue

        id_arranque = str(
            registro.get(
                "id_arranque_davis",
                ""
            )
            or
            ""
        )

        try:

            ultima_actividad = float(
                registro.get(
                    "ultima_actividad_ts",
                    0
                )
                or
                0
            )

        except Exception:

            ultima_actividad = 0

        expirada = (
            ultima_actividad <= 0
            or
            (
                ahora
                -
                ultima_actividad
            )
            >=
            TIEMPO_INACTIVIDAD_SEGUNDOS
        )

        arranque_anterior = (
            id_arranque
            !=
            ID_ARRANQUE_DAVIS
        )

        if (
            expirada
            or
            arranque_anterior
        ):

            sesiones.pop(
                nombre_usuario,
                None
            )

            hubo_cambios = True

    return hubo_cambios


# ==========================================================
# IDENTIFICAR DISPOSITIVO
# ==========================================================

def obtener_dispositivo_actual():

    return str(
        request.cookies.get(
            COOKIE_DISPOSITIVO,
            ""
        )
        or
        ""
    ).strip()


# ==========================================================
# REGISTRAR DISPOSITIVO ACTIVO
# ==========================================================

def registrar_dispositivo_activo(
    usuario,
    dispositivo_id
):

    nombre_usuario = str(
        usuario.get(
            "usuario",
            ""
        )
        or
        ""
    ).strip().lower()

    dispositivo_id = str(
        dispositivo_id
        or
        ""
    ).strip()

    if not nombre_usuario:

        return {
            "ok": False,
            "mensaje": (
                "El usuario no es válido."
            )
        }

    if not dispositivo_id:

        return {
            "ok": False,
            "mensaje": (
                "No se pudo identificar este dispositivo. "
                "Recarga la página e intenta nuevamente."
            )
        }

    ahora = time.time()

    with LOCK_SESIONES:

        sesiones = leer_sesiones()

        limpiar_sesiones_vencidas(
            sesiones
        )

        existente = sesiones.get(
            nombre_usuario
        )

        # ==================================================
        # YA ESTÁ EN OTRO DISPOSITIVO
        # ==================================================

        if isinstance(
            existente,
            dict
        ):

            dispositivo_existente = str(
                existente.get(
                    "dispositivo_id",
                    ""
                )
                or
                ""
            ).strip()

            if (
                dispositivo_existente
                and
                dispositivo_existente
                !=
                dispositivo_id
            ):

                guardar_sesiones(
                    sesiones
                )

                return {
                    "ok": False,
                    "mensaje": (
                        "Esta cuenta ya está siendo utilizada "
                        "en otro dispositivo."
                    )
                }

            # ==================================================
            # MISMO DISPOSITIVO
            #
            # Mantener token para permitir varias pestañas.
            # ==================================================

            token_sesion = str(
                existente.get(
                    "token_sesion",
                    ""
                )
                or
                ""
            ).strip()

            if not token_sesion:

                token_sesion = secrets.token_urlsafe(
                    32
                )

        else:

            token_sesion = secrets.token_urlsafe(
                32
            )

        sesiones[
            nombre_usuario
        ] = {

            "usuario":
                str(
                    usuario.get(
                        "usuario",
                        nombre_usuario
                    )
                ),

            "nombre":
                str(
                    usuario.get(
                        "nombre",
                        usuario.get(
                            "usuario",
                            nombre_usuario
                        )
                    )
                ),

            "dispositivo_id":
                dispositivo_id,

            "token_sesion":
                token_sesion,

            "id_arranque_davis":
                ID_ARRANQUE_DAVIS,

            "ultima_actividad_ts":
                ahora,

            "ultima_actividad":
                fecha_iso(
                    ahora
                ),
        }

        guardar_sesiones(
            sesiones
        )

    return {
        "ok": True,
        "token_sesion": token_sesion
    }


# ==========================================================
# VERIFICAR SESIÓN
# ==========================================================

def sesion_valida():

    if not session.get(
        "autenticado"
    ):
        return False

    nombre_usuario = str(
        session.get(
            "usuario",
            ""
        )
        or
        ""
    ).strip().lower()

    dispositivo_sesion = str(
        session.get(
            "dispositivo_id",
            ""
        )
        or
        ""
    ).strip()

    token_sesion = str(
        session.get(
            "token_sesion",
            ""
        )
        or
        ""
    ).strip()

    id_arranque_sesion = str(
        session.get(
            "id_arranque_davis",
            ""
        )
        or
        ""
    ).strip()

    dispositivo_cookie = obtener_dispositivo_actual()

    if not all([
        nombre_usuario,
        dispositivo_sesion,
        token_sesion,
        id_arranque_sesion,
        dispositivo_cookie,
    ]):

        return False

    if (
        id_arranque_sesion
        !=
        ID_ARRANQUE_DAVIS
    ):

        return False

    if (
        dispositivo_sesion
        !=
        dispositivo_cookie
    ):

        return False

    with LOCK_SESIONES:

        sesiones = leer_sesiones()

        hubo_cambios = limpiar_sesiones_vencidas(
            sesiones
        )

        registro = sesiones.get(
            nombre_usuario
        )

        if hubo_cambios:

            guardar_sesiones(
                sesiones
            )

        if not isinstance(
            registro,
            dict
        ):

            return False

        mismo_dispositivo = (
            str(
                registro.get(
                    "dispositivo_id",
                    ""
                )
                or
                ""
            ).strip()
            ==
            dispositivo_sesion
        )

        mismo_token = (
            str(
                registro.get(
                    "token_sesion",
                    ""
                )
                or
                ""
            ).strip()
            ==
            token_sesion
        )

        mismo_arranque = (
            str(
                registro.get(
                    "id_arranque_davis",
                    ""
                )
                or
                ""
            ).strip()
            ==
            ID_ARRANQUE_DAVIS
        )

        return bool(
            mismo_dispositivo
            and
            mismo_token
            and
            mismo_arranque
        )


# ==========================================================
# ACTUALIZAR ACTIVIDAD REAL
# ==========================================================

def actualizar_actividad():

    nombre_usuario = str(
        session.get(
            "usuario",
            ""
        )
        or
        ""
    ).strip().lower()

    dispositivo_id = str(
        session.get(
            "dispositivo_id",
            ""
        )
        or
        ""
    ).strip()

    token_sesion = str(
        session.get(
            "token_sesion",
            ""
        )
        or
        ""
    ).strip()

    if not all([
        nombre_usuario,
        dispositivo_id,
        token_sesion,
    ]):

        return False

    ahora = time.time()

    with LOCK_SESIONES:

        sesiones = leer_sesiones()

        limpiar_sesiones_vencidas(
            sesiones
        )

        registro = sesiones.get(
            nombre_usuario
        )

        if not isinstance(
            registro,
            dict
        ):

            guardar_sesiones(
                sesiones
            )

            return False

        if (
            str(
                registro.get(
                    "dispositivo_id",
                    ""
                )
                or
                ""
            ).strip()
            !=
            dispositivo_id
        ):

            return False

        if (
            str(
                registro.get(
                    "token_sesion",
                    ""
                )
                or
                ""
            ).strip()
            !=
            token_sesion
        ):

            return False

        registro[
            "ultima_actividad_ts"
        ] = ahora

        registro[
            "ultima_actividad"
        ] = fecha_iso(
            ahora
        )

        sesiones[
            nombre_usuario
        ] = registro

        guardar_sesiones(
            sesiones
        )

    return True


# ==========================================================
# LIBERAR CUENTA
# ==========================================================

def liberar_sesion_actual():

    nombre_usuario = str(
        session.get(
            "usuario",
            ""
        )
        or
        ""
    ).strip().lower()

    dispositivo_id = str(
        session.get(
            "dispositivo_id",
            ""
        )
        or
        ""
    ).strip()

    token_sesion = str(
        session.get(
            "token_sesion",
            ""
        )
        or
        ""
    ).strip()

    if not nombre_usuario:
        return

    with LOCK_SESIONES:

        sesiones = leer_sesiones()

        registro = sesiones.get(
            nombre_usuario
        )

        if not isinstance(
            registro,
            dict
        ):
            return

        mismo_dispositivo = (
            str(
                registro.get(
                    "dispositivo_id",
                    ""
                )
                or
                ""
            ).strip()
            ==
            dispositivo_id
        )

        mismo_token = (
            str(
                registro.get(
                    "token_sesion",
                    ""
                )
                or
                ""
            ).strip()
            ==
            token_sesion
        )

        if (
            mismo_dispositivo
            and
            mismo_token
        ):

            sesiones.pop(
                nombre_usuario,
                None
            )

            guardar_sesiones(
                sesiones
            )


# ==========================================================
# EVITAR CACHE
# ==========================================================

@auth_bp.after_app_request
def evitar_cache_privado(
    response
):

    if not request.path.startswith(
        "/static/"
    ):

        response.headers[
            "Cache-Control"
        ] = (
            "no-store, no-cache, "
            "must-revalidate, max-age=0"
        )

        response.headers[
            "Pragma"
        ] = "no-cache"

        response.headers[
            "Expires"
        ] = "0"

    return response


# ==========================================================
# PROTEGER TODO DAVIS
# ==========================================================

@auth_bp.before_app_request
def exigir_login():

    endpoint = request.endpoint or ""

    # ======================================================
    # ESTÁTICOS
    # ======================================================

    if endpoint == "static":

        return None

    # ======================================================
    # LOGIN
    # ======================================================

    if endpoint == "auth.login":

        if (
            session.get(
                "autenticado"
            )
            and
            not sesion_valida()
        ):

            session.clear()

        return None

    # ======================================================
    # LOGOUT
    # ======================================================

    if endpoint == "auth.logout":

        return None

    # ======================================================
    # SESIÓN VÁLIDA
    # ======================================================

    if sesion_valida():

        return None

    # ======================================================
    # SESIÓN INVÁLIDA
    # ======================================================

    if session:

        session.clear()

    # ======================================================
    # API
    # ======================================================

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({

            "ok":
                False,

            "estado":
                "no_autorizado",

            "mensaje":
                (
                    "Tu sesión expiró o no está activa. "
                    "Inicia sesión nuevamente."
                )

        }), 401

    # ======================================================
    # PÁGINA NORMAL
    # ======================================================

    return redirect(

        url_for(
            "auth.login",
            motivo="sesion"
        )

    )


# ==========================================================
# LOGIN
# ==========================================================

@auth_bp.route(
    "/login",
    methods=[
        "GET",
        "POST"
    ]
)
def login():

    # ======================================================
    # YA ESTÁ AUTENTICADO
    # ======================================================

    if sesion_valida():

        return redirect(
            url_for(
                "programa"
            )
        )

    if session:

        session.clear()

    error = ""

    motivo = str(
        request.args.get(
            "motivo",
            ""
        )
        or
        ""
    ).strip().lower()

    if motivo == "inactividad":

        error = (
            "Tu sesión se cerró automáticamente "
            "por 30 minutos de inactividad."
        )

    elif motivo == "sesion":

        error = (
            "Debes iniciar sesión para entrar a DAVIS."
        )

    # ======================================================
    # PROCESAR LOGIN
    # ======================================================

    if request.method == "POST":

        nombre_usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        usuario = verificar_credenciales(
            nombre_usuario,
            password
        )

        if usuario is None:

            error = (
                "Usuario o contraseña incorrectos."
            )

        else:

            dispositivo_id = obtener_dispositivo_actual()

            resultado = registrar_dispositivo_activo(
                usuario,
                dispositivo_id
            )

            # ==================================================
            # CUENTA EN OTRO DISPOSITIVO
            # ==================================================

            if not resultado.get(
                "ok"
            ):

                error = resultado.get(
                    "mensaje",
                    "No se pudo iniciar sesión."
                )

            else:

                ahora_ms = int(
                    time.time()
                    *
                    1000
                )

                session.clear()

                session[
                    "usuario"
                ] = str(
                    usuario.get(
                        "usuario",
                        ""
                    )
                )

                session[
                    "nombre"
                ] = str(
                    usuario.get(
                        "nombre",
                        usuario.get(
                            "usuario",
                            ""
                        )
                    )
                )

                session[
                    "rol"
                ] = str(
                    usuario.get(
                        "rol",
                        "usuario"
                    )
                )

                session[
                    "autenticado"
                ] = True

                session[
                    "dispositivo_id"
                ] = dispositivo_id

                session[
                    "token_sesion"
                ] = str(
                    resultado.get(
                        "token_sesion",
                        ""
                    )
                )

                session[
                    "id_arranque_davis"
                ] = ID_ARRANQUE_DAVIS

                session[
                    "inicio_sesion_ms"
                ] = ahora_ms

                session.permanent = False
                session.modified = True

                return redirect(
                    url_for(
                        "programa"
                    )
                )

    return render_template(
        "login.html",
        error=error,
        siguiente=""
    )


# ==========================================================
# API ACTIVIDAD
# ==========================================================

@auth_bp.post(
    "/api/auth/actividad"
)
def actividad():

    if not sesion_valida():

        session.clear()

        return jsonify({

            "ok":
                False,

            "estado":
                "no_autorizado",

            "mensaje":
                "Tu sesión expiró."

        }), 401

    if not actualizar_actividad():

        session.clear()

        return jsonify({

            "ok":
                False,

            "estado":
                "no_autorizado",

            "mensaje":
                (
                    "No se pudo mantener activa "
                    "la sesión."
                )

        }), 401

    return jsonify({

        "ok":
            True,

        "tiempo_inactividad_segundos":
            TIEMPO_INACTIVIDAD_SEGUNDOS

    })


# ==========================================================
# CERRAR SESIÓN
# ==========================================================

@auth_bp.get(
    "/logout"
)
def logout():

    motivo = str(
        request.args.get(
            "motivo",
            ""
        )
        or
        ""
    ).strip().lower()

    liberar_sesion_actual()

    session.clear()

    if motivo == "inactividad":

        return redirect(

            url_for(
                "auth.login",
                motivo="inactividad"
            )

        )

    return redirect(
        url_for(
            "auth.login"
        )
    )

