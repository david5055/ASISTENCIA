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

os.makedirs(CARPETA_TEMP, exist_ok=True)
os.makedirs(CARPETA_LOGS, exist_ok=True)


# ==========================================================
# MULTIUSUARIO
#
# ÚNICO CAMBIO DE ARQUITECTURA:
# - antes había un solo proceso global;
# - ahora cada dispositivo recibe un job_id propio;
# - cada job tiene su propio proceso, JSON y log;
# - máximo 5 procesos simultáneos.
#
# asistencia.py NO se modifica.
# ==========================================================

MAX_JOBS_ASISTENCIA = int(
    os.getenv(
        "DAVIS_MAX_ASISTENCIA_JOBS",
        "5"
    )
)

if MAX_JOBS_ASISTENCIA < 1:
    MAX_JOBS_ASISTENCIA = 1

JOBS_ASISTENCIA = {}
PROCESO_LOCK = threading.RLock()

ESTADOS_TERMINALES = {
    "finalizado",
    "error",
    "detenido",
}


# ==========================================================
# UTILIDADES
# ==========================================================

def guardar_json_seguro(ruta, datos):
    temporal = ruta + ".tmp"

    with open(
        temporal,
        "w",
        encoding="utf-8",
    ) as archivo:
        json.dump(
            datos,
            archivo,
            ensure_ascii=False,
            indent=4,
        )

    os.replace(temporal, ruta)


def eliminar_archivo(ruta):
    try:
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
    except Exception:
        pass


