import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid


# ==========================================================
# RUTAS
# Funciona si este archivo está en /services o en la raíz.
# ==========================================================
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(THIS_DIR).lower() in {"services", "service"}:
    BASE_DIR = os.path.dirname(THIS_DIR)
else:
    BASE_DIR = THIS_DIR

CARPETA_TEMP = os.path.join(BASE_DIR, "temp")
CARPETA_LOGS = os.path.join(BASE_DIR, "logs")

os.makedirs(CARPETA_TEMP, exist_ok=True)
os.makedirs(CARPETA_LOGS, exist_ok=True)


# ==========================================================
# CONFIGURACIÓN
# ==========================================================
def _env_int(nombre, defecto, minimo=None):
    try:
        valor = int(os.getenv(nombre, str(defecto)))
    except (TypeError, ValueError):
        valor = defecto

    if minimo is not None:
        valor = max(minimo, valor)
    return valor


MAX_JOBS = _env_int("DAVIS_MAX_JOBS", 5, 1)
ABANDON_TIMEOUT = _env_int("DAVIS_ABANDON_TIMEOUT", 180, 0)
MAX_JOB_SECONDS = _env_int("DAVIS_MAX_JOB_SECONDS", 3600, 0)
WATCHDOG_INTERVAL = _env_int("DAVIS_WATCHDOG_INTERVAL", 10, 2)
JOB_RETENTION_SECONDS = _env_int("DAVIS_JOB_RETENTION_SECONDS", 7200, 60)

ESTADOS_TERMINALES = {
    "finalizado",
    "error",
    "detenido",
    "cancelado_abandono",
    "cancelado_tiempo",
}

JOBS = {}
JOBS_LOCK = threading.RLock()
WATCHDOG_INICIADO = False

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
    "cargo",
)


# ==========================================================
# ARCHIVOS
# ==========================================================
def guardar_json_seguro(ruta, datos):
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=4)
    os.replace(temporal, ruta)


def leer_json_seguro(ruta):
    if not ruta or not os.path.exists(ruta):
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except Exception:
        return None


def eliminar_archivo(ruta):
    try:
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
    except Exception:
        pass


def eliminar_carpeta(ruta):
    try:
        if ruta and os.path.isdir(ruta):
            shutil.rmtree(ruta, ignore_errors=True)
    except Exception:
        pass


def escribir_log_job(job, mensaje):
    try:
        with open(job["log_path"], "a", encoding="utf-8") as archivo:
            archivo.write(str(mensaje) + "\n")
    except Exception:
        pass


def leer_log_job(job, max_bytes=131072):
    """Lee solo el final del log para que el endpoint de estado siga rápido."""
    ruta = job.get("log_path", "")
    if not ruta or not os.path.exists(ruta):
        return ""

    try:
        tamano = os.path.getsize(ruta)
        with open(ruta, "rb") as archivo:
            if max_bytes and tamano > max_bytes:
                archivo.seek(-max_bytes, os.SEEK_END)
                archivo.readline()  # descartar línea posiblemente cortada
            contenido = archivo.read()
        return contenido.decode("utf-8", errors="replace")
    except Exception:
        return ""


# ==========================================================
# RUTAS DE CONTROL DEL JOB
# ==========================================================
def ruta_revision_job(job):
    return os.path.join(job["control_dir"], "revision_pendiente.json")


def ruta_correccion_job(job):
    return os.path.join(job["control_dir"], "correccion.json")


def ruta_progreso_job(job):
    return os.path.join(job["control_dir"], "progreso.json")


def leer_revision_job(job):
    datos = leer_json_seguro(ruta_revision_job(job))
    return datos if isinstance(datos, dict) else None


def leer_progreso_job(job):
    datos = leer_json_seguro(ruta_progreso_job(job))
    if isinstance(datos, dict):
        job["ultimo_progreso"] = datos
        return datos
    ultimo = job.get("ultimo_progreso")
    return ultimo if isinstance(ultimo, dict) else None


