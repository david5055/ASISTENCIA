import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify
)

from dotenv import load_dotenv


# ==========================================================
# CARGAR CONFIGURACIÓN
# ==========================================================

load_dotenv()


# ==========================================================
# IMPORTAR UTILIDADES
# ==========================================================

from utils.data_loader import (
    cargar_personas,
    DataError
)


# ==========================================================
# IMPORTAR REGISTRO
# ==========================================================

from services.registro_service import (
    preparar_registro
)


# ==========================================================
# IMPORTAR ASISTENCIA
# ==========================================================

from services.asistencia_service import (
    preparar_asistencia,
    obtener_estado_asistencia,
    detener_asistencia
)


# ==========================================================
# CREAR APLICACIÓN
# ==========================================================

app = Flask(__name__)


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

app.config[
    "MAX_CONTENT_LENGTH"
] = 16 * 1024 * 1024


app.secret_key = os.getenv(
    "SECRET_KEY",
    "cambiar-esta-clave-en-produccion"
)


# ==========================================================
# PÁGINA PRINCIPAL
# ==========================================================

@app.get("/")
def inicio():

    return render_template(
        "index.html"
    )


# ==========================================================
# REGISTRO
# ==========================================================

@app.route(
    "/registro",
    methods=[
        "GET",
        "POST"
    ]
)
def registro():

    # ======================================================
    # MOSTRAR PÁGINA
    # ======================================================

    if request.method == "GET":

        return render_template(
            "registro.html"
        )


    # ======================================================
    # RECIBIR DATOS
    # ======================================================

    codigo = request.form.get(
        "codigo_integracion",
        ""
    ).strip()


    texto_json = request.form.get(
        "json_texto",
        ""
    ).strip()


    archivo = request.files.get(
        "archivo_datos"
    )


    # ======================================================
    # VALIDAR CÓDIGO
    # ======================================================

    if not codigo:

        return render_template(

            "registro.html",

            error=(
                "Debes ingresar el "
                "código de integración."
            )

        ), 400


    # ======================================================
    # LEER DATOS
    # ======================================================

    try:

        personas = cargar_personas(

            archivo=archivo,

            texto_json=texto_json

        )


        # ==================================================
        # PREPARAR REGISTRO
        # ==================================================

        resultado = preparar_registro(

            codigo_integracion=codigo,

            personas=personas

        )


        return render_template(

            "resultado.html",

            titulo="Registro preparado",

            resultado=resultado,

            volver="/registro"

        )


    except DataError as error:

        return render_template(

            "registro.html",

            error=str(error)

        ), 400


    except Exception as error:

        print(
            "ERROR EN REGISTRO:",
            error
        )


        return render_template(

            "registro.html",

            error=(
                "Ocurrió un error: "
                f"{error}"
            )

        ), 500


# ==========================================================
# ASISTENCIA
# ==========================================================

