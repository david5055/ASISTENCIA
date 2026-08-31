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
# VARIABLES DE ENTORNO
# ==========================================================

load_dotenv()


# ==========================================================
# UTILIDADES
# ==========================================================

from utils.data_loader import (
    cargar_personas,
    DataError
)


# ==========================================================
# SERVICIO ASISTENCIA
# ==========================================================

from services.asistencia_service import (
    preparar_asistencia,
    obtener_estado_asistencia,
    detener_asistencia
)


# ==========================================================
# SERVICIO REGISTRO
# ==========================================================

from services.registro_service import (
    preparar_registro,
    obtener_estado_registro,
    obtener_revision_pendiente,
    enviar_correccion_registro,
    detener_registro
)


# ==========================================================
# FLASK
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
# ==========================================================
#                MÓDULO ASISTENCIA
# ==========================================================
# ==========================================================


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
    # MOSTRAR FORMULARIO
    # ======================================================

    if request.method == "GET":

        return render_template(
            "asistencia.html"
        )


    # ======================================================
    # RECIBIR DATOS
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
                "Debes ingresar el enlace "
                "de asistencia."
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
                "Debes ingresar el código "
                "de integración."
            )

        ), 400


    # ======================================================
    # CARGAR PERSONAS
    # ======================================================

    try:

        personas = cargar_personas(

            archivo=archivo,

            texto_json=texto_json

        )


        resultado = preparar_asistencia(

            enlace_actividad=enlace,

            codigo_integracion=codigo,

            personas=personas

        )


        # ==================================================
        # NO SE PUDO INICIAR
        # ==================================================

        if not resultado.get(
            "ok",
            False
        ):

            return render_template(

                "asistencia.html",

                error=resultado.get(

                    "mensaje",

                    "No se pudo iniciar "
                    "la asistencia."

                )

            ), 400


        # ==================================================
        # IR A PROGRESO
        # ==================================================

        return redirect(
            url_for(
                "progreso_asistencia"
            )
        )


    except DataError as error:

        return render_template(

            "asistencia.html",

            error=str(
                error
            )

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
# PROGRESO ASISTENCIA
# ==========================================================

@app.get(
    "/asistencia/progreso"
)
def progreso_asistencia():

    return render_template(
        "progreso_asistencia.html"
    )


# ==========================================================
# API ESTADO ASISTENCIA
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
            "ERROR OBTENIENDO ESTADO ASISTENCIA:",
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
# DETENER ASISTENCIA
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
                    "Proceso de asistencia detenido correctamente."

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
                (
                    "No se pudo detener "
                    f"el proceso: {error}"
                )

        }), 500


# ==========================================================
# ==========================================================
#                   MÓDULO REGISTRO
# ==========================================================
# ==========================================================


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
    # MOSTRAR FORMULARIO
    # ======================================================

    if request.method == "GET":

        return render_template(
            "registro.html"
        )


    # ======================================================
    # DATOS DEL FORMULARIO
    # ======================================================

    enlace = request.form.get(
        "enlace_registro",
        ""
    ).strip()


    # ======================================================
    # COMPATIBILIDAD CON FORMULARIO ANTERIOR
    #
    # Si todavía existe codigo_integracion,
    # lo recibimos para no romper el sistema.
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
    # VALIDAR URL SI EL USUARIO LA ESCRIBIÓ
    # ======================================================

    if enlace:

        if not enlace.startswith(
            (
                "http://",
                "https://"
            )
        ):

            return render_template(

                "registro.html",

                error=(
                    "El enlace del formulario "
                    "de registro no es válido."
                )

            ), 400


    # ======================================================
    # CARGAR PERSONAS
    # ======================================================

    try:

        personas = cargar_personas(

            archivo=archivo,

            texto_json=texto_json

        )


        # ==================================================
        # INICIAR REGISTRO
        # ==================================================

        resultado = preparar_registro(

            enlace_registro=enlace,

            codigo_integracion=codigo,

            personas=personas

        )


        # ==================================================
        # NO SE PUDO INICIAR
        # ==================================================

        if not resultado.get(
            "ok",
            False
        ):

            return render_template(

                "registro.html",

                error=resultado.get(

                    "mensaje",

                    "No se pudo iniciar "
                    "el registro."

                )

            ), 400


        # ==================================================
        # IR A PANTALLA DE PROGRESO
        # ==================================================

        return redirect(
            url_for(
                "progreso_registro"
            )
        )


    except DataError as error:

        return render_template(

            "registro.html",

            error=str(
                error
            )

        ), 400


    except Exception as error:

        print()
        print(
            "======================================"
        )
        print(
            "ERROR INICIANDO REGISTRO"
        )
        print(
            "======================================"
        )
        print(
            error
        )


        return render_template(

            "registro.html",

            error=(
                "No se pudo iniciar "
                f"el registro: {error}"
            )

        ), 500