# ==========================================================
# LIMPIAR DATOS DEL JOB
# ==========================================================
def limpiar_datos_job(job):
    if job.get("datos_limpiados", False):
        return

    # Guardamos el último progreso en RAM antes de borrar datos sensibles.
    try:
        progreso = leer_json_seguro(ruta_progreso_job(job))
        if isinstance(progreso, dict):
            job["ultimo_progreso"] = progreso
    except Exception:
        pass

    eliminar_archivo(job.get("json_path", ""))
    eliminar_carpeta(job.get("control_dir", ""))
    job["datos_limpiados"] = True


# ==========================================================
# FINALIZAR PROCESO + CHROMIUM
# ==========================================================
def matar_proceso_job(job):
    proceso = job.get("process")
    if proceso is None or proceso.poll() is not None:
        return

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proceso.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            try:
                proceso.kill()
            except Exception:
                pass
        return

    try:
        grupo = os.getpgid(proceso.pid)
        os.killpg(grupo, signal.SIGTERM)
        try:
            proceso.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(grupo, signal.SIGKILL)
    except Exception:
        try:
            proceso.terminate()
            proceso.wait(timeout=5)
        except Exception:
            try:
                proceso.kill()
            except Exception:
                pass


# ==========================================================
# ESTADO INTERNO
# ==========================================================
def refrescar_estado_job(job):
    estado_actual = job.get("estado", "ejecutando")
    if estado_actual in ESTADOS_TERMINALES:
        return estado_actual

    proceso = job.get("process")
    if proceso is None:
        job["estado"] = "error"
        job["finished_at"] = time.time()
        return "error"

    codigo = proceso.poll()

    if codigo is None:
        # La existencia del archivo de revisión manda sobre el progreso.
        if leer_revision_job(job) is not None:
            job["estado"] = "requiere_revision"
            return "requiere_revision"

        job["estado"] = "ejecutando"
        return "ejecutando"

    # Capturar progreso antes de borrar el control_dir.
    leer_progreso_job(job)

    job["estado"] = "finalizado" if codigo == 0 else "error"
    if not job.get("finished_at"):
        job["finished_at"] = time.time()

    limpiar_datos_job(job)
    return job["estado"]


def resolver_job_id(job_id=None):
    if job_id:
        return str(job_id).strip()

    with JOBS_LOCK:
        if len(JOBS) == 1:
            return next(iter(JOBS))
    return ""


def obtener_job(job_id=None):
    identificador = resolver_job_id(job_id)
    if not identificador:
        return None
    with JOBS_LOCK:
        return JOBS.get(identificador)


def contar_jobs_activos():
    activos = 0
    with JOBS_LOCK:
        for job in list(JOBS.values()):
            estado = refrescar_estado_job(job)
            if estado not in ESTADOS_TERMINALES:
                activos += 1
    return activos


# ==========================================================
# URL DE REGISTRO
# ==========================================================
def obtener_url_registro(enlace_registro="", codigo_integracion=""):
    url = str(enlace_registro or "").strip()
    if url.startswith(("http://", "https://")):
        return url

    # Primero DAVIS_REGISTRO_URL y luego REGISTRO_URL.
    for nombre in ("DAVIS_REGISTRO_URL", "REGISTRO_URL"):
        url = os.getenv(nombre, "").strip()
        if url.startswith(("http://", "https://")):
            return url

    posible_url = str(codigo_integracion or "").strip()
    if posible_url.startswith(("http://", "https://")):
        return posible_url

    return ""


