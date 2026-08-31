import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    session
)

from dotenv import load_dotenv


# ==========================================================
# CARGAR VARIABLES DE ENTORNO
# ==========================================================

load_dotenv()


# ==========================================================
# SERVICIO DE ASISTENCIA
#
# Se mantiene funcionando como estaba.
# ==========================================================

from services.asistencia_service import (
    preparar_asistencia,
    obtener_estado_asistencia,
    detener_asistencia
)


# ==========================================================
# SERVICIO DE REGISTRO MULTIUSUARIO
# ==========================================================

from services.registro_service import (
    preparar_registro,
    obtener_estado_registro,
    obtener_revision_pendiente,
    enviar_correccion_registro,
    registrar_heartbeat,
    detener_registro
)


# ==========================================================
# CARGADOR DE DATOS
# ==========================================================

from utils.data_loader import (
    cargar_personas,
    DataError
)


# ==========================================================
# FLASK
# ==========================================================

app = Flask(__name__)


# ==========================================================
# SECRET KEY
#
# En Railway debes tener:
#
# SECRET_KEY=una_clave_larga_y_segura
# ==========================================================

app.secret_key = os.getenv(
    "SECRET_KEY",
    "davis-clave-desarrollo-cambiar-en-produccion"
)


# ==========================================================
# TAMAÑO MÁXIMO DE ARCHIVOS
#
# 16 MB
# ==========================================================

app.config[
    "MAX_CONTENT_LENGTH"
] = 16 * 1024 * 1024


# ==========================================================
# UTILIDADES
# ==========================================================

def guardar_job_registro_en_sesion(
    job_id
):

    """
    Guarda en la sesión del navegador los JOBS
    creados por ese usuario.

    Esto evita que las páginas de distintos usuarios
    se mezclen entre sí.
    """

    jobs = session.get(
        "registro_jobs",
        []
    )


    if not isinstance(
        jobs,
        list
    ):

        jobs = []


    if job_id not in jobs:

        jobs.append(
            job_id
        )


    # Conservamos máximo los últimos 10
    # JOBS pertenecientes a este navegador.

    session[
        "registro_jobs"
    ] = jobs[
        -10:
    ]


    session.modified = True


# ==========================================================
# VERIFICAR QUE EL JOB PERTENECE AL NAVEGADOR
# ==========================================================

def job_registro_pertenece_a_sesion(
    job_id
):

    jobs = session.get(
        "registro_jobs",
        []
    )


    if not isinstance(
        jobs,
        list
    ):

        return False


    return job_id in jobs


# ==========================================================
# RESPUESTA JOB NO AUTORIZADO
# ==========================================================

def respuesta_job_no_autorizado():

    return jsonify({

        "ok":
            False,

        "estado":
            "no_encontrado",

        "mensaje":
            (
                "Este proceso de registro no pertenece "
                "a esta sesión de DAVIS."
            )

    }), 403


# ==========================================================
# INICIO
# ==========================================================

@app.get("/")
def inicio():

    return render_template(
        "index.html"
    )


