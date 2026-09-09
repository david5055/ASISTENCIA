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
    preparar_registro_adn,
    obtener_estado_registro,
    obtener_revision_pendiente,
    enviar_correccion_registro,
    saltar_persona_registro,
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
# CREAR FLASK
# ==========================================================

app = Flask(__name__)


# ==========================================================
# SECRET KEY
#
# EN RAILWAY:
#
# SECRET_KEY=una_clave_larga_y_segura
# ==========================================================

app.secret_key = os.getenv(
    "SECRET_KEY",
    "davis-desarrollo-cambiar-en-produccion"
)


# ==========================================================
# ARCHIVOS MÁXIMO 16 MB
# ==========================================================

app.config[
    "MAX_CONTENT_LENGTH"
] = 16 * 1024 * 1024


# ==========================================================
# CONFIGURACIÓN DE SESIONES
# ==========================================================

app.config[
    "SESSION_COOKIE_HTTPONLY"
] = True


app.config[
    "SESSION_COOKIE_SAMESITE"
] = "Lax"


# ==========================================================
# LOCAL:
#
# SESSION_COOKIE_SECURE=false
#
# RAILWAY:
#
# SESSION_COOKIE_SECURE=true
# ==========================================================

app.config[
    "SESSION_COOKIE_SECURE"
] = (
    os.getenv(
        "SESSION_COOKIE_SECURE",
        "false"
    ).lower()
    ==
    "true"
)


# ==========================================================
# ==========================================================
#
#                 UTILIDADES REGISTRO
#
# ==========================================================
# ==========================================================


# ==========================================================
# GUARDAR JOB EN SESIÓN
# ==========================================================

