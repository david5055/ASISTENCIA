import os
import sys
import json
import uuid
import time
import shutil
import signal
import subprocess
import threading
import re


# ==========================================================
# RUTAS
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

CARPETA_TEMP = os.path.join(
    BASE_DIR,
    "temp"
)

CARPETA_LOGS = os.path.join(
    BASE_DIR,
    "logs"
)

os.makedirs(
    CARPETA_TEMP,
    exist_ok=True
)

os.makedirs(
    CARPETA_LOGS,
    exist_ok=True
)


# ==========================================================
# CONFIGURACIÓN MULTIUSUARIO
#
# Se puede cambiar desde Railway:
#
# DAVIS_MAX_JOBS=5
# DAVIS_ABANDON_TIMEOUT=180
# DAVIS_MAX_JOB_SECONDS=3600
# ==========================================================

MAX_JOBS = int(
    os.getenv(
        "DAVIS_MAX_JOBS",
        "5"
    )
)

ABANDON_TIMEOUT = int(
    os.getenv(
        "DAVIS_ABANDON_TIMEOUT",
        "180"
    )
)

MAX_JOB_SECONDS = int(
    os.getenv(
        "DAVIS_MAX_JOB_SECONDS",
        "3600"
    )
)

WATCHDOG_INTERVAL = int(
    os.getenv(
        "DAVIS_WATCHDOG_INTERVAL",
        "10"
    )
)

JOB_RETENTION_SECONDS = int(
    os.getenv(
        "DAVIS_JOB_RETENTION_SECONDS",
        "7200"
    )
)


# ==========================================================
# ESTADOS TERMINALES
# ==========================================================

ESTADOS_TERMINALES = {

    "finalizado",

    "error",

    "detenido",

    "cancelado_abandono",

    "cancelado_tiempo"

}


# ==========================================================
# JOBS ACTIVOS
#
# Cada usuario tendrá su propio JOB.
#
# JOBS = {
#
#    "abc123": {
#        process,
#        log,
#        json,
#        control_dir,
#        heartbeat,
#        ...
#    }
#
# }
# ==========================================================

JOBS = {}

JOBS_LOCK = threading.RLock()

WATCHDOG_INICIADO = False


# ==========================================================
# CAMPOS PERMITIDOS PARA CORRECCIÓN
# ==========================================================

CAMPOS_PERSONA = (

    "tipo_documento",

    "documento",

    "nombre",

    "genero",

    "fecha_nacimiento",

    "telefono",

    "whatsapp",

    "correo",

    "departamento",

    "municipio",

    "distrito",

    "residencia",

    "direccion",

    "institucion",

    "cargo"

)


# ==========================================================
# GUARDAR JSON SEGURO
# ==========================================================

def guardar_json_seguro(
    ruta,
    datos
):

    temporal = (
        ruta
        +
        ".tmp"
    )

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
# LEER JSON SEGURO
# ==========================================================

def leer_json_seguro(
    ruta
):

    if not ruta:

        return None

    if not os.path.exists(
        ruta
    ):

        return None

    try:

        with open(
            ruta,
            "r",
            encoding="utf-8"
        ) as archivo:

            return json.load(
                archivo
            )

    except Exception:

        return None


# ==========================================================
# ELIMINAR ARCHIVO
# ==========================================================

def eliminar_archivo(
    ruta
):

    try:

        if (
            ruta
            and
            os.path.exists(
                ruta
            )
        ):

            os.remove(
                ruta
            )

    except Exception:

        pass


# ==========================================================
# ELIMINAR CARPETA
# ==========================================================

def eliminar_carpeta(
    ruta
):

    try:

        if (
            ruta
            and
            os.path.isdir(
                ruta
            )
        ):

            shutil.rmtree(
                ruta,
                ignore_errors=True
            )

    except Exception:

        pass


# ==========================================================
# ESCRIBIR AL LOG DEL JOB
# ==========================================================

def escribir_log_job(
    job,
    mensaje
):

    try:

        with open(
            job["log_path"],
            "a",
            encoding="utf-8"
        ) as archivo:

            archivo.write(
                str(mensaje)
                +
                "\n"
            )

    except Exception:

        pass


# ==========================================================
# LEER LOG
# ==========================================================