# ==========================================================
# INICIAR UN REGISTRO
# ==========================================================
def preparar_registro(codigo_integracion="", personas=None, enlace_registro=""):
    if personas is None:
        personas = []

    if not isinstance(personas, list):
        raise ValueError("Los datos deben contener una lista de personas.")
    if not personas:
        raise ValueError("No se recibieron personas para registrar.")

    url_registro = obtener_url_registro(
        enlace_registro=enlace_registro,
        codigo_integracion=codigo_integracion,
    )
    if not url_registro:
        raise ValueError("DAVIS no tiene configurada la URL del formulario de registro.")

    with JOBS_LOCK:
        activos = contar_jobs_activos()
        if activos >= MAX_JOBS:
            return {
                "ok": False,
                "mensaje": (
                    "DAVIS está procesando el máximo "
                    f"de {MAX_JOBS} trabajos simultáneos. Espera a que uno finalice."
                ),
                "jobs_activos": activos,
                "max_jobs": MAX_JOBS,
            }

        job_id = uuid.uuid4().hex
        json_path = os.path.join(CARPETA_TEMP, f"registro_{job_id}.json")
        control_dir = os.path.join(CARPETA_TEMP, f"control_registro_{job_id}")
        log_path = os.path.join(CARPETA_LOGS, f"registro_{job_id}.log")
        os.makedirs(control_dir, exist_ok=True)

        guardar_json_seguro(json_path, personas)

        with open(log_path, "w", encoding="utf-8") as archivo:
            archivo.write("======================================\n")
            archivo.write("SISTEMA DAVIS - REGISTRO\n")
            archivo.write("======================================\n")
            archivo.write(f"JOB: {job_id}\n")
            archivo.write(f"Registros recibidos: {len(personas)}\n")
            archivo.write("Preparando Playwright...\n")

        # Búsqueda compatible con:
        #   proyecto/registro.py
        #   proyecto/services/registro_service.py
        ruta_script = os.path.join(BASE_DIR, "registro.py")
        if not os.path.exists(ruta_script):
            eliminar_archivo(json_path)
            eliminar_carpeta(control_dir)
            raise FileNotFoundError(
                f"No se encontró registro.py en la carpeta principal de DAVIS: {ruta_script}"
            )

        ahora = time.time()
        job = {
            "job_id": job_id,
            "process": None,
            "total": len(personas),
            "created_at": ahora,
            "started_at": ahora,
            "last_heartbeat": ahora,
            "finished_at": None,
            "estado": "iniciando",
            "motivo_cancelacion": "",
            "json_path": json_path,
            "control_dir": control_dir,
            "log_path": log_path,
            "datos_limpiados": False,
            "ultimo_progreso": {
                "actual": 0,
                "total": len(personas),
                "documento": "",
                "creados": 0,
                "ya_registrados": 0,
                "omitidos": 0,
                "revisiones": 0,
                "errores": 0,
                "estado": "iniciando",
                "mensaje": "Preparando Playwright.",
            },
        }
        JOBS[job_id] = job

        env = os.environ.copy()
        env["DAVIS_REGISTRO_URL"] = url_registro
        env["DAVIS_ARCHIVO_JSON"] = json_path
        env["DAVIS_REGISTRO_JOB_ID"] = job_id
        env["DAVIS_REGISTRO_CONTROL_DIR"] = control_dir
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"

        # Railway necesita navegador oculto. Si el usuario ya configuró HEADLESS,
        # respetamos su valor.
        if "HEADLESS" not in env and (
            env.get("RAILWAY_ENVIRONMENT")
            or env.get("RAILWAY_PROJECT_ID")
            or env.get("RAILWAY_SERVICE_ID")
        ):
            env["HEADLESS"] = "true"

        opciones = {}
        if os.name == "nt":
            opciones["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            opciones["start_new_session"] = True

        log = open(log_path, "a", encoding="utf-8")
        try:
            proceso = subprocess.Popen(
                [sys.executable, ruta_script],
                cwd=BASE_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                **opciones,
            )
            job["process"] = proceso
            job["estado"] = "ejecutando"
        except Exception as error:
            job["estado"] = "error"
            job["finished_at"] = time.time()
            limpiar_datos_job(job)
            raise RuntimeError(f"No se pudo iniciar registro.py: {error}") from error
        finally:
            try:
                log.close()
            except Exception:
                pass

    iniciar_watchdog()

    return {
        "ok": True,
        "mensaje": "Registro iniciado correctamente.",
        "total": len(personas),
        "job_id": job_id,
        "jobs_activos": contar_jobs_activos(),
        "max_jobs": MAX_JOBS,
    }


# ==========================================================
# REVISIÓN PENDIENTE
# ==========================================================
def obtener_revision_pendiente(job_id=None):
    job = obtener_job(job_id)
    if not job:
        return None
    return leer_revision_job(job)


# ==========================================================
# HEARTBEAT
# ==========================================================
def registrar_heartbeat(job_id):
    identificador = str(job_id or "").strip()
    if not identificador:
        return {"ok": False, "mensaje": "Falta job_id."}

    with JOBS_LOCK:
        job = JOBS.get(identificador)
        if not job:
            return {"ok": False, "mensaje": "El proceso ya no existe."}

        estado = refrescar_estado_job(job)
        if estado in ESTADOS_TERMINALES:
            return {
                "ok": False,
                "estado": estado,
                "mensaje": "El proceso ya terminó.",
            }

        job["last_heartbeat"] = time.time()
        return {"ok": True, "estado": estado, "job_id": identificador}


# ==========================================================
# FALLBACK DE ESTADO DESDE LOG
# ==========================================================
def contar_lineas(contenido, frase):
    return sum(
        1
        for linea in contenido.splitlines()
        if linea.strip().startswith(frase)
    )


def contar_revisiones_unicas(contenido):
    registros = set()
    registro_actual = None
    patron = re.compile(r"REGISTRO\s+(\d+)\s+DE\s+(\d+)", flags=re.IGNORECASE)

    for linea in contenido.splitlines():
        limpia = linea.strip()
        coincidencia = patron.search(limpia)
        if coincidencia:
            registro_actual = int(coincidencia.group(1))
        if limpia.startswith("⏸️ REQUIERE REVISIÓN") and registro_actual is not None:
            registros.add(registro_actual)

    return len(registros)


def obtener_documento_actual(contenido):
    documentos = re.findall(
        r"^DOCUMENTO:\s*(.+)$",
        contenido,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    if documentos:
        return documentos[-1].strip()

    documentos = re.findall(
        r"^(?:DUI|NIE):\s*(.+)$",
        contenido,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    return documentos[-1].strip() if documentos else ""


def _estado_fallback_log(contenido, total_job):
    coincidencias = re.findall(
        r"REGISTRO\s+(\d+)\s+DE\s+(\d+)", contenido, flags=re.IGNORECASE
    )

    actual = 0
    total = total_job
    if coincidencias:
        actual = int(coincidencias[-1][0])
        total = int(coincidencias[-1][1])

    creados = contar_lineas(contenido, "✅ BENEFICIARIO CREADO CORRECTAMENTE")
    ya_registrados = contar_lineas(contenido, "⚠️ YA REGISTRADO")
    omitidos = contar_lineas(contenido, "⏭️ PERSONA OMITIDA MANUALMENTE")
    revisiones = contar_revisiones_unicas(contenido)
    errores = (
        contar_lineas(contenido, "❌ ERROR DE TIEMPO DE ESPERA")
        + contar_lineas(contenido, "❌ ERROR EN EL REGISTRO")
    )

    return {
        "actual": actual,
        "total": total,
        "documento": obtener_documento_actual(contenido),
        "creados": creados,
        "ya_registrados": ya_registrados,
        "omitidos": omitidos,
        "revisiones": revisiones,
        "errores": errores,
        "mensaje": "",
    }


# ==========================================================
# ESTADO PÚBLICO DEL REGISTRO
# ==========================================================
def obtener_estado_registro(job_id=None):
    identificador = resolver_job_id(job_id)

    if not identificador:
        return {
            "estado": "no_encontrado",
            "job_id": "",
            "actual": 0,
            "total": 0,
            "porcentaje": 0,
            "documento": "",
            "creados": 0,
            "ya_registrados": 0,
            "omitidos": 0,
            "revisiones": 0,
            "errores": 0,
            "requiere_revision": False,
            "motivo_revision": "",
            "campos_faltantes": [],
            "persona_revision": None,
            "motivo_cancelacion": "",
            "mensaje_progreso": "",
            "jobs_activos": contar_jobs_activos(),
            "max_jobs": MAX_JOBS,
            "log": [],
        }

    with JOBS_LOCK:
        job = JOBS.get(identificador)
        if not job:
            return {
                "estado": "no_encontrado",
                "job_id": identificador,
                "mensaje": "Este proceso ya no existe.",
            }

        estado = refrescar_estado_job(job)
        total_job = job.get("total", 0)
        motivo_cancelacion = job.get("motivo_cancelacion", "")
        ultimo_heartbeat = job.get("last_heartbeat", time.time())
        iniciado = job.get("started_at", time.time())

        progreso = leer_progreso_job(job)

    # Solo las últimas líneas del log; evita releer megabytes en cada polling.
    contenido = leer_log_job(job)
    fallback = _estado_fallback_log(contenido, total_job)

    if isinstance(progreso, dict):
        actual = int(progreso.get("actual", fallback["actual"]) or 0)
        total = int(progreso.get("total", total_job) or total_job or 0)
        documento = str(progreso.get("documento", fallback["documento"]) or "").strip()
        creados = int(progreso.get("creados", fallback["creados"]) or 0)
        ya_registrados = int(progreso.get("ya_registrados", fallback["ya_registrados"]) or 0)
        omitidos = int(progreso.get("omitidos", fallback["omitidos"]) or 0)
        revisiones = int(progreso.get("revisiones", fallback["revisiones"]) or 0)
        errores = int(progreso.get("errores", fallback["errores"]) or 0)
        mensaje_progreso = str(progreso.get("mensaje", "") or "")
    else:
        actual = fallback["actual"]
        total = fallback["total"]
        documento = fallback["documento"]
        creados = fallback["creados"]
        ya_registrados = fallback["ya_registrados"]
        omitidos = fallback["omitidos"]
        revisiones = fallback["revisiones"]
        errores = fallback["errores"]
        mensaje_progreso = fallback["mensaje"]

    revision = leer_revision_job(job)
    persona_revision = None
    motivo_revision = ""
    campos_faltantes = []

    if isinstance(revision, dict):
        persona_revision = revision.get("persona")
        motivo_revision = str(revision.get("motivo", "") or "")
        campos_faltantes = revision.get("campos_faltantes", [])
        if not isinstance(campos_faltantes, list):
            campos_faltantes = []

        documento_revision = str(revision.get("documento", "") or "").strip()
        if documento_revision:
            documento = documento_revision

    requiere_revision = isinstance(revision, dict)
    if requiere_revision and estado not in ESTADOS_TERMINALES:
        estado = "requiere_revision"

    if total > 0:
        porcentaje = round((actual / total) * 100)
    else:
        porcentaje = 0

    if estado == "finalizado":
        porcentaje = 100
        if total > 0:
            actual = total

    porcentaje = max(0, min(porcentaje, 100))

    lineas = [linea.strip() for linea in contenido.splitlines() if linea.strip()]
    ultimas_lineas = lineas[-20:]

    ahora = time.time()
    segundos_sin_heartbeat = max(0, int(ahora - ultimo_heartbeat))
    segundos_ejecutando = max(0, int(ahora - iniciado))

    return {
        "estado": estado,
        "job_id": identificador,
        "actual": actual,
        "total": total,
        "porcentaje": porcentaje,
        "documento": documento,
        "creados": creados,
        "ya_registrados": ya_registrados,
        "omitidos": omitidos,
        "revisiones": revisiones,
        "errores": errores,
        "requiere_revision": requiere_revision,
        "motivo_revision": motivo_revision,
        "campos_faltantes": campos_faltantes,
        "persona_revision": persona_revision,
        "motivo_cancelacion": motivo_cancelacion,
        "mensaje_progreso": mensaje_progreso,
        "segundos_sin_heartbeat": segundos_sin_heartbeat,
        "segundos_ejecutando": segundos_ejecutando,
        "abandon_timeout": ABANDON_TIMEOUT,
        "max_job_seconds": MAX_JOB_SECONDS,
        "jobs_activos": contar_jobs_activos(),
        "max_jobs": MAX_JOBS,
        "log": ultimas_lineas,
    }


# ==========================================================
# ENVIAR CORRECCIÓN
# ==========================================================
def enviar_correccion_registro(datos, job_id=None):
    identificador = resolver_job_id(job_id)
    if not identificador:
        return {"ok": False, "mensaje": "No se encontró el proceso de registro."}

    with JOBS_LOCK:
        job = JOBS.get(identificador)
        if not job:
            return {"ok": False, "mensaje": "El proceso ya no existe."}

        estado = refrescar_estado_job(job)
        if estado in ESTADOS_TERMINALES:
            return {"ok": False, "mensaje": "El proceso de registro ya terminó."}

    revision = leer_revision_job(job)
    if revision is None:
        return {"ok": False, "mensaje": "No existe ningún registro esperando corrección."}

    revision_job_id = str(revision.get("job_id", "") or "").strip()
    if revision_job_id and revision_job_id != identificador:
        return {"ok": False, "mensaje": "La revisión no pertenece a este proceso."}

    if not isinstance(datos, dict):
        return {"ok": False, "mensaje": "Los datos de corrección no son válidos."}

    datos_persona = datos.get("persona", datos)
    if not isinstance(datos_persona, dict):
        return {
            "ok": False,
            "mensaje": "La corrección debe contener los datos de la persona.",
        }

    correccion = {}
    for campo in CAMPOS_PERSONA:
        if campo in datos_persona:
            dato = datos_persona.get(campo, "")
            if dato is None:
                dato = ""
            correccion[campo] = str(dato).strip()

    if not correccion:
        return {"ok": False, "mensaje": "No se recibió ningún campo para corregir."}

    ruta = ruta_correccion_job(job)
    if os.path.exists(ruta):
        return {
            "ok": False,
            "mensaje": "La corrección ya fue enviada. DAVIS está procesándola.",
        }

    guardar_json_seguro(ruta, {"persona": correccion})

    # La corrección cuenta como actividad del usuario.
    registrar_heartbeat(identificador)

    return {
        "ok": True,
        "job_id": identificador,
        "mensaje": "Corrección enviada. DAVIS volverá a intentar este beneficiario.",
    }


# ==========================================================
# SALTAR PERSONA EN REVISIÓN
# ==========================================================
def saltar_persona_registro(job_id=None):
    identificador = resolver_job_id(job_id)

    if not identificador:
        return {
            "ok": False,
            "mensaje": "No se encontró el proceso de registro.",
        }

    with JOBS_LOCK:
        job = JOBS.get(identificador)

        if not job:
            return {
                "ok": False,
                "mensaje": "El proceso ya no existe.",
            }

        estado = refrescar_estado_job(job)

        if estado in ESTADOS_TERMINALES:
            return {
                "ok": False,
                "mensaje": "El proceso de registro ya terminó.",
            }

    revision = leer_revision_job(job)

    if revision is None:
        return {
            "ok": False,
            "mensaje": "No existe ninguna persona esperando revisión.",
        }

    revision_job_id = str(
        revision.get("job_id", "")
        or ""
    ).strip()

    if revision_job_id and revision_job_id != identificador:
        return {
            "ok": False,
            "mensaje": "La revisión no pertenece a este proceso.",
        }

    ruta = ruta_correccion_job(job)

    if os.path.exists(ruta):
        return {
            "ok": False,
            "mensaje": (
                "DAVIS ya está procesando una acción para esta persona. "
                "Espera un momento."
            ),
        }

    guardar_json_seguro(
        ruta,
        {
            "accion": "saltar",
        },
    )

    registrar_heartbeat(identificador)

    return {
        "ok": True,
        "job_id": identificador,
        "mensaje": (
            "Persona omitida. DAVIS continuará con el siguiente registro."
        ),
    }


# ==========================================================
# CANCELAR / DETENER
# ==========================================================
def cancelar_job(job_id, estado, motivo):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return False

        estado_actual = refrescar_estado_job(job)
        if estado_actual in ESTADOS_TERMINALES:
            return False

        job["estado"] = estado
        job["motivo_cancelacion"] = motivo
        job["finished_at"] = time.time()

    escribir_log_job(job, "")
    escribir_log_job(job, "======================================")

    if estado == "cancelado_abandono":
        escribir_log_job(job, "⚠️ PROCESO CANCELADO AUTOMÁTICAMENTE POR INACTIVIDAD")
    elif estado == "cancelado_tiempo":
        escribir_log_job(job, "⏱️ PROCESO CANCELADO AUTOMÁTICAMENTE POR TIEMPO MÁXIMO")
    elif estado == "detenido":
        escribir_log_job(job, "■ PROCESO DETENIDO MANUALMENTE")

    escribir_log_job(job, f"MOTIVO: {motivo}")
    escribir_log_job(job, "======================================")

    matar_proceso_job(job)
    limpiar_datos_job(job)
    return True


def detener_registro(job_id=None):
    identificador = resolver_job_id(job_id)
    if not identificador:
        return False

    return cancelar_job(
        identificador,
        "detenido",
        "El usuario detuvo el proceso manualmente.",
    )


# ==========================================================
# WATCHDOG
# ==========================================================
def watchdog_loop():
    while True:
        try:
            ahora = time.time()
            cancelar_abandono = []
            cancelar_tiempo = []
            eliminar_jobs = []

            with JOBS_LOCK:
                for job_id, job in list(JOBS.items()):
                    estado = refrescar_estado_job(job)

                    if estado in ESTADOS_TERMINALES:
                        terminado = job.get("finished_at")
                        if terminado and (ahora - terminado) > JOB_RETENTION_SECONDS:
                            eliminar_jobs.append(job_id)
                        continue

                    inicio = job.get("started_at", ahora)
                    ultimo_heartbeat = job.get("last_heartbeat", inicio)

                    if MAX_JOB_SECONDS > 0 and (ahora - inicio) > MAX_JOB_SECONDS:
                        cancelar_tiempo.append(job_id)
                        continue

                    if ABANDON_TIMEOUT > 0 and (ahora - ultimo_heartbeat) > ABANDON_TIMEOUT:
                        cancelar_abandono.append(job_id)

            for job_id in cancelar_tiempo:
                cancelar_job(
                    job_id,
                    "cancelado_tiempo",
                    (
                        "El proceso superó el tiempo máximo permitido de "
                        f"{MAX_JOB_SECONDS} segundos."
                    ),
                )

            for job_id in cancelar_abandono:
                cancelar_job(
                    job_id,
                    "cancelado_abandono",
                    (
                        "DAVIS dejó de recibir señales del navegador durante más de "
                        f"{ABANDON_TIMEOUT} segundos."
                    ),
                )

            with JOBS_LOCK:
                for job_id in eliminar_jobs:
                    job = JOBS.get(job_id)
                    if not job:
                        continue
                    limpiar_datos_job(job)
                    eliminar_archivo(job.get("log_path", ""))
                    JOBS.pop(job_id, None)

        except Exception as error:
            print("ERROR WATCHDOG REGISTRO:", error)

        time.sleep(WATCHDOG_INTERVAL)


def iniciar_watchdog():
    global WATCHDOG_INICIADO

    with JOBS_LOCK:
        if WATCHDOG_INICIADO:
            return

        hilo = threading.Thread(
            target=watchdog_loop,
            name="DAVIS-Registro-Watchdog",
            daemon=True,
        )
        hilo.start()
        WATCHDOG_INICIADO = True


# ==========================================================
# INICIAR WATCHDOG AL IMPORTAR EL SERVICIO
# ==========================================================
iniciar_watchdog()
