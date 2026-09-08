import base64
import hashlib
import hmac
import json
import os

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)


# ==========================================================
# BLUEPRINT
# ==========================================================

auth_bp = Blueprint(
    "auth",
    __name__
)


# ==========================================================
# RUTA DEL JSON
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

ARCHIVO_USUARIOS = os.path.join(
    BASE_DIR,
    "usuarios.json"
)


# ==========================================================
# LEER USUARIOS
# ==========================================================

def cargar_usuarios():

    if not os.path.exists(
        ARCHIVO_USUARIOS
    ):
        return []

    try:

        with open(
            ARCHIVO_USUARIOS,
            "r",
            encoding="utf-8"
        ) as archivo:

            datos = json.load(
                archivo
            )

        if not isinstance(
            datos,
            list
        ):
            return []

        return datos

    except Exception as error:

        print(
            "ERROR LEYENDO usuarios.json:",
            error
        )

        return []


# ==========================================================
# BUSCAR USUARIO
# ==========================================================

def buscar_usuario(
    nombre_usuario
):

    nombre_usuario = str(
        nombre_usuario
        or
        ""
    ).strip().lower()

    if not nombre_usuario:
        return None

    for usuario in cargar_usuarios():

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

        if actual == nombre_usuario:
            return usuario

    return None


# ==========================================================
# VERIFICAR HASH PBKDF2
# ==========================================================

def verificar_password(
    password,
    password_hash
):

    try:

        partes = str(
            password_hash
            or
            ""
        ).split("$")

        if len(partes) != 4:
            return False

        algoritmo = partes[0]

        if algoritmo != "pbkdf2_sha256":
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


# ==========================================================
# VERIFICAR CREDENCIALES
# ==========================================================

def verificar_credenciales(
    nombre_usuario,
    password
):

    usuario = buscar_usuario(
        nombre_usuario
    )

    if usuario is None:
        return None

    if not usuario.get(
        "activo",
        True
    ):
        return None

    password_hash = str(
        usuario.get(
            "password_hash",
            ""
        )
        or
        ""
    ).strip()

    if not password_hash:
        return None

    if not verificar_password(
        password,
        password_hash
    ):
        return None

    return usuario


# ==========================================================
# DESTINO SEGURO
# ==========================================================

def destino_seguro(
    destino
):

    destino = str(
        destino
        or
        ""
    ).strip()

    if (
        destino.startswith("/")
        and
        not destino.startswith("//")
    ):
        return destino

    return url_for(
        "inicio"
    )


# ==========================================================
# PROTEGER TODO DAVIS
# ==========================================================

@auth_bp.before_app_request
def exigir_login():

    endpoint = request.endpoint or ""

    if endpoint in (
        "auth.login",
        "static",
    ):
        return None

    if session.get(
        "usuario"
    ):
        return None

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({
            "ok": False,
            "estado": "no_autorizado",
            "mensaje": (
                "Tu sesión no está activa. "
                "Inicia sesión nuevamente."
            )
        }), 401

    return redirect(
        url_for(
            "auth.login",
            siguiente=request.full_path
            if request.query_string
            else request.path
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

    if session.get(
        "usuario"
    ):

        return redirect(
            url_for(
                "inicio"
            )
        )

    error = ""

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

            session.modified = True

            siguiente = request.form.get(
                "siguiente",
                ""
            )

            return redirect(
                destino_seguro(
                    siguiente
                )
            )

    siguiente = request.args.get(
        "siguiente",
        ""
    )

    return render_template(
        "login.html",
        error=error,
        siguiente=siguiente
    )


# ==========================================================
# CERRAR SESIÓN
# ==========================================================

@auth_bp.get(
    "/logout"
)
def logout():

    session.clear()

    return redirect(
        url_for(
            "auth.login"
        )
    )