# ==========================================================
# ==========================================================
#
#                MÓDULO ASISTENCIA
#
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

    try:

        codigo_integracion = request.form.get(
            "codigo_integracion",
            ""
        ).strip()


        archivo = request.files.get(
            "archivo_datos"
        )


        texto_json = request.form.get(
            "json_texto",
            ""
        )


        # ==================================================
        # CÓDIGO
        # ==================================================

        if not codigo_integracion:

            mensaje = (
                "Debes ingresar el código de integración."
            )


            return render_template(

                "asistencia.html",

                error=mensaje,

                mensaje_error=mensaje

            )


        # ==================================================
        # CARGAR PERSONAS
        # ==================================================

        personas = cargar_personas(

            archivo=archivo,

            texto_json=texto_json

        )


        # ==================================================
        # INICIAR ASISTENCIA
        # ==================================================

        resultado = preparar_asistencia(

            codigo_integracion,

            personas

        )


        # ==================================================
        # SI EL SERVICIO RETORNA DICCIONARIO
        # ==================================================

        if isinstance(
            resultado,
            dict
        ):

            if not resultado.get(
                "ok",
                True
            ):

                mensaje = resultado.get(

                    "mensaje",

                    "No se pudo iniciar la asistencia."

                )


                return render_template(

                    "asistencia.html",

                    error=mensaje,

                    mensaje_error=mensaje

                )


        # ==================================================
        # PROGRESO
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
            ),

            mensaje_error=str(
                error
            )

        )


    except Exception as error:

        print(
            "ERROR INICIANDO ASISTENCIA:",
            error
        )


        mensaje = (
            "No se pudo iniciar el proceso de asistencia. "
            f"{error}"
        )


        return render_template(

            "asistencia.html",

            error=mensaje,

            mensaje_error=mensaje

        )


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
def api_asistencia_estado():

    try:

        estado = obtener_estado_asistencia()


        return jsonify(
            estado
        )


    except Exception as error:

        print(
            "ERROR ESTADO ASISTENCIA:",
            error
        )


        return jsonify({

            "estado":
                "error",

            "mensaje":
                str(
                    error
                ),

            "actual":
                0,

            "total":
                0,

            "porcentaje":
                0,

            "enviadas":
                0,

            "ya_existentes":
                0,

            "no_encontrados":
                0,

            "errores":
                1,

            "log":
                []

        }), 500


# ==========================================================
# DETENER ASISTENCIA
# ==========================================================

@app.post(
    "/api/asistencia/detener"
)
def api_asistencia_detener():

    try:

        resultado = detener_asistencia()


        return jsonify({

            "ok":
                bool(
                    resultado
                ),

            "mensaje":
                (
                    "Proceso de asistencia detenido."
                    if resultado
                    else
                    "No existe un proceso activo."
                )

        })


    except Exception as error:

        return jsonify({

            "ok":
                False,

            "mensaje":
                str(
                    error
                )

        }), 500


# ==========================================================
# ==========================================================
#
#               MÓDULO REGISTRO
#
#               MULTIUSUARIO
#
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
    # MOSTRAR PÁGINA
    # ======================================================

    if request.method == "GET":

        return render_template(
            "registro.html"
        )


    # ======================================================
    # RECIBIR REGISTROS
    # ======================================================

    try:

        # ==================================================
        # URL DEL FORMULARIO
        #
        # Puede venir:
        #
        # 1. Escrita en la página
        # 2. Desde REGISTRO_URL en Railway
        # ==================================================

        enlace_registro = request.form.get(
            "enlace_registro",
            ""
        ).strip()


        # ==================================================
        # COMPATIBILIDAD CON VERSIONES ANTERIORES
        # ==================================================

        codigo_integracion = request.form.get(
            "codigo_integracion",
            ""
        ).strip()


        # ==================================================
        # ARCHIVO
        # ==================================================

        archivo = request.files.get(
            "archivo_datos"
        )


        # ==================================================
        # JSON PEGADO
        # ==================================================

        texto_json = request.form.get(
            "json_texto",
            ""
        )


        # ==================================================
        # VALIDAR URL SI EL USUARIO LA ESCRIBIÓ
        # ==================================================

        if enlace_registro:

            if not enlace_registro.startswith(
                (
                    "http://",
                    "https://"
                )
            ):

                mensaje = (
                    "La URL del formulario de registro "
                    "no es válida."
                )


                return render_template(

                    "registro.html",

                    error=mensaje,

                    mensaje_error=mensaje

                )


        # ==================================================
        # LEER JSON / CSV
        # ==================================================

        personas = cargar_personas(

            archivo=archivo,

            texto_json=texto_json

        )


        # ==================================================
        # PREPARAR NUEVO JOB
        # ==================================================

        resultado = preparar_registro(

            enlace_registro=
                enlace_registro,

            codigo_integracion=
                codigo_integracion,

            personas=
                personas

        )


        # ==================================================
        # LÍMITE DE 5 TRABAJOS
        # ==================================================

        if not resultado.get(
            "ok",
            False
        ):

            mensaje = resultado.get(

                "mensaje",

                "No se pudo iniciar el registro."

            )


            return render_template(

                "registro.html",

                error=mensaje,

                mensaje_error=mensaje,

                jobs_activos=
                    resultado.get(
                        "jobs_activos",
                        0
                    ),

                max_jobs=
                    resultado.get(
                        "max_jobs",
                        5
                    )

            )


        # ==================================================
        # JOB ÚNICO DE ESTE USUARIO
        # ==================================================

        job_id = resultado.get(
            "job_id",
            ""
        )


        if not job_id:

            raise RuntimeError(
                "DAVIS no generó el identificador del proceso."
            )


        # ==================================================
        # GUARDAR JOB EN LA SESIÓN DE ESTE NAVEGADOR
        # ==================================================

        guardar_job_registro_en_sesion(
            job_id
        )


        # ==================================================
        # REDIRECCIONAR A SU PROPIO PROGRESO
        # ==================================================

        return redirect(

            url_for(

                "progreso_registro",

                job_id=job_id

            )

        )


    # ======================================================
    # ERROR DE DATOS
    # ======================================================

    except DataError as error:

        return render_template(

            "registro.html",

            error=str(
                error
            ),

            mensaje_error=str(
                error
            )

        )


    # ======================================================
    # ERROR GENERAL
    # ======================================================

    except Exception as error:

        print(
            "ERROR INICIANDO REGISTRO:",
            error
        )


        mensaje = (

            "No se pudo iniciar el proceso de registro. "

            +

            str(
                error
            )

        )


        return render_template(

            "registro.html",

            error=mensaje,

            mensaje_error=mensaje

        )


