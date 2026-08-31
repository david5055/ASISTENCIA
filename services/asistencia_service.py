import os
import sys
import json
import uuid
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


RUTA_LOG_ASISTENCIA = os.path.join(
    CARPETA_LOGS,
    "asistencia.log"
)


# ==========================================================
# ESTADO GLOBAL
# ==========================================================

PROCESO_ASISTENCIA = None

TOTAL_ASISTENCIA = 0

PROCESO_DETENIDO = False

RUTA_JSON_ACTUAL = ""

PROCESO_LOCK = threading.RLock()


# ==========================================================
# UTILIDADES
# ==========================================================

def guardar_json_seguro(
    ruta,
    datos
):

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


def leer_log_asistencia():

    if not os.path.exists(
        RUTA_LOG_ASISTENCIA
    ):

        return ""

    try:

        with open(
            RUTA_LOG_ASISTENCIA,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as archivo:

            return archivo.read()

    except Exception:

        return ""


def contar_lineas(
    contenido,
    prefijo
):

    total = 0

    for linea in contenido.splitlines():

        if linea.strip().startswith(
            prefijo
        ):

            total += 1

    return total


def buscar_ultimo_entero(
    contenido,
    patron
):

    coincidencias = re.findall(
        patron,
        contenido,
        flags=re.IGNORECASE
    )

    if not coincidencias:

        return None

    try:

        return int(
            coincidencias[-1]
        )

    except Exception:

        return None


# ==========================================================
# MATAR PROCESO + PLAYWRIGHT + CHROMIUM
# ==========================================================

def matar_proceso(
    proceso
):

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

            return

        except Exception:

            pass


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

            return

        except Exception:

            pass


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
# PREPARAR ASISTENCIA
#
# RECIBE:
#
# 1. enlace_asistencia
# 2. codigo_integracion
# 3. personas
# ==========================================================

def preparar_asistencia(
    enlace_asistencia,
    codigo_integracion,
    personas
):

    global PROCESO_ASISTENCIA
    global TOTAL_ASISTENCIA
    global PROCESO_DETENIDO
    global RUTA_JSON_ACTUAL


    enlace_asistencia = str(
        enlace_asistencia or ""
    ).strip()


    codigo_integracion = str(
        codigo_integracion or ""
    ).strip()


    # ======================================================
    # VALIDACIONES
    # ======================================================

    if not enlace_asistencia:

        return {
            "ok": False,
            "mensaje": "Debes ingresar el enlace de asistencia."
        }


    if not enlace_asistencia.startswith(
        (
            "http://",
            "https://"
        )
    ):

        return {
            "ok": False,
            "mensaje": "El enlace de asistencia no es válido."
        }


    if not codigo_integracion:

        return {
            "ok": False,
            "mensaje": "Debes ingresar el código de integración."
        }


    if not isinstance(
        personas,
        list
    ):

        return {
            "ok": False,
            "mensaje": "Los beneficiarios deben venir en una lista."
        }


    if len(
        personas
    ) == 0:

        return {
            "ok": False,
            "mensaje": "No se recibieron beneficiarios."
        }


    with PROCESO_LOCK:

        # ==================================================
        # NO PERMITIR DOS ASISTENCIAS AL MISMO TIEMPO
        # ==================================================

        if (
            PROCESO_ASISTENCIA is not None
            and
            PROCESO_ASISTENCIA.poll() is None
        ):

            return {
                "ok": False,
                "mensaje": (
                    "Ya existe un proceso de asistencia "
                    "ejecutándose. Detén o espera a que termine "
                    "antes de iniciar otro."
                )
            }


        # ==================================================
        # LIMPIAR JSON ANTERIOR
        # ==================================================

        eliminar_archivo(
            RUTA_JSON_ACTUAL
        )


        # ==================================================
        # CREAR JSON TEMPORAL
        # ==================================================

        identificador = uuid.uuid4().hex


        ruta_json = os.path.join(
            CARPETA_TEMP,
            f"asistencia_{identificador}.json"
        )


        guardar_json_seguro(
            ruta_json,
            personas
        )


        # ==================================================
        # REINICIAR LOG
        # ==================================================

        with open(
            RUTA_LOG_ASISTENCIA,
            "w",
            encoding="utf-8"
        ) as archivo:

            archivo.write(
                "======================================\n"
            )

            archivo.write(
                "SISTEMA DAVIS - ASISTENCIA\n"
            )

            archivo.write(
                "======================================\n"
            )

            archivo.write(
                f"Registros recibidos: {len(personas)}\n"
            )

            archivo.write(
                "Preparando Playwright...\n"
            )


        # ==================================================
        # SCRIPT
        # ==================================================

        ruta_script = os.path.join(
            BASE_DIR,
            "asistencia.py"
        )


        if not os.path.exists(
            ruta_script
        ):

            eliminar_archivo(
                ruta_json
            )

            return {
                "ok": False,
                "mensaje": (
                    "No se encontró asistencia.py "
                    "en la carpeta principal de DAVIS."
                )
            }


        # ==================================================
        # VARIABLES DE ENTORNO
        # ==================================================

        env = os.environ.copy()


        env[
            "DAVIS_ASISTENCIA_URL"
        ] = enlace_asistencia


        env[
            "DAVIS_CODIGO_INTEGRACION"
        ] = codigo_integracion


        env[
            "DAVIS_ARCHIVO_JSON"
        ] = ruta_json


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
        # CONFIGURACIÓN PROCESO
        # ==================================================

        opciones = {}


        if os.name == "nt":

            opciones[
                "creationflags"
            ] = subprocess.CREATE_NEW_PROCESS_GROUP

        else:

            opciones[
                "start_new_session"
            ] = True


        # ==================================================
        # ABRIR LOG
        # ==================================================

        log = open(
            RUTA_LOG_ASISTENCIA,
            "a",
            encoding="utf-8"
        )


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


            PROCESO_ASISTENCIA = proceso

            TOTAL_ASISTENCIA = len(
                personas
            )

            PROCESO_DETENIDO = False

            RUTA_JSON_ACTUAL = ruta_json


        except Exception as error:

            eliminar_archivo(
                ruta_json
            )


            PROCESO_ASISTENCIA = None

            TOTAL_ASISTENCIA = 0

            RUTA_JSON_ACTUAL = ""


            return {
                "ok": False,
                "mensaje": (
                    "No se pudo iniciar asistencia.py: "
                    + str(
                        error
                    )
                )
            }


        finally:

            try:

                log.close()

            except Exception:

                pass


    return {
        "ok": True,
        "mensaje": "Asistencia iniciada correctamente.",
        "total": len(
            personas
        )
    }


# ==========================================================
# DOCUMENTO ACTUAL
# ==========================================================

def obtener_documento_actual(
    contenido
):

    coincidencias = re.findall(
        r"^DOCUMENTO:\s*(.+)$",
        contenido,
        flags=(
            re.MULTILINE
            |
            re.IGNORECASE
        )
    )


    if coincidencias:

        return coincidencias[
            -1
        ].strip()


    coincidencias = re.findall(
        r"^(?:NIE|DUI):\s*(.+)$",
        contenido,
        flags=(
            re.MULTILINE
            |
            re.IGNORECASE
        )
    )


    if coincidencias:

        return coincidencias[
            -1
        ].strip()


    return ""


# ==========================================================
# TIPO DOCUMENTO ACTUAL
# ==========================================================

def obtener_tipo_documento_actual(
    contenido
):

    tipos = re.findall(
        r"^TIPO_DOCUMENTO:\s*(NIE|DUI)\s*$",
        contenido,
        flags=(
            re.MULTILINE
            |
            re.IGNORECASE
        )
    )


    if tipos:

        return tipos[
            -1
        ].strip().upper()


    coincidencias = re.findall(
        r"^(NIE|DUI):\s*.+$",
        contenido,
        flags=(
            re.MULTILINE
            |
            re.IGNORECASE
        )
    )


    if coincidencias:

        return coincidencias[
            -1
        ].strip().upper()


    return ""


# ==========================================================
# ESTADO ASISTENCIA
# ==========================================================

def obtener_estado_asistencia():

    global PROCESO_ASISTENCIA
    global TOTAL_ASISTENCIA
    global PROCESO_DETENIDO
    global RUTA_JSON_ACTUAL


    contenido = leer_log_asistencia()


    # ======================================================
    # PROGRESO
    # ======================================================

    coincidencias = re.findall(
        r"ASISTENCIA\s+(\d+)\s+DE\s+(\d+)",
        contenido,
        flags=re.IGNORECASE
    )


    actual = 0

    total = TOTAL_ASISTENCIA


    if coincidencias:

        ultimo = coincidencias[
            -1
        ]


        try:

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

        except Exception:

            pass


    # ======================================================
    # DOCUMENTO ACTUAL
    # ======================================================

    documento = obtener_documento_actual(
        contenido
    )


    tipo_documento = obtener_tipo_documento_actual(
        contenido
    )


    # ======================================================
    # ASISTENCIAS ENVIADAS
    # ======================================================

    enviadas = contar_lineas(
        contenido,
        "✅ ASISTENCIA ENVIADA"
    )


    # ======================================================
    # YA TENÍAN ASISTENCIA
    # ======================================================

    ya_existentes = contar_lineas(
        contenido,
        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
    )


    # ======================================================
    # NO ENCONTRADOS
    #
    # NIE Y DUI
    # ======================================================

    no_encontrados = (

        contar_lineas(
            contenido,
            "🔎 NIE NO ENCONTRADO"
        )

        +

        contar_lineas(
            contenido,
            "🔎 DUI NO ENCONTRADO"
        )

        +

        contar_lineas(
            contenido,
            "🔎 DOCUMENTO NO ENCONTRADO"
        )

    )


    # ======================================================
    # OMITIDOS
    # ======================================================

    omitidos = (

        contar_lineas(
            contenido,
            "⚠️ REGISTRO SIN DOCUMENTO"
        )

        +

        contar_lineas(
            contenido,
            "⚠️ TIPO DE DOCUMENTO INVÁLIDO"
        )

    )


    # ======================================================
    # ERRORES
    # ======================================================

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

        +

        contar_lineas(
            contenido,
            "❌ NO SE PUDO CONFIRMAR EL ENVÍO"
        )

    )


    # ======================================================
    # RESUMEN FINAL
    # ======================================================

    resumen_enviadas = buscar_ultimo_entero(
        contenido,
        r"Asistencias enviadas:\s*(\d+)"
    )


    resumen_existentes = buscar_ultimo_entero(
        contenido,
        r"Ya ten[ií]an(?: registrada)? asistencia:\s*(\d+)"
    )


    if resumen_existentes is None:

        resumen_existentes = buscar_ultimo_entero(
            contenido,
            r"Ya ten[ií]an registrada asistencia:\s*(\d+)"
        )


    resumen_no_encontrados = buscar_ultimo_entero(
        contenido,
        r"Documentos no encontrados:\s*(\d+)"
    )


    # ======================================================
    # COMPATIBILIDAD VERSIÓN ANTERIOR
    # ======================================================

    if resumen_no_encontrados is None:

        resumen_no_encontrados = buscar_ultimo_entero(
            contenido,
            r"NIE no encontrados:\s*(\d+)"
        )


    resumen_omitidos = buscar_ultimo_entero(
        contenido,
        r"Omitidos:\s*(\d+)"
    )


    resumen_errores = buscar_ultimo_entero(
        contenido,
        r"Errores:\s*(\d+)"
    )


    if resumen_enviadas is not None:

        enviadas = resumen_enviadas


    if resumen_existentes is not None:

        ya_existentes = resumen_existentes


    if resumen_no_encontrados is not None:

        no_encontrados = resumen_no_encontrados


    if resumen_omitidos is not None:

        omitidos = resumen_omitidos


    if resumen_errores is not None:

        errores = resumen_errores


    # ======================================================
    # ESTADO DEL PROCESO
    # ======================================================

    with PROCESO_LOCK:

        proceso = PROCESO_ASISTENCIA


        if PROCESO_DETENIDO:

            estado = "detenido"


        elif proceso is None:

            estado = "listo"


        else:

            codigo = proceso.poll()


            if codigo is None:

                estado = "ejecutando"


            elif codigo == 0:

                estado = "finalizado"


            else:

                estado = "error"


    # ======================================================
    # FINALIZADO
    # ======================================================

    if estado == "finalizado":

        if total > 0:

            actual = total


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


    porcentaje = max(
        0,
        min(
            porcentaje,
            100
        )
    )


    # ======================================================
    # ÚLTIMAS LÍNEAS LOG
    # ======================================================

    lineas = []


    for linea in contenido.splitlines():

        limpia = linea.strip()


        if limpia:

            lineas.append(
                limpia
            )


    ultimas_lineas = lineas[
        -25:
    ]


    # ======================================================
    # LIMPIAR JSON TEMPORAL AL TERMINAR
    # ======================================================

    if estado in (
        "finalizado",
        "error",
        "detenido"
    ):

        eliminar_archivo(
            RUTA_JSON_ACTUAL
        )


        RUTA_JSON_ACTUAL = ""


    # ======================================================
    # RESPUESTA WEB
    # ======================================================

    return {

        "estado":
            estado,

        "actual":
            actual,

        "total":
            total,

        "porcentaje":
            porcentaje,

        "documento":
            documento,

        "tipo_documento":
            tipo_documento,

        "enviadas":
            enviadas,

        "ya_existentes":
            ya_existentes,

        "no_encontrados":
            no_encontrados,

        "omitidos":
            omitidos,

        "errores":
            errores,

        "log":
            ultimas_lineas

    }


# ==========================================================
# DETENER ASISTENCIA
# ==========================================================

def detener_asistencia():

    global PROCESO_ASISTENCIA
    global PROCESO_DETENIDO
    global RUTA_JSON_ACTUAL


    with PROCESO_LOCK:

        proceso = PROCESO_ASISTENCIA


        if proceso is None:

            return False


        if proceso.poll() is not None:

            return False


        PROCESO_DETENIDO = True


    # ======================================================
    # LOG
    # ======================================================

    try:

        with open(
            RUTA_LOG_ASISTENCIA,
            "a",
            encoding="utf-8"
        ) as archivo:

            archivo.write(
                "\n"
            )

            archivo.write(
                "======================================\n"
            )

            archivo.write(
                "■ PROCESO DETENIDO MANUALMENTE\n"
            )

            archivo.write(
                "======================================\n"
            )

    except Exception:

        pass


    # ======================================================
    # CERRAR PYTHON + PLAYWRIGHT + CHROMIUM
    # ======================================================

    matar_proceso(
        proceso
    )


    # ======================================================
    # ELIMINAR JSON
    # ======================================================

    eliminar_archivo(
        RUTA_JSON_ACTUAL
    )


    RUTA_JSON_ACTUAL = ""


    return True