def guardar_job_registro_en_sesion(
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

        jobs = []


    if job_id not in jobs:

        jobs.append(
            job_id
        )


    # ======================================================
    # CONSERVAR ÚLTIMOS 10 JOBS
    # ======================================================

    session[
        "registro_jobs"
    ] = jobs[
        -10:
    ]


    session[
        "ultimo_registro_job"
    ] = job_id


    session.modified = True


# ==========================================================
# OBTENER ÚLTIMO JOB DE ESTA SESIÓN
# ==========================================================

def obtener_ultimo_job_sesion():

    job_id = session.get(
        "ultimo_registro_job",
        ""
    )


    if job_id:

        return str(
            job_id
        ).strip()


    jobs = session.get(
        "registro_jobs",
        []
    )


    if (
        isinstance(
            jobs,
            list
        )
        and
        jobs
    ):

        return str(
            jobs[
                -1
            ]
        ).strip()


    return ""


# ==========================================================
# VERIFICAR QUE JOB PERTENECE A ESTA SESIÓN
# ==========================================================

def job_registro_pertenece_a_sesion(
    job_id
):

    if not job_id:

        return False


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
# ==========================================================
#
#               UTILIDADES ASISTENCIA
#
# ==========================================================
# ==========================================================


def guardar_job_asistencia_en_sesion(job_id):

    job_id = str(
        job_id
        or ""
    ).strip()

    if not job_id:
        return

    jobs = session.get(
        "asistencia_jobs",
        []
    )

    if not isinstance(jobs, list):
        jobs = []

    if job_id not in jobs:
        jobs.append(job_id)

    session[
        "asistencia_jobs"
    ] = jobs[-10:]

    session[
        "ultimo_asistencia_job"
    ] = job_id

    session.modified = True


def obtener_ultimo_job_asistencia_sesion():

    job_id = session.get(
        "ultimo_asistencia_job",
        ""
    )

    if job_id:
        return str(
            job_id
        ).strip()

    jobs = session.get(
        "asistencia_jobs",
        []
    )

    if isinstance(jobs, list) and jobs:
        return str(
            jobs[-1]
        ).strip()

    return ""


# ==========================================================
# ==========================================================
#
#                       INICIO
#
# ==========================================================
# ==========================================================


@app.get("/")
def inicio():

    return render_template(
        "programa.html"
    )


# ==========================================================
# SELECCIÓN DE PROGRAMA
# ==========================================================

@app.get(
    "/programa"
)
def programa():

    return render_template(
        "programa.html"
    )


# ==========================================================
# INICIO MAE
# ==========================================================

@app.get(
    "/mae"
)
def mae():

    return render_template(
        "index.html"
    )


# ==========================================================
# INICIO ADN
# ==========================================================

@app.get(
    "/adn"
)
def adn():

    return render_template(
        "ADNVIU.html"
    )


# ==========================================================
# GENERADOR DE PROMPT IA - MAE
# ==========================================================

@app.get(
    "/generar-prompt"
)
def generar_prompt():

    return render_template(
        "generar_prompt.html"
    )


# ==========================================================
# GENERADOR DE PROMPT IA - ADN
# ==========================================================

@app.get(
    "/generar-prompt-adn"
)
def generar_prompt_adn():

    return render_template(
        "generar_prompt_adn.html"
    )


# ==========================================================
# ==========================================================
#
#                     ASISTENCIA
#
# ==========================================================
# ==========================================================


# ==========================================================
# FORMULARIO ASISTENCIA
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
    # PROCESAR FORMULARIO
    # ======================================================

    try:

        enlace_asistencia = request.form.get(
            "enlace_asistencia",
            ""
        ).strip()

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

        if not enlace_asistencia:

            mensaje = (
                "Debes ingresar el enlace de asistencia."
            )

            return render_template(
                "asistencia.html",
                error=mensaje,
                mensaje_error=mensaje
            )

        if not enlace_asistencia.startswith(
            (
                "http://",
                "https://"
            )
        ):

            mensaje = (
                "El enlace de asistencia no es válido."
            )

            return render_template(
                "asistencia.html",
                error=mensaje,
                mensaje_error=mensaje
            )

        if not codigo_integracion:

            mensaje = (
                "Debes ingresar el código de integración."
            )

            return render_template(
                "asistencia.html",
                error=mensaje,
                mensaje_error=mensaje
            )

        personas = cargar_personas(
            archivo=archivo,
            texto_json=texto_json
        )

        resultado = preparar_asistencia(
            enlace_asistencia,
            codigo_integracion,
            personas
        )

        if isinstance(resultado, dict):

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

            job_id = str(
                resultado.get(
                    "job_id",
                    ""
                )
            ).strip()

            if job_id:
                guardar_job_asistencia_en_sesion(
                    job_id
                )

        return redirect(
            url_for(
                "progreso_asistencia"
            )
        )

    except DataError as error:

        return render_template(
            "asistencia.html",
            error=str(error),
            mensaje_error=str(error)
        )

    except Exception as error:

        print(
            "ERROR INICIANDO ASISTENCIA:",
            error
        )

        mensaje = (
            "No se pudo iniciar el proceso de asistencia. "
            +
            str(error)
        )

        return render_template(
            "asistencia.html",
            error=mensaje,
            mensaje_error=mensaje
        )


# ==========================================================
# PROGRESO ASISTENCIA
#
# La URL se conserva exactamente igual.
# Cada dispositivo usa el job guardado en SU sesión.
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

        job_id = obtener_ultimo_job_asistencia_sesion()

        if not job_id:
            return jsonify({
                "estado": "listo",
                "actual": 0,
                "total": 0,
                "porcentaje": 0,
                "documento": "",
                "nie": "",
                "enviadas": 0,
                "ya_existentes": 0,
                "no_encontrados": 0,
                "omitidos": 0,
                "errores": 0,
                "log": []
            })

        estado = obtener_estado_asistencia(
            job_id
        )

        return jsonify(
            estado
        )

    except Exception as error:

        print(
            "ERROR ESTADO ASISTENCIA:",
            error
        )

        return jsonify({
            "estado": "error",
            "mensaje": str(error),
            "actual": 0,
            "total": 0,
            "porcentaje": 0,
            "documento": "",
            "nie": "",
            "enviadas": 0,
            "ya_existentes": 0,
            "no_encontrados": 0,
            "omitidos": 0,
            "errores": 1,
            "log": []
        }), 500


# ==========================================================
# DETENER ASISTENCIA
# ==========================================================

@app.post(
    "/api/asistencia/detener"
)
def api_asistencia_detener():

    try:

        job_id = obtener_ultimo_job_asistencia_sesion()

        if not job_id:
            return jsonify({
                "ok": False,
                "mensaje": (
                    "No existe un proceso de asistencia "
                    "activo en este dispositivo."
                )
            })

        resultado = detener_asistencia(
            job_id
        )

        return jsonify({
            "ok": bool(resultado),
            "mensaje": (
                "Proceso de asistencia detenido."
                if resultado
                else
                "No existe un proceso de asistencia activo."
            )
        })

    except Exception as error:

        print(
            "ERROR DETENIENDO ASISTENCIA:",
            error
        )

        return jsonify({
            "ok": False,
            "mensaje": str(error)
        }), 500


# ==========================================================
# ==========================================================
#
#                  REGISTRO MULTIUSUARIO
#
# ==========================================================
# ==========================================================


# ==========================================================
# FORMULARIO REGISTRO
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
    # GET
    # ======================================================

    if request.method == "GET":

        return render_template(
            "registro.html"
        )


    # ======================================================
    # POST
    # ======================================================

    try:

        # ==================================================
        # ENLACE REGISTRO
        # ==================================================

        enlace_registro = request.form.get(
            "enlace_registro",
            ""
        ).strip()


        # ==================================================
        # COMPATIBILIDAD
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
        # CARGAR PERSONAS
        # ==================================================

        personas = cargar_personas(

            archivo=archivo,

            texto_json=texto_json

        )


        # ==================================================
        # PREPARAR JOB
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
        # VALIDAR RESPUESTA
        # ==================================================

        if not isinstance(
            resultado,
            dict
        ):

            raise RuntimeError(
                "El servicio de registro devolvió "
                "una respuesta no válida."
            )


        # ==================================================
        # MÁXIMO DE PROCESOS ALCANZADO
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
        # JOB ID
        # ==================================================

        job_id = str(

            resultado.get(
                "job_id",
                ""
            )

        ).strip()


        if not job_id:

            raise RuntimeError(

                "DAVIS no generó el identificador "
                "del proceso."

            )


        # ==================================================
        # GUARDAR JOB EN SESIÓN
        # ==================================================

        guardar_job_registro_en_sesion(
            job_id
        )


        # ==================================================
        # IR AL PROGRESO DEL JOB ESPECÍFICO
        # ==================================================

        return redirect(

            url_for(

                "progreso_registro",

                job_id=job_id

            )

        )


    # ======================================================
    # ERROR DATOS
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
# FORMULARIO REGISTRO ADN
# ==========================================================

@app.route(
    "/registro-adn",
    methods=[
        "GET",
        "POST"
    ]
)
def registro_adn():

    # ======================================================
    # GET
    # ======================================================

    if request.method == "GET":

        return render_template(
            "registro_adn.html"
        )


    # ======================================================
    # POST
    # ======================================================

    try:

        # ==================================================
        # ENLACE REGISTRO
        # ==================================================

        enlace_registro = request.form.get(
            "enlace_registro",
            ""
        ).strip()


        # ==================================================
        # COMPATIBILIDAD
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

                    "registro_adn.html",

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
        # PREPARAR JOB
        # ==================================================

        resultado = preparar_registro_adn(

            enlace_registro=
                enlace_registro,

            codigo_integracion=
                codigo_integracion,

            personas=
                personas

        )


        # ==================================================
        # VALIDAR RESPUESTA
        # ==================================================

        if not isinstance(
            resultado,
            dict
        ):

            raise RuntimeError(
                "El servicio de registro devolvió "
                "una respuesta no válida."
            )


        # ==================================================
        # MÁXIMO DE PROCESOS ALCANZADO
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

                "registro_adn.html",

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
        # JOB ID
        # ==================================================

        job_id = str(

            resultado.get(
                "job_id",
                ""
            )

        ).strip()


        if not job_id:

            raise RuntimeError(

                "DAVIS no generó el identificador "
                "del proceso."

            )


        # ==================================================
        # GUARDAR JOB EN SESIÓN
        # ==================================================

        guardar_job_registro_en_sesion(
            job_id
        )


        # ==================================================
        # IR AL PROGRESO DEL JOB ESPECÍFICO
        # ==================================================

        return redirect(

            url_for(

                "progreso_registro",

                job_id=job_id

            )

        )


    # ======================================================
    # ERROR DATOS
    # ======================================================

    except DataError as error:

        return render_template(

            "registro_adn.html",

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
            "ERROR INICIANDO REGISTRO ADN:",
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

            "registro_adn.html",

            error=mensaje,

            mensaje_error=mensaje

        )


# ==========================================================
# PROGRESO REGISTRO POR JOB
# ==========================================================

@app.get(
    "/registro/progreso/<job_id>"
)
def progreso_registro(
    job_id
):

    job_id = str(
        job_id
    ).strip()


    # ======================================================
    # SEGURIDAD DE SESIÓN
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
# COMPATIBILIDAD URL ANTERIOR
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

        job_id = obtener_ultimo_job_sesion()


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
# ==========================================================
#
#                 API REGISTRO POR JOB
#
# ==========================================================
# ==========================================================


# ==========================================================
# ESTADO
# ==========================================================

@app.get(
    "/api/registro/<job_id>/estado"
)
def api_registro_estado(
    job_id
):

    job_id = str(
        job_id
    ).strip()


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

            "omitidos":
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

            "motivo_cancelacion":
                "",

            "jobs_activos":
                0,

            "max_jobs":
                5,

            "log":
                []

        }), 500