@app.route(
    "/asistencia",
    methods=[
        "GET",
        "POST"
    ]
)
def asistencia():

    # ======================================================
    # MOSTRAR PÁGINA
    # ======================================================

    if request.method == "GET":

        return render_template(
            "asistencia.html"
        )


    # ======================================================
    # RECIBIR DATOS DE LA WEB
    # ======================================================

    enlace = request.form.get(
        "enlace_actividad",
        ""
    ).strip()


    codigo = request.form.get(
        "codigo_integracion",
        ""
    ).strip()


    texto_json = request.form.get(
        "json_texto",
        ""
    ).strip()


    archivo = request.files.get(
        "archivo_datos"
    )


    # ======================================================
    # VALIDAR ENLACE
    # ======================================================

    if not enlace:

        return render_template(

            "asistencia.html",

            error=(
                "Debes ingresar el "
                "enlace de asistencia."
            )

        ), 400


    if not enlace.startswith(
        (
            "http://",
            "https://"
        )
    ):

        return render_template(

            "asistencia.html",

            error=(
                "El enlace de asistencia "
                "no es válido."
            )

        ), 400


    # ======================================================
    # VALIDAR CÓDIGO
    # ======================================================

    if not codigo:

        return render_template(

            "asistencia.html",

            error=(
                "Debes ingresar el "
                "código de integración."
            )

        ), 400


    # ======================================================
    # LEER JSON / CSV
    # ======================================================

    try:

        personas = cargar_personas(

            archivo=archivo,

            texto_json=texto_json

        )


        # ==================================================
        # INICIAR AUTOMATIZACIÓN
        # ==================================================

        resultado = preparar_asistencia(

            enlace_actividad=enlace,

            codigo_integracion=codigo,

            personas=personas

        )


        # ==================================================
        # SI YA EXISTE OTRO PROCESO
        # ==================================================

        if not resultado.get(
            "ok",
            False
        ):

            return render_template(

                "asistencia.html",

                error=resultado.get(

                    "mensaje",

                    "No se pudo iniciar la asistencia."

                )

            ), 400


        # ==================================================
        # REDIRECCIONAR A PROGRESO
        # ==================================================

        return redirect(

            url_for(
                "progreso_asistencia"
            )

        )


    except DataError as error:

        return render_template(

            "asistencia.html",

            error=str(error)

        ), 400


    except Exception as error:

        print()
        print(
            "======================================"
        )

        print(
            "ERROR INICIANDO ASISTENCIA"
        )

        print(
            "======================================"
        )

        print(
            error
        )


        return render_template(

            "asistencia.html",

            error=(
                "No se pudo iniciar "
                f"la asistencia: {error}"
            )

        ), 500


# ==========================================================
# PANTALLA DE PROGRESO DE ASISTENCIA
# ==========================================================

@app.get(
    "/asistencia/progreso"
)
def progreso_asistencia():

    return render_template(
        "progreso_asistencia.html"
    )


# ==========================================================
# API - ESTADO DE ASISTENCIA
# ==========================================================

@app.get(
    "/api/asistencia/estado"
)
def api_estado_asistencia():

    try:

        estado = obtener_estado_asistencia()

        return jsonify(
            estado
        )


    except Exception as error:

        print(
            "ERROR OBTENIENDO ESTADO:",
            error
        )


        return jsonify({

            "estado":
                "error",

            "actual":
                0,

            "total":
                0,

            "porcentaje":
                0,

            "nie":
                "",

            "enviadas":
                0,

            "ya_existentes":
                0,

            "no_encontrados":
                0,

            "sin_documento":
                0,

            "errores":
                1,

            "log": [

                "Error leyendo el estado de DAVIS.",

                str(error)

            ]

        }), 500


# ==========================================================
# API - DETENER ASISTENCIA
# ==========================================================

@app.post(
    "/api/asistencia/detener"
)
def api_detener_asistencia():

    try:

        detenido = detener_asistencia()


        if detenido:

            return jsonify({

                "ok":
                    True,

                "mensaje":
                    "Proceso detenido correctamente."

            })


        return jsonify({

            "ok":
                False,

            "mensaje":
                "No existe un proceso de asistencia ejecutándose."

        })


    except Exception as error:

        return jsonify({

            "ok":
                False,

            "mensaje":
                f"No se pudo detener el proceso: {error}"

        }), 500


# ==========================================================
# ERROR: ARCHIVO DEMASIADO GRANDE
# ==========================================================

@app.errorhandler(413)
def archivo_demasiado_grande(error):

    return (

        "El archivo supera el límite permitido de 16 MB.",

        413

    )


# ==========================================================
# INICIAR DAVIS
# ==========================================================

if __name__ == "__main__":

    print()
    print(
        "======================================"
    )

    print(
        "          SISTEMA DAVIS"
    )

    print(
        "======================================"
    )

    print()

    print(
        "Sistema iniciado."
    )

    print()

    print(
        "Abre en esta computadora:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print()

    print(
        "======================================"
    )


    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True,

        # IMPORTANTE:
        # evita que Flask cree otro proceso
        # y perdamos el estado de Playwright.
        use_reloader=False

    )