# ==========================================================
# PROGRESO INDIVIDUAL
#
# Ejemplo:
#
# /registro/progreso/a57d83....
# ==========================================================

@app.get(
    "/registro/progreso/<job_id>"
)
def progreso_registro(
    job_id
):

    # ======================================================
    # SEGURIDAD:
    # ESTE JOB DEBE PERTENECER A ESTE NAVEGADOR
    # ======================================================

    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return render_template(

            "resultado.html",

            titulo=
                "Proceso no disponible",

            mensaje=(
                "Este proceso de registro no pertenece "
                "a esta sesión de DAVIS."
            )

        ), 403


    return render_template(

        "progreso_registro.html",

        job_id=job_id

    )


# ==========================================================
# COMPATIBILIDAD CON URL ANTERIOR
#
# /registro/progreso?job_id=ABC
# ==========================================================

@app.get(
    "/registro/progreso"
)
def progreso_registro_compatibilidad():

    job_id = request.args.get(
        "job_id",
        ""
    ).strip()


    if not job_id:

        return redirect(
            url_for(
                "registro"
            )
        )


    return redirect(

        url_for(

            "progreso_registro",

            job_id=job_id

        )

    )


# ==========================================================
# API ESTADO DEL JOB
#
# Cada usuario consulta solamente SU JOB.
#
# /api/registro/<job_id>/estado
# ==========================================================

@app.get(
    "/api/registro/<job_id>/estado"
)
def api_registro_estado(
    job_id
):

    # ======================================================
    # VERIFICAR PROPIETARIO
    # ======================================================

    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

        estado = obtener_estado_registro(
            job_id
        )


        return jsonify(
            estado
        )


    except Exception as error:

        print(
            "ERROR ESTADO REGISTRO:",
            error
        )


        return jsonify({

            "estado":
                "error",

            "job_id":
                job_id,

            "mensaje":
                str(
                    error
                ),

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

            "log":
                []

        }), 500


# ==========================================================
# API REVISIÓN PENDIENTE
#
# /api/registro/<job_id>/revision
# ==========================================================

