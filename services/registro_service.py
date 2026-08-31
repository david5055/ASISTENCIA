import os
import sys
import json
import uuid
import shutil
import signal
import subprocess
import threading
import re


# ==========================================================
# RUTAS PRINCIPALES
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


RUTA_LOG_REGISTRO = os.path.join(
    CARPETA_LOGS,
    "registro.log"
)


# ==========================================================
# VARIABLES DEL PROCESO
# ==========================================================

PROCESO_REGISTRO = None

TOTAL_REGISTRO = 0

PROCESO_DETENIDO = False

JOB_ID_ACTUAL = ""

CONTROL_DIR_ACTUAL = ""

RUTA_JSON_ACTUAL = ""


# ==========================================================
# BLOQUEO PARA EVITAR DOS PROCESOS SIMULTÁNEOS
# ==========================================================

PROCESO_LOCK = threading.Lock()


# ==========================================================
# CAMPOS PERMITIDOS EN UNA CORRECCIÓN
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
# GUARDAR JSON DE FORMA SEGURA
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

        if ruta and os.path.exists(
            ruta
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

        if ruta and os.path.isdir(
            ruta
        ):

            shutil.rmtree(
                ruta,
                ignore_errors=True
            )


    except Exception:

        pass


# ==========================================================
# LIMPIAR ARCHIVOS DEL PROCESO ANTERIOR
# ==========================================================

def limpiar_proceso_anterior():

    global CONTROL_DIR_ACTUAL
    global RUTA_JSON_ACTUAL


    if RUTA_JSON_ACTUAL:

        eliminar_archivo(
            RUTA_JSON_ACTUAL
        )


    if CONTROL_DIR_ACTUAL:

        eliminar_carpeta(
            CONTROL_DIR_ACTUAL
        )


    CONTROL_DIR_ACTUAL = ""

    RUTA_JSON_ACTUAL = ""


# ==========================================================
# OBTENER URL DE REGISTRO
# ==========================================================

def obtener_url_registro(
    enlace_registro="",
    codigo_integracion=""
):

    # ======================================================
    # PRIMERA OPCIÓN:
    # URL enviada directamente desde DAVIS Web.
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
    # SEGUNDA OPCIÓN:
    # VARIABLE DE ENTORNO DE RAILWAY / .env
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
    #
    # Si el app.py anterior envía la URL en el parámetro
    # codigo_integracion, también podemos reconocerla.
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
# INICIAR REGISTRO
# ==========================================================

def preparar_registro(
    codigo_integracion="",
    personas=None,
    enlace_registro=""
):

    global PROCESO_REGISTRO
    global TOTAL_REGISTRO
    global PROCESO_DETENIDO
    global JOB_ID_ACTUAL
    global CONTROL_DIR_ACTUAL
    global RUTA_JSON_ACTUAL


    if personas is None:

        personas = []


    # ======================================================
    # BLOQUEO
    # ======================================================

    with PROCESO_LOCK:


        # ==================================================
        # EVITAR DOS REGISTROS SIMULTÁNEOS
        # ==================================================

        if PROCESO_REGISTRO is not None:

            if PROCESO_REGISTRO.poll() is None:

                return {

                    "ok":
                        False,

                    "mensaje":
                        "Ya existe un proceso de registro ejecutándose."

                }


        # ==================================================
        # VALIDAR PERSONAS
        # ==================================================

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


        # ==================================================
        # OBTENER URL
        # ==================================================

        url_registro = obtener_url_registro(

            enlace_registro=
                enlace_registro,

            codigo_integracion=
                codigo_integracion

        )


        if not url_registro:

            raise ValueError(
                "DAVIS no tiene configurada la URL del formulario de registro."
            )


        # ==================================================
        # REINICIAR ESTADO
        # ==================================================

        TOTAL_REGISTRO = len(
            personas
        )


        PROCESO_DETENIDO = False


        # ==================================================
        # LIMPIAR PROCESO ANTERIOR
        # ==================================================

        limpiar_proceso_anterior()


        # ==================================================
        # CREAR JOB ÚNICO
        # ==================================================

        JOB_ID_ACTUAL = uuid.uuid4().hex


        # ==================================================
        # JSON TEMPORAL
        # ==================================================

        RUTA_JSON_ACTUAL = os.path.join(

            CARPETA_TEMP,

            f"registro_{JOB_ID_ACTUAL}.json"

        )


        guardar_json_seguro(

            RUTA_JSON_ACTUAL,

            personas

        )


        # ==================================================
        # CARPETA DE CONTROL
        # ==================================================

        CONTROL_DIR_ACTUAL = os.path.join(

            CARPETA_TEMP,

            f"control_registro_{JOB_ID_ACTUAL}"

        )


        os.makedirs(
            CONTROL_DIR_ACTUAL,
            exist_ok=True
        )


        # ==================================================
        # RUTA registro.py
        # ==================================================

        ruta_script = os.path.join(
            BASE_DIR,
            "registro.py"
        )


        if not os.path.exists(
            ruta_script
        ):

            raise FileNotFoundError(
                "No se encontró registro.py en la carpeta principal de DAVIS."
            )


        # ==================================================
        # VARIABLES DE ENTORNO PARA registro.py
        # ==================================================

        env = os.environ.copy()


        env[
            "DAVIS_REGISTRO_URL"
        ] = url_registro


        env[
            "DAVIS_ARCHIVO_JSON"
        ] = RUTA_JSON_ACTUAL


        env[
            "DAVIS_REGISTRO_JOB_ID"
        ] = JOB_ID_ACTUAL


        env[
            "DAVIS_REGISTRO_CONTROL_DIR"
        ] = CONTROL_DIR_ACTUAL


        # ==================================================
        # UTF-8
        # ==================================================

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
        # LIMPIAR LOG
        # ==================================================

        with open(
            RUTA_LOG_REGISTRO,
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
                f"JOB: {JOB_ID_ACTUAL}\n"
            )

            archivo.write(
                f"Registros recibidos: {TOTAL_REGISTRO}\n"
            )

            archivo.write(
                "Preparando Playwright...\n"
            )


        # ==================================================
        # ABRIR LOG
        # ==================================================

        log = open(
            RUTA_LOG_REGISTRO,
            "a",
            encoding="utf-8"
        )


        # ==================================================
        # OPCIONES DEL PROCESO
        # ==================================================

        opciones_proceso = {}


        # ==================================================
        # WINDOWS
        # ==================================================

        if os.name == "nt":

            opciones_proceso[
                "creationflags"
            ] = subprocess.CREATE_NEW_PROCESS_GROUP


        # ==================================================
        # LINUX / RAILWAY
        # ==================================================

        else:

            opciones_proceso[
                "start_new_session"
            ] = True


        # ==================================================
        # EJECUTAR registro.py
        # ==================================================

        try:

            PROCESO_REGISTRO = subprocess.Popen(

                [
                    sys.executable,
                    ruta_script
                ],

                cwd=BASE_DIR,

                stdout=log,

                stderr=subprocess.STDOUT,

                env=env,

                **opciones_proceso

            )


        except Exception as error:

            log.close()


            raise RuntimeError(
                f"No se pudo iniciar registro.py: {error}"
            )


        # ==================================================
        # EL HIJO YA TIENE EL ARCHIVO DE LOG.
        # EL PADRE PUEDE CERRAR SU COPIA.
        # ==================================================

        try:

            log.close()

        except Exception:

            pass


        # ==================================================
        # RESPUESTA
        # ==================================================

        return {

            "ok":
                True,

            "mensaje":
                "Registro iniciado correctamente.",

            "total":
                TOTAL_REGISTRO,

            "job_id":
                JOB_ID_ACTUAL

        }


# ==========================================================
# LEER LOG
# ==========================================================

def leer_log_registro():

    if not os.path.exists(
        RUTA_LOG_REGISTRO
    ):

        return ""


    try:

        with open(
            RUTA_LOG_REGISTRO,
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
# CONTAR REGISTROS QUE REQUIRIERON REVISIÓN
#
# Evita contar dos veces a la misma persona si necesita
# más de una corrección.
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
                coincidencia.group(1)
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
# OBTENER ARCHIVO DE REVISIÓN
# ==========================================================

def ruta_revision_actual():

    if not CONTROL_DIR_ACTUAL:

        return ""


    return os.path.join(
        CONTROL_DIR_ACTUAL,
        "revision_pendiente.json"
    )


# ==========================================================
# OBTENER ARCHIVO DE CORRECCIÓN
# ==========================================================

def ruta_correccion_actual():

    if not CONTROL_DIR_ACTUAL:

        return ""


    return os.path.join(
        CONTROL_DIR_ACTUAL,
        "correccion.json"
    )


# ==========================================================
# LEER REVISIÓN PENDIENTE
# ==========================================================

def obtener_revision_pendiente():

    ruta = ruta_revision_actual()


    if not ruta:

        return None


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
# EXTRAER DOCUMENTO ACTUAL DEL LOG
# ==========================================================

def obtener_documento_actual(
    contenido
):

    # ======================================================
    # PRIORIDAD:
    # DOCUMENTO: XXXXX
    # ======================================================

    documentos = re.findall(

        r"^DOCUMENTO:\s*(.+)$",

        contenido,

        flags=re.MULTILINE
        |
        re.IGNORECASE

    )


    if documentos:

        return documentos[
            -1
        ].strip()


    # ======================================================
    # FALLBACK:
    # DUI: XXXXX
    # NIE: XXXXX
    # ======================================================

    documentos = re.findall(

        r"^(?:DUI|NIE):\s*(.+)$",

        contenido,

        flags=re.MULTILINE
        |
        re.IGNORECASE

    )


    if documentos:

        return documentos[
            -1
        ].strip()


    return ""


# ==========================================================
# OBTENER ESTADO DEL REGISTRO
# ==========================================================

def obtener_estado_registro():

    global PROCESO_REGISTRO
    global TOTAL_REGISTRO
    global PROCESO_DETENIDO


    contenido = leer_log_registro()


    # ======================================================
    # REVISIÓN PENDIENTE
    # ======================================================

    revision = obtener_revision_pendiente()


    # ======================================================
    # ESTADO GENERAL
    # ======================================================

    if PROCESO_DETENIDO:

        estado = "detenido"


    elif (
        revision is not None
        and
        PROCESO_REGISTRO is not None
        and
        PROCESO_REGISTRO.poll() is None
    ):

        estado = "requiere_revision"


    elif PROCESO_REGISTRO is None:

        estado = "listo"


    elif PROCESO_REGISTRO.poll() is None:

        estado = "ejecutando"


    elif PROCESO_REGISTRO.returncode == 0:

        estado = "finalizado"


    else:

        estado = "error"


    # ======================================================
    # REGISTRO ACTUAL
    #
    # REGISTRO 7 DE 50
    # ======================================================

    coincidencias = re.findall(

        r"REGISTRO\s+(\d+)\s+DE\s+(\d+)",

        contenido,

        flags=re.IGNORECASE

    )


    actual = 0

    total = TOTAL_REGISTRO


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
    # DOCUMENTO ACTUAL
    # ======================================================

    documento_actual = obtener_documento_actual(
        contenido
    )


    # ======================================================
    # BENEFICIARIOS CREADOS
    # ======================================================

    creados = contar_lineas(

        contenido,

        "✅ BENEFICIARIO CREADO CORRECTAMENTE"

    )


    # ======================================================
    # YA REGISTRADOS
    # ======================================================

    ya_registrados = contar_lineas(

        contenido,

        "⚠️ YA REGISTRADO"

    )


    # ======================================================
    # REVISIONES
    # ======================================================

    revisiones = contar_revisiones_unicas(
        contenido
    )


    # ======================================================
    # ERRORES
    # ======================================================

    errores_timeout = contar_lineas(

        contenido,

        "❌ ERROR DE TIEMPO DE ESPERA"

    )


    errores_generales = contar_lineas(

        contenido,

        "❌ ERROR EN EL REGISTRO"

    )


    errores = (
        errores_timeout
        +
        errores_generales
    )


    # ======================================================
    # RESUMEN FINAL
    #
    # Cuando el proceso termina usamos los contadores
    # oficiales impresos por registro.py.
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
    # DATOS DE LA REVISIÓN
    # ======================================================

    requiere_revision = (
        estado
        ==
        "requiere_revision"
    )


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

            documento_actual = (
                documento_revision
            )


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
    # RESPUESTA PARA DAVIS WEB
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
            documento_actual,

        "creados":
            creados,

        "ya_registrados":
            ya_registrados,

        "revisiones":
            revisiones,

        "errores":
            errores,

        "requiere_revision":
            requiere_revision,

        "motivo_revision":
            motivo_revision,

        "campos_faltantes":
            campos_faltantes,

        "persona_revision":
            persona_revision,

        "job_id":
            JOB_ID_ACTUAL,

        "log":
            ultimas_lineas

    }


# ==========================================================
# ENVIAR CORRECCIÓN DESDE DAVIS WEB
# ==========================================================

def enviar_correccion_registro(
    datos
):

    global PROCESO_REGISTRO


    # ======================================================
    # COMPROBAR PROCESO
    # ======================================================

    if PROCESO_REGISTRO is None:

        return {

            "ok":
                False,

            "mensaje":
                "No existe un proceso de registro activo."

        }


    if PROCESO_REGISTRO.poll() is not None:

        return {

            "ok":
                False,

            "mensaje":
                "El proceso de registro ya terminó."

        }


    # ======================================================
    # COMPROBAR REVISIÓN
    # ======================================================

    revision = obtener_revision_pendiente()


    if revision is None:

        return {

            "ok":
                False,

            "mensaje":
                "No existe ningún registro esperando corrección."

        }


    # ======================================================
    # VALIDAR DATOS
    # ======================================================

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


    # ======================================================
    # SI VIENEN DENTRO DE persona
    # ======================================================

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


    # ======================================================
    # SOLO CAMPOS PERMITIDOS
    # ======================================================

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


    # ======================================================
    # RUTA
    # ======================================================

    ruta = ruta_correccion_actual()


    if not ruta:

        return {

            "ok":
                False,

            "mensaje":
                "No se encontró la carpeta de control del registro."

        }


    # ======================================================
    # EVITAR DOBLE ENVÍO
    # ======================================================

    if os.path.exists(
        ruta
    ):

        return {

            "ok":
                False,

            "mensaje":
                "La corrección ya fue enviada. DAVIS está procesándola."

        }


    # ======================================================
    # GUARDAR CORRECCIÓN
    # ======================================================

    guardar_json_seguro(

        ruta,

        {
            "persona":
                correccion
        }

    )


    return {

        "ok":
            True,

        "mensaje":
            "Corrección enviada. DAVIS volverá a intentar este beneficiario."

    }


# ==========================================================
# DETENER PROCESO
# ==========================================================

def detener_registro():

    global PROCESO_REGISTRO
    global PROCESO_DETENIDO


    with PROCESO_LOCK:


        if PROCESO_REGISTRO is None:

            return False


        if PROCESO_REGISTRO.poll() is not None:

            return False


        try:

            # ==================================================
            # WINDOWS
            # Mata Python y Chromium del proceso.
            # ==================================================

            if os.name == "nt":

                subprocess.run(

                    [
                        "taskkill",
                        "/PID",
                        str(
                            PROCESO_REGISTRO.pid
                        ),
                        "/T",
                        "/F"
                    ],

                    stdout=subprocess.DEVNULL,

                    stderr=subprocess.DEVNULL,

                    check=False

                )


            # ==================================================
            # LINUX / RAILWAY
            # ==================================================

            else:

                try:

                    os.killpg(

                        os.getpgid(
                            PROCESO_REGISTRO.pid
                        ),

                        signal.SIGTERM

                    )


                except Exception:

                    PROCESO_REGISTRO.terminate()


            PROCESO_DETENIDO = True


            return True


        except Exception:

            return False