def leer_log_asistencia(job):
    ruta = str(
        job.get("log_path", "")
        or ""
    ).strip()

    if not ruta or not os.path.exists(ruta):
        return ""

    try:
        with open(
            ruta,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as archivo:
            return archivo.read()
    except Exception:
        return ""


def contar_lineas(contenido, prefijo):
    total = 0

    for linea in contenido.splitlines():
        if linea.strip().startswith(prefijo):
            total += 1

    return total


def buscar_ultimo_entero(contenido, patron):
    coincidencias = re.findall(
        patron,
        contenido,
        flags=re.IGNORECASE,
    )

    if not coincidencias:
        return None

    try:
        return int(coincidencias[-1])
    except Exception:
        return None


# ==========================================================
# MATAR PROCESO + PLAYWRIGHT + CHROMIUM
# ==========================================================

def matar_proceso(proceso):
    if proceso is None:
        return

    if proceso.poll() is not None:
        return

    if os.name == "nt":
        try:
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(proceso.pid),
                    "/T",
                    "/F",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
        except Exception:
            pass

        try:
            proceso.kill()
        except Exception:
            pass

    else:
        try:
            grupo = os.getpgid(proceso.pid)
            os.killpg(grupo, signal.SIGTERM)

            try:
                proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(grupo, signal.SIGKILL)

            return
        except Exception:
            pass

        try:
            proceso.terminate()
            proceso.wait(timeout=5)
        except Exception:
            try:
                proceso.kill()
            except Exception:
                pass


# ==========================================================
# ESTADO INTERNO DE UN JOB
# ==========================================================

def _actualizar_estado_job(job):
    estado = str(
        job.get("estado", "ejecutando")
        or "ejecutando"
    )

    if estado in ESTADOS_TERMINALES:
        return estado

    proceso = job.get("process")

    if proceso is None:
        job["estado"] = "error"
        return "error"

    codigo = proceso.poll()

    if codigo is None:
        job["estado"] = "ejecutando"
        return "ejecutando"

    if codigo == 0:
        job["estado"] = "finalizado"
    else:
        job["estado"] = "error"

    eliminar_archivo(
        job.get("json_path", "")
    )

    job["json_path"] = ""

    return job["estado"]


def _contar_jobs_activos():
    activos = 0

    # PROCESO_LOCK es RLock, por eso es seguro llamar
    # esta función desde preparar_asistencia.
    with PROCESO_LOCK:
        for job in JOBS_ASISTENCIA.values():
            estado = _actualizar_estado_job(job)

            if estado == "ejecutando":
                activos += 1

    return activos


def _obtener_job(job_id):
    identificador = str(
        job_id
        or ""
    ).strip()

    if not identificador:
        return None

    with PROCESO_LOCK:
        return JOBS_ASISTENCIA.get(
            identificador
        )


# ==========================================================
# PREPARAR ASISTENCIA
#
# La lógica de asistencia.py queda intacta.
# Solo se crea un proceso independiente por dispositivo.
# ==========================================================

def preparar_asistencia(
    enlace_asistencia,
    codigo_integracion,
    personas,
):
    enlace_asistencia = str(
        enlace_asistencia
        or ""
    ).strip()

    codigo_integracion = str(
        codigo_integracion
        or ""
    ).strip()

    if not enlace_asistencia:
        return {
            "ok": False,
            "mensaje": (
                "Debes ingresar el enlace "
                "de asistencia."
            ),
        }

    if not enlace_asistencia.startswith(
        (
            "http://",
            "https://",
        )
    ):
        return {
            "ok": False,
            "mensaje": (
                "El enlace de asistencia "
                "no es válido."
            ),
        }

    if not codigo_integracion:
        return {
            "ok": False,
            "mensaje": (
                "Debes ingresar el código "
                "de integración."
            ),
        }

    if not isinstance(personas, list):
        return {
            "ok": False,
            "mensaje": (
                "Los beneficiarios deben "
                "venir en una lista."
            ),
        }

    if not personas:
        return {
            "ok": False,
            "mensaje": (
                "No se recibieron beneficiarios."
            ),
        }

    personas_normalizadas = []

    for persona in personas:
        if not isinstance(persona, dict):
            continue

        persona_copia = dict(persona)

        persona_copia[
            "tipo_documento"
        ] = str(
            persona_copia.get(
                "tipo_documento",
                "NIE",
            )
            or "NIE"
        ).strip().upper()

        persona_copia[
            "documento"
        ] = str(
            persona_copia.get(
                "documento",
                "",
            )
            or ""
        ).strip()

        personas_normalizadas.append(
            persona_copia
        )

    if not personas_normalizadas:
        return {
            "ok": False,
            "mensaje": (
                "No se encontraron registros "
                "válidos para procesar."
            ),
        }

    with PROCESO_LOCK:
        activos = _contar_jobs_activos()

        if activos >= MAX_JOBS_ASISTENCIA:
            return {
                "ok": False,
                "mensaje": (
                    "DAVIS ya tiene "
                    f"{MAX_JOBS_ASISTENCIA} procesos "
                    "de asistencia activos. "
                    "Espera a que uno termine."
                ),
                "jobs_activos": activos,
                "max_jobs": MAX_JOBS_ASISTENCIA,
            }

        identificador = uuid.uuid4().hex

        ruta_json = os.path.join(
            CARPETA_TEMP,
            f"asistencia_{identificador}.json",
        )

        ruta_log = os.path.join(
            CARPETA_LOGS,
            f"asistencia_{identificador}.log",
        )

        guardar_json_seguro(
            ruta_json,
            personas_normalizadas,
        )

        # Mismo encabezado que antes, pero ahora cada job
        # escribe en SU PROPIO archivo de log.
        with open(
            ruta_log,
            "w",
            encoding="utf-8",
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
                f"Registros recibidos: "
                f"{len(personas_normalizadas)}\n"
            )
            archivo.write(
                "Preparando Playwright...\n"
            )

        ruta_script = os.path.join(
            BASE_DIR,
            "asistencia.py",
        )

        if not os.path.exists(ruta_script):
            eliminar_archivo(ruta_json)

            return {
                "ok": False,
                "mensaje": (
                    "No se encontró asistencia.py "
                    "en la carpeta principal de DAVIS."
                ),
            }

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

        opciones = {}

        if os.name == "nt":
            opciones[
                "creationflags"
            ] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            opciones[
                "start_new_session"
            ] = True

        log = open(
            ruta_log,
            "a",
            encoding="utf-8",
        )

        try:
            proceso = subprocess.Popen(
                [
                    sys.executable,
                    ruta_script,
                ],
                cwd=BASE_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                **opciones,
            )

            JOBS_ASISTENCIA[
                identificador
            ] = {
                "job_id": identificador,
                "process": proceso,
                "total": len(
                    personas_normalizadas
                ),
                "detenido": False,
                "estado": "ejecutando",
                "json_path": ruta_json,
                "log_path": ruta_log,
            }

        except Exception as error:
            eliminar_archivo(ruta_json)

            return {
                "ok": False,
                "mensaje": (
                    "No se pudo iniciar "
                    "asistencia.py: "
                    + str(error)
                ),
            }

        finally:
            try:
                log.close()
            except Exception:
                pass

    return {
        "ok": True,
        "mensaje": (
            "Asistencia iniciada correctamente."
        ),
        "total": len(
            personas_normalizadas
        ),
        "job_id": identificador,
        "jobs_activos": _contar_jobs_activos(),
        "max_jobs": MAX_JOBS_ASISTENCIA,
    }


# ==========================================================
# DOCUMENTO ACTUAL
# ==========================================================

def obtener_documento_actual(contenido):
    coincidencias = re.findall(
        r"^DOCUMENTO:\s*(.+)$",
        contenido,
        flags=(
            re.MULTILINE
            |
            re.IGNORECASE
        ),
    )

    if coincidencias:
        return coincidencias[-1].strip()

    coincidencias = re.findall(
        r"^(?:NIE|DUI):\s*(.+)$",
        contenido,
        flags=(
            re.MULTILINE
            |
            re.IGNORECASE
        ),
    )

    if coincidencias:
        return coincidencias[-1].strip()

    return ""


# ==========================================================
# TIPO DOCUMENTO ACTUAL
# ==========================================================

def obtener_tipo_documento_actual(contenido):
    tipos = re.findall(
        r"^TIPO_DOCUMENTO:\s*(NIE|DUI)\s*$",
        contenido,
        flags=(
            re.MULTILINE
            |
            re.IGNORECASE
        ),
    )

    if tipos:
        return tipos[-1].strip().upper()

    return ""


# ==========================================================
# ESTADO ASISTENCIA POR JOB
#
# Esta parte conserva los mismos contadores y el mismo
# análisis del log de tu service original.
# ==========================================================

def obtener_estado_asistencia(job_id=None):
    job = _obtener_job(job_id)

    if job is None:
        return {
            "estado": "listo",
            "actual": 0,
            "total": 0,
            "porcentaje": 0,
            "documento": "",
            "nie": "",
            "tipo_documento": "",
            "enviadas": 0,
            "ya_existentes": 0,
            "no_encontrados": 0,
            "omitidos": 0,
            "errores": 0,
            "log": [],
            "jobs_activos": _contar_jobs_activos(),
            "max_jobs": MAX_JOBS_ASISTENCIA,
        }

    with PROCESO_LOCK:
        estado = _actualizar_estado_job(job)
        total_job = int(
            job.get("total", 0)
            or 0
        )

    contenido = leer_log_asistencia(job)

    coincidencias = re.findall(
        r"ASISTENCIA\s+(\d+)\s+DE\s+(\d+)",
        contenido,
        flags=re.IGNORECASE,
    )

    actual = 0
    total = total_job

    if coincidencias:
        ultimo = coincidencias[-1]

        try:
            actual = int(ultimo[0])
            total = int(ultimo[1])
        except Exception:
            pass

    documento = obtener_documento_actual(
        contenido
    )

    tipo_documento = obtener_tipo_documento_actual(
        contenido
    )

    enviadas = contar_lineas(
        contenido,
        "✅ ASISTENCIA ENVIADA",
    )

    ya_existentes = contar_lineas(
        contenido,
        "⚠️ YA TENÍA REGISTRADA ASISTENCIA",
    )

    no_encontrados = (
        contar_lineas(
            contenido,
            "🔎 NIE NO ENCONTRADO",
        )
        +
        contar_lineas(
            contenido,
            "🔎 DUI NO ENCONTRADO",
        )
        +
        contar_lineas(
            contenido,
            "🔎 DOCUMENTO NO ENCONTRADO",
        )
    )

    omitidos = (
        contar_lineas(
            contenido,
            "⚠️ REGISTRO SIN DOCUMENTO",
        )
        +
        contar_lineas(
            contenido,
            "⚠️ TIPO DE DOCUMENTO INVÁLIDO",
        )
    )

    errores = (
        contar_lineas(
            contenido,
            "❌ ERROR DE TIEMPO DE ESPERA",
        )
        +
        contar_lineas(
            contenido,
            "❌ ERROR EN EL REGISTRO",
        )
        +
        contar_lineas(
            contenido,
            "❌ NO SE PUDO CONFIRMAR EL ENVÍO",
        )
    )

    resumen_enviadas = buscar_ultimo_entero(
        contenido,
        r"Asistencias enviadas:\s*(\d+)",
    )

    resumen_existentes = buscar_ultimo_entero(
        contenido,
        r"Ya ten[ií]an registrada asistencia:\s*(\d+)",
    )

    resumen_no_encontrados = buscar_ultimo_entero(
        contenido,
        r"Documentos no encontrados:\s*(\d+)",
    )

    resumen_omitidos = buscar_ultimo_entero(
        contenido,
        r"Omitidos:\s*(\d+)",
    )

    resumen_errores = buscar_ultimo_entero(
        contenido,
        r"Errores:\s*(\d+)",
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

    if estado == "finalizado":
        if total > 0:
            actual = total

    if total > 0:
        porcentaje = round(
            (actual / total)
            * 100
        )
    else:
        porcentaje = 0

    if estado == "finalizado":
        porcentaje = 100

    porcentaje = max(
        0,
        min(
            porcentaje,
            100,
        ),
    )

    lineas = [
        linea.strip()
        for linea
        in contenido.splitlines()
        if linea.strip()
    ]

    return {
        "estado": estado,
        "job_id": str(
            job.get("job_id", "")
            or ""
        ),
        "actual": actual,
        "total": total,
        "porcentaje": porcentaje,
        "documento": documento,
        # Alias para que tu progreso_asistencia.html original
        # siga funcionando sin modificarlo.
        "nie": documento,
        "tipo_documento": tipo_documento,
        "enviadas": enviadas,
        "ya_existentes": ya_existentes,
        "no_encontrados": no_encontrados,
        "omitidos": omitidos,
        "errores": errores,
        "jobs_activos": _contar_jobs_activos(),
        "max_jobs": MAX_JOBS_ASISTENCIA,
        "log": lineas[-30:],
    }


# ==========================================================
# DETENER ASISTENCIA POR JOB
# ==========================================================

def detener_asistencia(job_id=None):
    job = _obtener_job(job_id)

    if job is None:
        return False

    with PROCESO_LOCK:
        estado = _actualizar_estado_job(job)

        if estado != "ejecutando":
            return False

        proceso = job.get("process")
        job["detenido"] = True
        job["estado"] = "detenido"

    try:
        with open(
            job.get("log_path", ""),
            "a",
            encoding="utf-8",
        ) as archivo:
            archivo.write("\n")
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

    matar_proceso(proceso)

    eliminar_archivo(
        job.get("json_path", "")
    )

    job["json_path"] = ""

    return True