def leer_log_job(
    job
):

    ruta = job.get(
        "log_path",
        ""
    )

    if not ruta:

        return ""

    if not os.path.exists(
        ruta
    ):

        return ""

    try:

        with open(
            ruta,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as archivo:

            return archivo.read()

    except Exception:

        return ""


# ==========================================================
# RUTA REVISIÓN
# ==========================================================

def ruta_revision_job(
    job
):

    return os.path.join(

        job[
            "control_dir"
        ],

        "revision_pendiente.json"

    )


# ==========================================================
# RUTA CORRECCIÓN
# ==========================================================

def ruta_correccion_job(
    job
):

    return os.path.join(

        job[
            "control_dir"
        ],

        "correccion.json"

    )


# ==========================================================
# LEER REVISIÓN DIRECTAMENTE
#
# Esta función NO intenta resolver job_id.
# ==========================================================

def leer_revision_job(
    job
):

    ruta = ruta_revision_job(
        job
    )

    datos = leer_json_seguro(
        ruta
    )

    if not isinstance(
        datos,
        dict
    ):

        return None

    return datos


# ==========================================================
# LIMPIAR DATOS SENSIBLES
#
# Cuando termina un trabajo:
#
# - elimina JSON
# - elimina correcciones
# - elimina revisión
#
# Conservamos solamente el log temporalmente.
# ==========================================================

def limpiar_datos_job(
    job
):

    if job.get(
        "datos_limpiados",
        False
    ):

        return

    eliminar_archivo(
        job.get(
            "json_path",
            ""
        )
    )

    eliminar_carpeta(
        job.get(
            "control_dir",
            ""
        )
    )

    job[
        "datos_limpiados"
    ] = True


# ==========================================================
# MATAR PYTHON + PLAYWRIGHT + CHROMIUM
# ==========================================================

def matar_proceso_job(
    job
):

    proceso = job.get(
        "process"
    )

    if proceso is None:

        return

    if proceso.poll() is not None:

        return


    # ======================================================
    # WINDOWS
    # ======================================================

    if os.name == "nt":

        try:

            subprocess.run(

                [
                    "taskkill",

                    "/PID",

                    str(
                        proceso.pid
                    ),

                    "/T",

                    "/F"
                ],

                stdout=subprocess.DEVNULL,

                stderr=subprocess.DEVNULL,

                check=False

            )

        except Exception:

            try:

                proceso.kill()

            except Exception:

                pass


    # ======================================================
    # LINUX / RAILWAY
    # ======================================================

    else:

        try:

            grupo = os.getpgid(
                proceso.pid
            )

            os.killpg(
                grupo,
                signal.SIGTERM
            )

            try:

                proceso.wait(
                    timeout=5
                )

            except subprocess.TimeoutExpired:

                os.killpg(
                    grupo,
                    signal.SIGKILL
                )

        except Exception:

            try:

                proceso.terminate()

                proceso.wait(
                    timeout=5
                )

            except Exception:

                try:

                    proceso.kill()

                except Exception:

                    pass


# ==========================================================
# ACTUALIZAR ESTADO SEGÚN EL PROCESO
# ==========================================================

def refrescar_estado_job(
    job
):

    estado_actual = job.get(
        "estado",
        "ejecutando"
    )


    # ======================================================
    # NO CAMBIAR UN ESTADO TERMINAL
    # ======================================================

    if estado_actual in ESTADOS_TERMINALES:

        return estado_actual


    proceso = job.get(
        "process"
    )


    if proceso is None:

        job[
            "estado"
        ] = "error"

        job[
            "finished_at"
        ] = time.time()

        return "error"


    codigo = proceso.poll()


    # ======================================================
    # TODAVÍA ESTÁ VIVO
    # ======================================================

    if codigo is None:

        revision = leer_revision_job(
            job
        )


        if revision is not None:

            job[
                "estado"
            ] = "requiere_revision"

            return "requiere_revision"


        job[
            "estado"
        ] = "ejecutando"

        return "ejecutando"


    # ======================================================
    # TERMINÓ
    # ======================================================

    if codigo == 0:

        job[
            "estado"
        ] = "finalizado"

    else:

        job[
            "estado"
        ] = "error"


    if not job.get(
        "finished_at"
    ):

        job[
            "finished_at"
        ] = time.time()


    limpiar_datos_job(
        job
    )


    return job[
        "estado"
    ]


# ==========================================================
# RESOLVER JOB
#
# Cuando ya hagamos app.py multiusuario,
# siempre enviaremos job_id.
#
# Si existe solo uno, esta función permite mantener
# compatibilidad temporal.
# ==========================================================

def resolver_job_id(
    job_id=None
):

    if job_id:

        return str(
            job_id
        ).strip()


    with JOBS_LOCK:

        if len(
            JOBS
        ) == 1:

            return next(
                iter(
                    JOBS
                )
            )


    return ""


# ==========================================================
# OBTENER JOB
# ==========================================================

def obtener_job(
    job_id=None
):

    identificador = resolver_job_id(
        job_id
    )


    if not identificador:

        return None


    with JOBS_LOCK:

        return JOBS.get(
            identificador
        )


# ==========================================================
# CONTAR JOBS ACTIVOS
# ==========================================================

def contar_jobs_activos():

    activos = 0


    with JOBS_LOCK:

        for job in JOBS.values():

            estado = refrescar_estado_job(
                job
            )


            if estado not in ESTADOS_TERMINALES:

                activos += 1


    return activos


# ==========================================================
# OBTENER URL REGISTRO
# ==========================================================

def obtener_url_registro(
    enlace_registro="",
    codigo_integracion=""
):

    # ======================================================
    # URL ENVIADA DESDE LA WEB
    # ======================================================

    url = str(
        enlace_registro or ""
    ).strip()


    if url.startswith(
        (
            "http://",
            "https://"
        )
    ):

        return url


    # ======================================================
    # VARIABLE DE RAILWAY
    # ======================================================

    url = os.getenv(
        "REGISTRO_URL",
        ""
    ).strip()


    if url.startswith(
        (
            "http://",
            "https://"
        )
    ):

        return url


    # ======================================================
    # COMPATIBILIDAD TEMPORAL
    # ======================================================

    posible_url = str(
        codigo_integracion or ""
    ).strip()


    if posible_url.startswith(
        (
            "http://",
            "https://"
        )
    ):

        return posible_url


    return ""


# ==========================================================
# PREPARAR NUEVO REGISTRO
# ==========================================================

def preparar_registro(
    codigo_integracion="",
    personas=None,
    enlace_registro=""
):

    if personas is None:

        personas = []


    # ======================================================
    # VALIDAR LISTA
    # ======================================================

    if not isinstance(
        personas,
        list
    ):

        raise ValueError(
            "Los datos deben contener una lista de personas."
        )


    if len(
        personas
    ) == 0:

        raise ValueError(
            "No se recibieron personas para registrar."
        )


    # ======================================================
    # URL
    # ======================================================

    url_registro = obtener_url_registro(

        enlace_registro=
            enlace_registro,

        codigo_integracion=
            codigo_integracion

    )


    if not url_registro:

        raise ValueError(

            "DAVIS no tiene configurada "
            "la URL del formulario de registro."

        )


    # ======================================================
    # REVISAR LÍMITE
    # ======================================================

    with JOBS_LOCK:

        activos = contar_jobs_activos()


        if activos >= MAX_JOBS:

            return {

                "ok":
                    False,

                "mensaje":
                    (
                        "DAVIS está procesando el máximo "
                        f"de {MAX_JOBS} trabajos simultáneos. "
                        "Espera a que uno finalice."
                    ),

                "jobs_activos":
                    activos,

                "max_jobs":
                    MAX_JOBS

            }


        # ==================================================
        # JOB ÚNICO
        # ==================================================

        job_id = uuid.uuid4().hex


        json_path = os.path.join(

            CARPETA_TEMP,

            f"registro_{job_id}.json"

        )


        control_dir = os.path.join(

            CARPETA_TEMP,

            f"control_registro_{job_id}"

        )


        log_path = os.path.join(

            CARPETA_LOGS,

            f"registro_{job_id}.log"

        )


        os.makedirs(
            control_dir,
            exist_ok=True
        )


        # ==================================================
        # JSON DE ESTE USUARIO
        # ==================================================

        guardar_json_seguro(
            json_path,
            personas
        )


        # ==================================================
        # LOG DE ESTE USUARIO
        # ==================================================

        with open(
            log_path,
            "w",
            encoding="utf-8"
        ) as archivo:

            archivo.write(
                "======================================\n"
            )

            archivo.write(
                "SISTEMA DAVIS - REGISTRO\n"
            )

            archivo.write(
                "======================================\n"
            )

            archivo.write(
                f"JOB: {job_id}\n"
            )

            archivo.write(
                f"Registros recibidos: {len(personas)}\n"
            )

            archivo.write(
                "Preparando Playwright...\n"
            )


        # ==================================================
        # registro.py
        # ==================================================

        ruta_script = os.path.join(
            BASE_DIR,
            "registro.py"
        )


        if not os.path.exists(
            ruta_script
        ):

            eliminar_archivo(
                json_path
            )

            eliminar_carpeta(
                control_dir
            )

            raise FileNotFoundError(

                "No se encontró registro.py "
                "en la carpeta principal de DAVIS."

            )


        ahora = time.time()


        # ==================================================
        # CREAR INFORMACIÓN DEL JOB
        # ==================================================

        job = {

            "job_id":
                job_id,

            "process":
                None,

            "total":
                len(
                    personas
                ),

            "created_at":
                ahora,

            "started_at":
                ahora,

            "last_heartbeat":
                ahora,

            "finished_at":
                None,

            "estado":
                "iniciando",

            "motivo_cancelacion":
                "",

            "json_path":
                json_path,

            "control_dir":
                control_dir,

            "log_path":
                log_path,

            "datos_limpiados":
                False

        }


        JOBS[
            job_id
        ] = job


        # ==================================================
        # VARIABLES PARA registro.py
        # ==================================================

        env = os.environ.copy()


        env[
            "DAVIS_REGISTRO_URL"
        ] = url_registro


        env[
            "DAVIS_ARCHIVO_JSON"
        ] = json_path


        env[
            "DAVIS_REGISTRO_JOB_ID"
        ] = job_id


        env[
            "DAVIS_REGISTRO_CONTROL_DIR"
        ] = control_dir


        env[
            "PYTHONIOENCODING"
        ] = "utf-8"


        env[
            "PYTHONUTF8"
        ] = "1"


        env[
            "PYTHONUNBUFFERED"
        ] = "1"


        # ==================================================
        # LOG DEL SUBPROCESO
        # ==================================================

        log = open(

            log_path,

            "a",

            encoding="utf-8"

        )


        opciones = {}


        # ==================================================
        # WINDOWS
        # ==================================================

        if os.name == "nt":

            opciones[
                "creationflags"
            ] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
            )


        # ==================================================
        # LINUX / RAILWAY
        # ==================================================

        else:

            opciones[
                "start_new_session"
            ] = True


        # ==================================================
        # INICIAR PLAYWRIGHT
        # ==================================================

        try:

            proceso = subprocess.Popen(

                [
                    sys.executable,
                    ruta_script
                ],

                cwd=BASE_DIR,

                stdout=log,

                stderr=subprocess.STDOUT,

                env=env,

                **opciones

            )


            job[
                "process"
            ] = proceso


            job[
                "estado"
            ] = "ejecutando"


        except Exception as error:

            job[
                "estado"
            ] = "error"


            job[
                "finished_at"
            ] = time.time()


            limpiar_datos_job(
                job
            )


            raise RuntimeError(

                "No se pudo iniciar registro.py: "
                f"{error}"

            )


        finally:

            try:

                log.close()

            except Exception:

                pass


    # ======================================================
    # ASEGURAR WATCHDOG
    # ======================================================

    iniciar_watchdog()


    return {

        "ok":
            True,

        "mensaje":
            "Registro iniciado correctamente.",

        "total":
            len(
                personas
            ),

        "job_id":
            job_id,

        "jobs_activos":
            contar_jobs_activos(),

        "max_jobs":
            MAX_JOBS

    }


