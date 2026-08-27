import os
import sys
import json
import uuid
import subprocess
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
# VARIABLES DEL PROCESO
# ==========================================================

PROCESO_ASISTENCIA = None

TOTAL_ASISTENCIA = 0

PROCESO_DETENIDO = False


# ==========================================================
# INICIAR ASISTENCIA
# ==========================================================

def preparar_asistencia(
    enlace_actividad,
    codigo_integracion,
    personas
):

    global PROCESO_ASISTENCIA
    global TOTAL_ASISTENCIA
    global PROCESO_DETENIDO


    # ======================================================
    # VALIDACIONES
    # ======================================================

    if not enlace_actividad:

        raise ValueError(
            "No se recibió el enlace de asistencia."
        )


    if not codigo_integracion:

        raise ValueError(
            "No se recibió el código de integración."
        )


    if not personas:

        raise ValueError(
            "No se recibieron personas para procesar."
        )


    # ======================================================
    # EVITAR DOS PROCESOS
    # ======================================================

    if PROCESO_ASISTENCIA is not None:

        if PROCESO_ASISTENCIA.poll() is None:

            return {

                "ok":
                    False,

                "mensaje":
                    "Ya existe un proceso de asistencia ejecutándose."

            }


    # ======================================================
    # REINICIAR
    # ======================================================

    TOTAL_ASISTENCIA = len(
        personas
    )


    PROCESO_DETENIDO = False


    # ======================================================
    # CREAR JSON TEMPORAL
    # ======================================================

    identificador = str(
        uuid.uuid4()
    )


    ruta_json = os.path.join(

        CARPETA_TEMP,

        f"asistencia_{identificador}.json"

    )


    with open(
        ruta_json,
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(

            personas,

            archivo,

            ensure_ascii=False,

            indent=4

        )


    # ======================================================
    # asistencia.py
    # ======================================================

    ruta_script = os.path.join(
        BASE_DIR,
        "asistencia.py"
    )


    if not os.path.exists(
        ruta_script
    ):

        raise FileNotFoundError(

            "No se encontró asistencia.py "
            "en la carpeta principal de DAVIS."

        )


    # ======================================================
    # VARIABLES PARA asistencia.py
    # ======================================================

    env = os.environ.copy()


    env[
        "DAVIS_ASISTENCIA_URL"
    ] = enlace_actividad


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


    # ======================================================
    # LIMPIAR LOG
    # ======================================================

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
            f"Registros recibidos: {TOTAL_ASISTENCIA}\n"
        )


        archivo.write(
            "Preparando Playwright...\n"
        )


    # ======================================================
    # ABRIR LOG
    # ======================================================

    log = open(

        RUTA_LOG_ASISTENCIA,

        "a",

        encoding="utf-8"

    )


    # ======================================================
    # EJECUTAR asistencia.py
    # ======================================================

    try:

        PROCESO_ASISTENCIA = subprocess.Popen(

            [
                sys.executable,
                ruta_script
            ],

            cwd=BASE_DIR,

            stdout=log,

            stderr=subprocess.STDOUT,

            env=env

        )


    except Exception as error:

        log.close()


        raise RuntimeError(

            f"No se pudo iniciar asistencia.py: {error}"

        )


    # ======================================================
    # RESPUESTA
    # ======================================================

    return {

        "ok":
            True,

        "mensaje":
            "Asistencia iniciada correctamente.",

        "total":
            TOTAL_ASISTENCIA

    }


# ==========================================================
# LEER LOG
# ==========================================================

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


# ==========================================================
# CONTAR LÍNEAS
# ==========================================================