# ==========================================================
# REVISIÓN
# ==========================================================

@app.get(
    "/api/registro/<job_id>/revision"
)
def api_registro_revision(
    job_id
):

    job_id = str(
        job_id
    ).strip()


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


        if not isinstance(
            revision,
            dict
        ):

            return jsonify({

                "ok":
                    False,

                "job_id":
                    job_id,

                "mensaje":
                    "Los datos de revisión no son válidos."

            }), 500


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

        print(
            "ERROR REVISION REGISTRO:",
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
# CORREGIR
# ==========================================================

@app.post(
    "/api/registro/<job_id>/corregir"
)
def api_registro_corregir(
    job_id
):

    job_id = str(
        job_id
    ).strip()


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
        # FORM NORMAL
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
        # ENVIAR CORRECCIÓN
        # ==================================================

        resultado = enviar_correccion_registro(

            datos,

            job_id=job_id

        )


        if not isinstance(
            resultado,
            dict
        ):

            return jsonify({

                "ok":
                    False,

                "mensaje":
                    "DAVIS no pudo procesar la corrección."

            }), 500


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
# SALTAR PERSONA
# ==========================================================

@app.post(
    "/api/registro/<job_id>/saltar"
)
def api_registro_saltar(
    job_id
):

    job_id = str(
        job_id
    ).strip()


    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

        resultado = saltar_persona_registro(
            job_id=job_id
        )


        if not isinstance(
            resultado,
            dict
        ):

            return jsonify({

                "ok":
                    False,

                "mensaje":
                    "DAVIS no pudo procesar la omisión."

            }), 500


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

        print(
            "ERROR SALTANDO PERSONA:",
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
# HEARTBEAT
# ==========================================================

@app.post(
    "/api/registro/<job_id>/heartbeat"
)
def api_registro_heartbeat(
    job_id
):

    job_id = str(
        job_id
    ).strip()


    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

        resultado = registrar_heartbeat(
            job_id
        )


        if not isinstance(
            resultado,
            dict
        ):

            return jsonify({

                "ok":
                    False,

                "mensaje":
                    "Respuesta de heartbeat no válida."

            }), 500


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

        print(
            "ERROR HEARTBEAT REGISTRO:",
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
# DETENER JOB ESPECÍFICO
# ==========================================================

@app.post(
    "/api/registro/<job_id>/detener"
)
def api_registro_detener(
    job_id
):

    job_id = str(
        job_id
    ).strip()


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
# ==========================================================
#
#           COMPATIBILIDAD REGISTRO ANTERIOR
#
# ==========================================================
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


    if not job_id:

        job_id = obtener_ultimo_job_sesion()


    if not job_id:

        return jsonify({

            "estado":
                "no_encontrado",

            "mensaje":
                "No existe un proceso de registro en esta sesión."

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

        job_id = obtener_ultimo_job_sesion()


    if not job_id:

        return jsonify({

            "ok":
                False,

            "mensaje":
                "No existe un proceso de registro."

        }), 400


    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

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
# CORRECCIÓN ANTIGUA
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

        job_id = obtener_ultimo_job_sesion()


    if not job_id:

        return jsonify({

            "ok":
                False,

            "mensaje":
                "No existe un proceso de registro."

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


    try:

        resultado = enviar_correccion_registro(

            datos,

            job_id=job_id

        )


        return jsonify(
            resultado
        )


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
# SALTAR PERSONA - COMPATIBILIDAD
# ==========================================================

@app.post(
    "/api/registro/saltar"
)
def api_registro_saltar_compatibilidad():

    job_id = request.args.get(
        "job_id",
        ""
    ).strip()


    if not job_id:

        job_id = obtener_ultimo_job_sesion()


    if not job_id:

        return jsonify({

            "ok":
                False,

            "mensaje":
                "No existe un proceso de registro."

        }), 400


    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

        resultado = saltar_persona_registro(
            job_id=job_id
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

            "mensaje":
                str(
                    error
                )

        }), 500


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

        job_id = obtener_ultimo_job_sesion()


    if not job_id:

        return jsonify({

            "ok":
                False,

            "mensaje":
                "No existe un proceso de registro."

        }), 400


    if not job_registro_pertenece_a_sesion(
        job_id
    ):

        return respuesta_job_no_autorizado()


    try:

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
#                     ERRORES
#
# ==========================================================
# ==========================================================


# ==========================================================
# ARCHIVO DEMASIADO GRANDE
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
# 404
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
# 500
# ==========================================================

@app.errorhandler(
    500
)
def error_interno(
    error
):

    print(
        "ERROR INTERNO DAVIS:",
        error
    )


    return render_template(

        "resultado.html",

        titulo=
            "Error de DAVIS",

        mensaje=(
            "Ocurrió un error interno. "
            "Intenta nuevamente."
        )

    ), 500


# ==========================================================
# ==========================================================
#
#                  EJECUCIÓN LOCAL
#
# ==========================================================
# ==========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True,

        use_reloader=False

    )