# ==========================================================
# PANTALLA DE PROGRESO REGISTRO
# ==========================================================

@app.get(
    "/registro/progreso"
)
def progreso_registro():

    return render_template(
        "progreso_registro.html"
    )


# ==========================================================
# API ESTADO REGISTRO
# ==========================================================

@app.get(
    "/api/registro/estado"
)
def api_estado_registro():

    try:

        estado = obtener_estado_registro()


        return jsonify(
            estado
        )


    except Exception as error:

        print()
        print(
            "ERROR OBTENIENDO ESTADO REGISTRO:"
        )
        print(
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

            "documento":
                "",

            "creados":
                0,

            "ya_registrados":
                0,

            "revisiones":
                0,

            "errores":
                1,

            "requiere_revision":
                False,

            "motivo_revision":
                "",

            "campos_faltantes":
                [],

            "persona_revision":
                None,

            "log": [
                "Error leyendo el estado de registro.",
                str(error)
            ]

        }), 500


# ==========================================================
# API OBTENER REVISIÓN PENDIENTE
# ==========================================================

@app.get(
    "/api/registro/revision"
)
def api_revision_registro():

    try:

        revision = obtener_revision_pendiente()


        # ==================================================
        # NO HAY REVISIÓN
        # ==================================================

        if revision is None:

            return jsonify({

                "ok":
                    True,

                "requiere_revision":
                    False,

                "revision":
                    None

            })


        # ==================================================
        # HAY REVISIÓN
        # ==================================================

        return jsonify({

            "ok":
                True,

            "requiere_revision":
                True,

            "revision":
                revision

        })


    except Exception as error:

        return jsonify({

            "ok":
                False,

            "requiere_revision":
                False,

            "mensaje":
                str(error)

        }), 500


# ==========================================================
# API ENVIAR CORRECCIÓN
# ==========================================================

@app.post(
    "/api/registro/corregir"
)
def api_corregir_registro():

    try:

        # ==================================================
        # PRIMERO INTENTAR JSON
        # ==================================================

        datos = request.get_json(
            silent=True
        )


        # ==================================================
        # SI VIENE DESDE FORMULARIO HTML
        # ==================================================

        if datos is None:

            datos = request.form.to_dict()


        # ==================================================
        # VALIDAR
        # ==================================================

        if not datos:

            return jsonify({

                "ok":
                    False,

                "mensaje":
                    "No se recibieron datos para corregir."

            }), 400


        # ==================================================
        # ENVIAR AL SERVICE
        # ==================================================

        resultado = enviar_correccion_registro(
            datos
        )


        if resultado.get(
            "ok",
            False
        ):

            return jsonify(
                resultado
            )


        return jsonify(
            resultado
        ), 400


    except Exception as error:

        print()
        print(
            "ERROR ENVIANDO CORRECCIÓN:"
        )
        print(
            error
        )


        return jsonify({

            "ok":
                False,

            "mensaje":
                (
                    "No se pudo enviar "
                    f"la corrección: {error}"
                )

        }), 500


# ==========================================================
# DETENER REGISTRO
# ==========================================================

@app.post(
    "/api/registro/detener"
)
def api_detener_registro():

    try:

        detenido = detener_registro()


        if detenido:

            return jsonify({

                "ok":
                    True,

                "mensaje":
                    "Proceso de registro detenido correctamente."

            })


        return jsonify({

            "ok":
                False,

            "mensaje":
                "No existe un proceso de registro ejecutándose."

        })


    except Exception as error:

        return jsonify({

            "ok":
                False,

            "mensaje":
                (
                    "No se pudo detener "
                    f"el registro: {error}"
                )

        }), 500


# ==========================================================
# ERROR ARCHIVO DEMASIADO GRANDE
# ==========================================================

@app.errorhandler(
    413
)
def archivo_demasiado_grande(
    error
):

    return (
        "El archivo supera el límite permitido de 16 MB.",
        413
    )


# ==========================================================
# EJECUTAR LOCALMENTE
# ==========================================================

if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        "           SISTEMA DAVIS"
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

        use_reloader=False

    )