def contar_lineas_exactas(
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
# OBTENER ESTADO
# ==========================================================

def obtener_estado_asistencia():

    global PROCESO_ASISTENCIA
    global TOTAL_ASISTENCIA
    global PROCESO_DETENIDO


    contenido = leer_log_asistencia()


    # ======================================================
    # ESTADO
    # ======================================================

    if PROCESO_DETENIDO:

        estado = "detenido"


    elif PROCESO_ASISTENCIA is None:

        estado = "listo"


    elif PROCESO_ASISTENCIA.poll() is None:

        estado = "ejecutando"


    elif PROCESO_ASISTENCIA.returncode == 0:

        estado = "finalizado"


    else:

        estado = "error"


    # ======================================================
    # REGISTRO ACTUAL
    #
    # ASISTENCIA 25 DE 75
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


        actual = int(
            ultimo[0]
        )


        total = int(
            ultimo[1]
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


    # ======================================================
    # FINALIZADO
    # ======================================================

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
    # NIE ACTUAL
    # ======================================================

    nies = re.findall(

        r"^NIE:\s*(.+)$",

        contenido,

        flags=re.MULTILINE

    )


    nie_actual = ""


    if nies:

        nie_actual = nies[
            -1
        ].strip()


    # ======================================================
    # ENVIADAS
    # ======================================================

    enviadas = contar_lineas_exactas(

        contenido,

        "✅ ASISTENCIA ENVIADA"

    )


    # ======================================================
    # YA TENÍAN ASISTENCIA
    # ======================================================

    ya_existentes = contar_lineas_exactas(

        contenido,

        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"

    )


    # ======================================================
    # COMPATIBILIDAD CON LOG VIEJO
    # ======================================================

    ya_existentes_viejo = contar_lineas_exactas(

        contenido,

        "⚠️ YA EXISTE UNA ASISTENCIA"

    )


    ya_existentes += ya_existentes_viejo


    # ======================================================
    # NO ENCONTRADOS
    # ======================================================

    no_encontrados = contar_lineas_exactas(

        contenido,

        "🔎 NIE NO ENCONTRADO"

    )


    # ======================================================
    # SIN DOCUMENTO
    # ======================================================

    sin_documento = contar_lineas_exactas(

        contenido,

        "⚠️ Registro sin documento"

    )


    # ======================================================
    # ERRORES
    # ======================================================

    error_registro = contar_lineas_exactas(

        contenido,

        "❌ ERROR EN EL REGISTRO"

    )


    error_timeout = contar_lineas_exactas(

        contenido,

        "❌ ERROR DE TIEMPO DE ESPERA"

    )


    error_boton = contar_lineas_exactas(

        contenido,

        "❌ No apareció el botón"

    )


    error_habilitado = contar_lineas_exactas(

        contenido,

        "❌ El botón de asistencia"

    )


    error_confirmacion = contar_lineas_exactas(

        contenido,

        "❌ NO SE PUDO CONFIRMAR"

    )


    error_formulario = contar_lineas_exactas(

        contenido,

        "❌ No se pudo acceder al formulario"

    )


    errores = (

        error_registro

        +

        error_timeout

        +

        error_boton

        +

        error_habilitado

        +

        error_confirmacion

        +

        error_formulario

    )


    # ======================================================
    # TOMAR RESUMEN FINAL CUANDO TERMINE
    # ======================================================

    final_enviadas = re.findall(

        r"Asistencias enviadas:\s*(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    final_ya_existentes = re.findall(

        r"Ya ten[ií]an asistencia:\s*(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    final_no_encontrados = re.findall(

        r"NIE no encontrados:\s*(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    final_sin_documento = re.findall(

        r"Sin documento:\s*(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    final_errores = re.findall(

        r"Errores:\s*(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    if final_enviadas:

        enviadas = int(
            final_enviadas[-1]
        )


    if final_ya_existentes:

        ya_existentes = int(
            final_ya_existentes[-1]
        )


    if final_no_encontrados:

        no_encontrados = int(
            final_no_encontrados[-1]
        )


    if final_sin_documento:

        sin_documento = int(
            final_sin_documento[-1]
        )


    if final_errores:

        errores = int(
            final_errores[-1]
        )


    # ======================================================
    # ÚLTIMAS LÍNEAS
    # ======================================================

    lineas = []


    for linea in contenido.splitlines():

        linea = linea.strip()


        if linea:

            lineas.append(
                linea
            )


    ultimas_lineas = lineas[
        -15:
    ]


    # ======================================================
    # RESPUESTA A DAVIS WEB
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

        "nie":
            nie_actual,

        "enviadas":
            enviadas,

        "ya_existentes":
            ya_existentes,

        "no_encontrados":
            no_encontrados,

        "sin_documento":
            sin_documento,

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


    if PROCESO_ASISTENCIA is None:

        return False


    if PROCESO_ASISTENCIA.poll() is not None:

        return False


    try:

        PROCESO_ASISTENCIA.terminate()


        PROCESO_DETENIDO = True


        return True


    except Exception:

        return False