# ==========================================================
# OBTENER REVISIÓN PENDIENTE
# ==========================================================

def obtener_revision_pendiente(
    job_id=None
):

    job = obtener_job(
        job_id
    )


    if not job:

        return None


    return leer_revision_job(
        job
    )


# ==========================================================
# HEARTBEAT
#
# La página de progreso enviará una señal cada 15 segundos.
# ==========================================================

def registrar_heartbeat(
    job_id
):

    identificador = str(
        job_id or ""
    ).strip()


    if not identificador:

        return {

            "ok":
                False,

            "mensaje":
                "Falta job_id."

        }


    with JOBS_LOCK:

        job = JOBS.get(
            identificador
        )


        if not job:

            return {

                "ok":
                    False,

                "mensaje":
                    "El proceso ya no existe."

            }


        estado = refrescar_estado_job(
            job
        )


        if estado in ESTADOS_TERMINALES:

            return {

                "ok":
                    False,

                "estado":
                    estado,

                "mensaje":
                    "El proceso ya terminó."

            }


        job[
            "last_heartbeat"
        ] = time.time()


        return {

            "ok":
                True,

            "estado":
                estado,

            "job_id":
                identificador

        }


# ==========================================================
# CONTAR LÍNEAS
# ==========================================================

def contar_lineas(
    contenido,
    frase
):

    contador = 0


    for linea in contenido.splitlines():

        if linea.strip().startswith(
            frase
        ):

            contador += 1


    return contador