@app.get(
    "/api/registro/<job_id>/revision"
)
def api_registro_revision(
    job_id
):

    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

        revision = obtener_revision_pendiente(
            job_id
        )


        if revision is None:

            return jsonify({

                "ok":
                    True,

                "requiere_revision":
                    False,

                "job_id":
                    job_id

            })


        return jsonify({

            "ok":
                True,

            "requiere_revision":
                True,

            "job_id":
                job_id,

            **revision

        })


    except Exception as error:

        return jsonify({

            "ok":
                False,

            "job_id":
                job_id,

            "mensaje":
                str(
                    error
                )

        }), 500


# ==========================================================
# API ENVIAR CORRECCIÓN
#
# /api/registro/<job_id>/corregir
# ==========================================================

@app.post(
    "/api/registro/<job_id>/corregir"
)
def api_registro_corregir(
    job_id
):

    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

        # ==================================================
        # JSON
        # ==================================================

        datos = request.get_json(
            silent=True
        )


        # ==================================================
        # COMPATIBILIDAD CON FORMULARIO NORMAL
        # ==================================================

        if datos is None:

            datos = request.form.to_dict()


        if not isinstance(
            datos,
            dict
        ):

            return jsonify({

                "ok":
                    False,

                "mensaje":
                    "No se recibieron datos de corrección."

            }), 400


        # ==================================================
        # ENVIAR A ESTE JOB ESPECÍFICO
        # ==================================================

        resultado = enviar_correccion_registro(

            datos,

            job_id=job_id

        )


        codigo_http = (

            200

            if resultado.get(
                "ok"
            )

            else

            400

        )


        return jsonify(
            resultado
        ), codigo_http


    except Exception as error:

        print(
            "ERROR CORRECCIÓN REGISTRO:",
            error
        )


        return jsonify({

            "ok":
                False,

            "mensaje":
                str(
                    error
                )

        }), 500


# ==========================================================
# HEARTBEAT
#
# La página enviará una señal aproximadamente
# cada 15 segundos.
#
# Mientras llegan señales:
#
# DAVIS sabe que el usuario sigue conectado.
#
# Si dejan de llegar durante 180 segundos:
#
# registro_service.py mata Playwright y Chromium.
# ==========================================================

@app.post(
    "/api/registro/<job_id>/heartbeat"
)
def api_registro_heartbeat(
    job_id
):

    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

        resultado = registrar_heartbeat(
            job_id
        )


        codigo_http = (

            200

            if resultado.get(
                "ok"
            )

            else

            409

        )


        return jsonify(
            resultado
        ), codigo_http


    except Exception as error:

        return jsonify({

            "ok":
                False,

            "job_id":
                job_id,

            "mensaje":
                str(
                    error
                )

        }), 500


# ==========================================================
# DETENER JOB MANUALMENTE
#
# Solamente detiene el trabajo del usuario.
#
# NO toca los trabajos de los otros cuatro usuarios.
# ==========================================================

@app.post(
    "/api/registro/<job_id>/detener"
)
def api_registro_detener(
    job_id
):

    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

        detenido = detener_registro(
            job_id
        )


        if detenido:

            return jsonify({

                "ok":
                    True,

                "job_id":
                    job_id,

                "estado":
                    "detenido",

                "mensaje":
                    "Proceso detenido correctamente."

            })


        return jsonify({

            "ok":
                False,

            "job_id":
                job_id,

            "mensaje":
                (
                    "El proceso ya terminó "
                    "o no se encuentra activo."
                )

        }), 409


    except Exception as error:

        print(
            "ERROR DETENIENDO REGISTRO:",
            error
        )


        return jsonify({

            "ok":
                False,

            "job_id":
                job_id,

            "mensaje":
                str(
                    error
                )

        }), 500


# ==========================================================
# RUTAS ANTERIORES DE REGISTRO
#
# Las mantenemos temporalmente para que DAVIS
# no falle durante la migración.
#
# Cuando terminemos progreso_registro.html,
# utilizaremos solamente las rutas por job_id.
# ==========================================================


# ==========================================================
# ESTADO ANTIGUO
# ==========================================================