# ==========================================================
# CONTAR REVISIONES ÚNICAS
# ==========================================================

def contar_revisiones_unicas(
    contenido
):

    registros = set()

    registro_actual = None


    patron = re.compile(

        r"REGISTRO\s+(\d+)\s+DE\s+(\d+)",

        flags=re.IGNORECASE

    )


    for linea in contenido.splitlines():

        limpia = linea.strip()


        coincidencia = patron.search(
            limpia
        )


        if coincidencia:

            registro_actual = int(
                coincidencia.group(
                    1
                )
            )


        if limpia.startswith(
            "⏸️ REQUIERE REVISIÓN"
        ):

            if registro_actual is not None:

                registros.add(
                    registro_actual
                )


    return len(
        registros
    )


# ==========================================================
# DOCUMENTO ACTUAL
# ==========================================================

def obtener_documento_actual(
    contenido
):

    documentos = re.findall(

        r"^DOCUMENTO:\s*(.+)$",

        contenido,

        flags=
            re.MULTILINE
            |
            re.IGNORECASE

    )


    if documentos:

        return documentos[
            -1
        ].strip()


    documentos = re.findall(

        r"^(?:DUI|NIE):\s*(.+)$",

        contenido,

        flags=
            re.MULTILINE
            |
            re.IGNORECASE

    )


    if documentos:

        return documentos[
            -1
        ].strip()


    return ""


# ==========================================================
# OBTENER ESTADO DE UN JOB
# ==========================================================

def obtener_estado_registro(
    job_id=None
):

    identificador = resolver_job_id(
        job_id
    )


    # ======================================================
    # JOB NO ENCONTRADO
    # ======================================================

    if not identificador:

        return {

            "estado":
                "no_encontrado",

            "job_id":
                "",

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
                0,

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
                contar_jobs_activos(),

            "max_jobs":
                MAX_JOBS,

            "log":
                []

        }


    with JOBS_LOCK:

        job = JOBS.get(
            identificador
        )


        if not job:

            return {

                "estado":
                    "no_encontrado",

                "job_id":
                    identificador,

                "mensaje":
                    "Este proceso ya no existe."

            }


        estado = refrescar_estado_job(
            job
        )


        total_job = job.get(
            "total",
            0
        )


        motivo_cancelacion = job.get(
            "motivo_cancelacion",
            ""
        )


    contenido = leer_log_job(
        job
    )


    revision = leer_revision_job(
        job
    )


    # ======================================================
    # REGISTRO ACTUAL
    # ======================================================

    coincidencias = re.findall(

        r"REGISTRO\s+(\d+)\s+DE\s+(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    actual = 0

    total = total_job


    if coincidencias:

        ultimo = coincidencias[
            -1
        ]


        actual = int(
            ultimo[
                0
            ]
        )


        total = int(
            ultimo[
                1
            ]
        )


    # ======================================================
    # PORCENTAJE
    # ======================================================

    if total > 0:

        porcentaje = round(

            (
                actual
                /
                total
            )

            *

            100

        )

    else:

        porcentaje = 0


    if estado == "finalizado":

        porcentaje = 100


        if total > 0:

            actual = total


    porcentaje = max(

        0,

        min(
            porcentaje,
            100
        )

    )


    # ======================================================
    # DOCUMENTO
    # ======================================================

    documento = obtener_documento_actual(
        contenido
    )


    # ======================================================
    # CONTADORES
    # ======================================================

    creados = contar_lineas(

        contenido,

        "✅ BENEFICIARIO CREADO CORRECTAMENTE"

    )


    ya_registrados = contar_lineas(

        contenido,

        "⚠️ YA REGISTRADO"

    )


    revisiones = contar_revisiones_unicas(
        contenido
    )


    errores = (

        contar_lineas(

            contenido,

            "❌ ERROR DE TIEMPO DE ESPERA"

        )

        +

        contar_lineas(

            contenido,

            "❌ ERROR EN EL REGISTRO"

        )

    )


    # ======================================================
    # RESUMEN FINAL
    # ======================================================

    resumen_creados = re.findall(

        r"Beneficiarios creados:\s*(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    resumen_ya_registrados = re.findall(

        r"Ya registrados:\s*(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    resumen_revisiones = re.findall(

        r"Requirieron revisi[oó]n:\s*(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    resumen_errores = re.findall(

        r"Errores:\s*(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    if resumen_creados:

        creados = int(
            resumen_creados[
                -1
            ]
        )


    if resumen_ya_registrados:

        ya_registrados = int(
            resumen_ya_registrados[
                -1
            ]
        )


    if resumen_revisiones:

        revisiones = int(
            resumen_revisiones[
                -1
            ]
        )


    if resumen_errores:

        errores = int(
            resumen_errores[
                -1
            ]
        )


    # ======================================================
    # REVISIÓN PENDIENTE
    # ======================================================

    persona_revision = None

    motivo_revision = ""

    campos_faltantes = []


    if isinstance(
        revision,
        dict
    ):

        persona_revision = revision.get(
            "persona"
        )


        motivo_revision = str(
            revision.get(
                "motivo",
                ""
            )
        )


        campos_faltantes = revision.get(
            "campos_faltantes",
            []
        )


        if not isinstance(
            campos_faltantes,
            list
        ):

            campos_faltantes = []


        documento_revision = str(
            revision.get(
                "documento",
                ""
            )
        ).strip()


        if documento_revision:

            documento = documento_revision


    # ======================================================
    # ÚLTIMAS LÍNEAS
    # ======================================================

    lineas = []


    for linea in contenido.splitlines():

        limpia = linea.strip()


        if limpia:

            lineas.append(
                limpia
            )


    ultimas_lineas = lineas[
        -20:
    ]


    # ======================================================
    # INFORMACIÓN DE TIEMPO
    # ======================================================

    ahora = time.time()


    with JOBS_LOCK:

        ultimo_heartbeat = job.get(
            "last_heartbeat",
            ahora
        )


        iniciado = job.get(
            "started_at",
            ahora
        )


    segundos_sin_heartbeat = max(

        0,

        int(
            ahora
            -
            ultimo_heartbeat
        )

    )


    segundos_ejecutando = max(

        0,

        int(
            ahora
            -
            iniciado
        )

    )


    # ======================================================
    # RESPUESTA
    # ======================================================

    return {

        "estado":
            estado,

        "job_id":
            identificador,

        "actual":
            actual,

        "total":
            total,

        "porcentaje":
            porcentaje,

        "documento":
            documento,

        "creados":
            creados,

        "ya_registrados":
            ya_registrados,

        "revisiones":
            revisiones,

        "errores":
            errores,

        "requiere_revision":
            (
                estado
                ==
                "requiere_revision"
            ),

        "motivo_revision":
            motivo_revision,

        "campos_faltantes":
            campos_faltantes,

        "persona_revision":
            persona_revision,

        "motivo_cancelacion":
            motivo_cancelacion,

        "segundos_sin_heartbeat":
            segundos_sin_heartbeat,

        "segundos_ejecutando":
            segundos_ejecutando,

        "abandon_timeout":
            ABANDON_TIMEOUT,

        "max_job_seconds":
            MAX_JOB_SECONDS,

        "jobs_activos":
            contar_jobs_activos(),

        "max_jobs":
            MAX_JOBS,

        "log":
            ultimas_lineas

    }


# ==========================================================
# ENVIAR CORRECCIÓN
# ==========================================================

def enviar_correccion_registro(
    datos,
    job_id=None
):

    identificador = resolver_job_id(
        job_id
    )


    if not identificador:

        return {

            "ok":
                False,

            "mensaje":
                "No se encontró el proceso de registro."

        }


    with JOBS_LOCK:

        job = JOBS.get(
            identificador
        )


        if not job:

            return {

                "ok":
                    False,

                "mensaje":
                    "El proceso ya no existe."

            }


        estado = refrescar_estado_job(
            job
        )


        if estado in ESTADOS_TERMINALES:

            return {

                "ok":
                    False,

                "mensaje":
                    "El proceso de registro ya terminó."

            }


    revision = leer_revision_job(
        job
    )


    if revision is None:

        return {

            "ok":
                False,

            "mensaje":
                "No existe ningún registro esperando corrección."

        }


    if not isinstance(
        datos,
        dict
    ):

        return {

            "ok":
                False,

            "mensaje":
                "Los datos de corrección no son válidos."

        }


    datos_persona = datos.get(
        "persona",
        datos
    )


    if not isinstance(
        datos_persona,
        dict
    ):

        return {

            "ok":
                False,

            "mensaje":
                "La corrección debe contener los datos de la persona."

        }


    correccion = {}


    for campo in CAMPOS_PERSONA:

        if campo in datos_persona:

            dato = datos_persona.get(
                campo,
                ""
            )


            if dato is None:

                dato = ""


            correccion[
                campo
            ] = str(
                dato
            ).strip()


    if not correccion:

        return {

            "ok":
                False,

            "mensaje":
                "No se recibió ningún campo para corregir."

        }


    ruta = ruta_correccion_job(
        job
    )


    if os.path.exists(
        ruta
    ):

        return {

            "ok":
                False,

            "mensaje":
                (
                    "La corrección ya fue enviada. "
                    "DAVIS está procesándola."
                )

        }


    guardar_json_seguro(

        ruta,

        {

            "persona":
                correccion

        }

    )


    # ======================================================
    # CORREGIR TAMBIÉN CUENTA COMO ACTIVIDAD
    # ======================================================

    registrar_heartbeat(
        identificador
    )


    return {

        "ok":
            True,

        "job_id":
            identificador,

        "mensaje":
            (
                "Corrección enviada. "
                "DAVIS volverá a intentar este beneficiario."
            )

    }


# ==========================================================
# CANCELAR JOB
# ==========================================================

def cancelar_job(
    job_id,
    estado,
    motivo
):

    with JOBS_LOCK:

        job = JOBS.get(
            job_id
        )


        if not job:

            return False


        estado_actual = refrescar_estado_job(
            job
        )


        if estado_actual in ESTADOS_TERMINALES:

            return False


        job[
            "estado"
        ] = estado


        job[
            "motivo_cancelacion"
        ] = motivo


        job[
            "finished_at"
        ] = time.time()


    # ======================================================
    # ESCRIBIR MOTIVO
    # ======================================================

    escribir_log_job(
        job,
        ""
    )


    escribir_log_job(
        job,
        "======================================"
    )


    if estado == "cancelado_abandono":

        escribir_log_job(

            job,

            "⚠️ PROCESO CANCELADO AUTOMÁTICAMENTE POR INACTIVIDAD"

        )


    elif estado == "cancelado_tiempo":

        escribir_log_job(

            job,

            "⏱️ PROCESO CANCELADO AUTOMÁTICAMENTE POR TIEMPO MÁXIMO"

        )


    elif estado == "detenido":

        escribir_log_job(

            job,

            "■ PROCESO DETENIDO MANUALMENTE"

        )


    escribir_log_job(

        job,

        f"MOTIVO: {motivo}"

    )


    escribir_log_job(
        job,
        "======================================"
    )


    # ======================================================
    # MATAR PLAYWRIGHT Y CHROMIUM
    # ======================================================

    matar_proceso_job(
        job
    )


    # ======================================================
    # ELIMINAR DATOS TEMPORALES
    # ======================================================

    limpiar_datos_job(
        job
    )


    return True


# ==========================================================
# DETENER MANUALMENTE
# ==========================================================

def detener_registro(
    job_id=None
):

    identificador = resolver_job_id(
        job_id
    )


    if not identificador:

        return False


    return cancelar_job(

        identificador,

        "detenido",

        "El usuario detuvo el proceso manualmente."

    )


# ==========================================================
# WATCHDOG
#
# Este hilo vigila permanentemente:
#
# - pestaña cerrada
# - usuario desconectado
# - proceso trabado
# - tiempo máximo
# - procesos terminados
# ==========================================================

def watchdog_loop():

    while True:

        try:

            ahora = time.time()


            cancelar_abandono = []

            cancelar_tiempo = []

            eliminar_jobs = []


            # ==================================================
            # REVISAR TODOS LOS JOBS
            # ==================================================

            with JOBS_LOCK:

                for job_id, job in list(
                    JOBS.items()
                ):

                    estado = refrescar_estado_job(
                        job
                    )


                    # ==========================================
                    # JOB TERMINADO
                    # ==========================================

                    if estado in ESTADOS_TERMINALES:

                        terminado = job.get(
                            "finished_at"
                        )


                        if (

                            terminado

                            and

                            (
                                ahora
                                -
                                terminado
                            )

                            >
                            JOB_RETENTION_SECONDS

                        ):

                            eliminar_jobs.append(
                                job_id
                            )


                        continue


                    inicio = job.get(
                        "started_at",
                        ahora
                    )


                    ultimo_heartbeat = job.get(
                        "last_heartbeat",
                        inicio
                    )


                    # ==========================================
                    # TIEMPO MÁXIMO
                    # ==========================================

                    if (

                        MAX_JOB_SECONDS > 0

                        and

                        (
                            ahora
                            -
                            inicio
                        )

                        >
                        MAX_JOB_SECONDS

                    ):

                        cancelar_tiempo.append(
                            job_id
                        )


                        continue


                    # ==========================================
                    # PESTAÑA CERRADA / USUARIO ABANDONÓ
                    # ==========================================

                    if (

                        ABANDON_TIMEOUT > 0

                        and

                        (
                            ahora
                            -
                            ultimo_heartbeat
                        )

                        >
                        ABANDON_TIMEOUT

                    ):

                        cancelar_abandono.append(
                            job_id
                        )


            # ==================================================
            # CANCELAR POR TIEMPO
            # ==================================================

            for job_id in cancelar_tiempo:

                cancelar_job(

                    job_id,

                    "cancelado_tiempo",

                    (
                        "El proceso superó el tiempo máximo "
                        f"permitido de {MAX_JOB_SECONDS} segundos."
                    )

                )


            # ==================================================
            # CANCELAR POR ABANDONO
            # ==================================================

            for job_id in cancelar_abandono:

                cancelar_job(

                    job_id,

                    "cancelado_abandono",

                    (
                        "DAVIS dejó de recibir señales "
                        "del navegador durante más de "
                        f"{ABANDON_TIMEOUT} segundos."
                    )

                )


            # ==================================================
            # ELIMINAR JOBS ANTIGUOS
            # ==================================================

            with JOBS_LOCK:

                for job_id in eliminar_jobs:

                    job = JOBS.get(
                        job_id
                    )


                    if not job:

                        continue


                    limpiar_datos_job(
                        job
                    )


                    eliminar_archivo(
                        job.get(
                            "log_path",
                            ""
                        )
                    )


                    JOBS.pop(
                        job_id,
                        None
                    )


        except Exception as error:

            print(
                "ERROR WATCHDOG REGISTRO:",
                error
            )


        # ==================================================
        # ESPERAR ANTES DE VOLVER A REVISAR
        # ==================================================

        time.sleep(

            max(
                WATCHDOG_INTERVAL,
                2
            )

        )


# ==========================================================
# INICIAR WATCHDOG UNA SOLA VEZ
# ==========================================================

def iniciar_watchdog():

    global WATCHDOG_INICIADO


    with JOBS_LOCK:

        if WATCHDOG_INICIADO:

            return


        hilo = threading.Thread(

            target=watchdog_loop,

            name="DAVIS-Registro-Watchdog",

            daemon=True

        )


        hilo.start()


        WATCHDOG_INICIADO = True


# ==========================================================
# INICIAR WATCHDOG
# ==========================================================

iniciar_watchdog()