@app.get(
    "/api/registro/estado"
)
def api_registro_estado_compatibilidad():

    job_id = request.args.get(
        "job_id",
        ""
    ).strip()


    # ======================================================
    # SI NO VIENE JOB EN LA URL
    # INTENTAR OBTENER EL ÚLTIMO DE ESTA SESIÓN
    # ======================================================

    if not job_id:

        jobs = session.get(
            "registro_jobs",
            []
        )


        if isinstance(
            jobs,
            list
        ) and jobs:

            job_id = jobs[
                -1
            ]


    if not job_id:

        return jsonify({

            "estado":
                "no_encontrado",

            "mensaje":
                "No se indicó job_id."

        }), 400


    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

        return jsonify(

            obtener_estado_registro(
                job_id
            )

        )


    except Exception as error:

        return jsonify({

            "estado":
                "error",

            "mensaje":
                str(
                    error
                )

        }), 500


# ==========================================================
# REVISIÓN ANTIGUA
# ==========================================================

@app.get(
    "/api/registro/revision"
)
def api_registro_revision_compatibilidad():

    job_id = request.args.get(
        "job_id",
        ""
    ).strip()


    if not job_id:

        jobs = session.get(
            "registro_jobs",
            []
        )


        if isinstance(
            jobs,
            list
        ) and jobs:

            job_id = jobs[
                -1
            ]


    if not job_id:

        return jsonify({

            "ok":
                False,

            "mensaje":
                "No se indicó job_id."

        }), 400


    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    revision = obtener_revision_pendiente(
        job_id
    )


    return jsonify({

        "ok":
            True,

        "requiere_revision":
            revision is not None,

        "job_id":
            job_id,

        "revision":
            revision

    })


# ==========================================================
# CORREGIR ANTIGUO
# ==========================================================

@app.post(
    "/api/registro/corregir"
)
def api_registro_corregir_compatibilidad():

    job_id = request.args.get(
        "job_id",
        ""
    ).strip()


    if not job_id:

        jobs = session.get(
            "registro_jobs",
            []
        )


        if isinstance(
            jobs,
            list
        ) and jobs:

            job_id = jobs[
                -1
            ]


    if not job_id:

        return jsonify({

            "ok":
                False,

            "mensaje":
                "No se indicó job_id."

        }), 400


    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    datos = request.get_json(
        silent=True
    )


    if datos is None:

        datos = request.form.to_dict()


    resultado = enviar_correccion_registro(

        datos,

        job_id=job_id

    )


    return jsonify(
        resultado
    )


# ==========================================================
# DETENER ANTIGUO
# ==========================================================

@app.post(
    "/api/registro/detener"
)
def api_registro_detener_compatibilidad():

    job_id = request.args.get(
        "job_id",
        ""
    ).strip()


    if not job_id:

        jobs = session.get(
            "registro_jobs",
            []
        )


        if isinstance(
            jobs,
            list
        ) and jobs:

            job_id = jobs[
                -1
            ]


    if not job_id:

        return jsonify({

            "ok":
                False,

            "mensaje":
                "No se indicó job_id."

        }), 400


    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    detenido = detener_registro(
        job_id
    )


    return jsonify({

        "ok":
            bool(
                detenido
            ),

        "job_id":
            job_id,

        "mensaje":
            (
                "Proceso detenido."
                if detenido
                else
                "El proceso ya terminó."
            )

    })


# ==========================================================
# ERROR: ARCHIVO DEMASIADO GRANDE
# ==========================================================

@app.errorhandler(
    413
)
def archivo_demasiado_grande(
    error
):

    return render_template(

        "resultado.html",

        titulo=
            "Archivo demasiado grande",

        mensaje=(
            "El archivo supera el tamaño máximo "
            "permitido por DAVIS."
        )

    ), 413


# ==========================================================
# ERROR 404
# ==========================================================

@app.errorhandler(
    404
)
def pagina_no_encontrada(
    error
):

    return render_template(

        "resultado.html",

        titulo=
            "Página no encontrada",

        mensaje=
            "La página solicitada no existe."

    ), 404


# ==========================================================
# EJECUCIÓN LOCAL
#
# Railway usa Gunicorn y NO entra aquí.
# ==========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True,

        use_reloader=False

    )