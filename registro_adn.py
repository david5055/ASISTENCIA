import json
import os
import sys
import time
import unicodedata

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# ==========================================================
# UTF-8
# ==========================================================
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace",
        line_buffering=True,
    )

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace",
        line_buffering=True,
    )


# ==========================================================
# CONFIGURACIÓN
# ==========================================================
def _env_bool(nombre, valor_defecto=False):
    valor = os.getenv(nombre)

    if valor is None or not str(valor).strip():
        return valor_defecto

    return str(valor).strip().lower() in {
        "1",
        "true",
        "yes",
        "si",
        "sí",
        "on",
    }


URL = (
    os.getenv("DAVIS_REGISTRO_URL", "").strip()
    or os.getenv("REGISTRO_URL", "").strip()
)

ARCHIVO_JSON = os.getenv(
    "DAVIS_ARCHIVO_JSON",
    "",
).strip()

JOB_ID = (
    os.getenv(
        "DAVIS_REGISTRO_JOB_ID",
        "registro",
    ).strip()
    or "registro"
)


# ==========================================================
# RAILWAY / HEADLESS
# ==========================================================
EN_RAILWAY = bool(
    os.getenv("RAILWAY_ENVIRONMENT")
    or os.getenv("RAILWAY_PROJECT_ID")
    or os.getenv("RAILWAY_SERVICE_ID")
)

HEADLESS = _env_bool(
    "HEADLESS",
    EN_RAILWAY,
)


# ==========================================================
# DIRECTORIO DE CONTROL
# ==========================================================
CONTROL_DIR = os.getenv(
    "DAVIS_REGISTRO_CONTROL_DIR",
    "",
).strip()

if not CONTROL_DIR:

    if ARCHIVO_JSON:

        CONTROL_DIR = os.path.join(
            os.path.dirname(
                os.path.abspath(
                    ARCHIVO_JSON
                )
            ),
            f"control_{JOB_ID}",
        )

    else:

        CONTROL_DIR = os.path.join(
            os.getcwd(),
            "temp",
            f"control_{JOB_ID}",
        )


os.makedirs(
    CONTROL_DIR,
    exist_ok=True,
)


ARCHIVO_REVISION = os.path.join(
    CONTROL_DIR,
    "revision_pendiente.json",
)

ARCHIVO_CORRECCION = os.path.join(
    CONTROL_DIR,
    "correccion.json",
)

ARCHIVO_PROGRESO = os.path.join(
    CONTROL_DIR,
    "progreso.json",
)


# ==========================================================
# UTILIDADES
# ==========================================================
def normalizar_texto(texto):

    texto = str(
        texto or ""
    ).lower()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(
            caracter
        ) != "Mn"
    )

    return texto.strip()


def valor(persona, campo):

    dato = persona.get(
        campo,
        "",
    )

    if dato is None:
        return ""

    return str(
        dato
    ).strip()


def guardar_json(ruta, datos):

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

    os.replace(
        temporal,
        ruta,
    )


def eliminar_archivo(ruta):

    try:

        if ruta and os.path.exists(ruta):
            os.remove(ruta)

    except Exception:
        pass


def texto_de_pagina(page):

    try:

        texto = page.evaluate(
            "() => document.body ? document.body.innerText : ''"
        )

        return normalizar_texto(
            texto
        )

    except Exception:

        return ""


# ==========================================================
# PROGRESO
# ==========================================================
PROGRESO = {

    "job_id": JOB_ID,

    "estado": "iniciando",

    "actual": 0,

    "total": 0,

    "documento": "",

    "creados": 0,

    "ya_registrados": 0,

    "omitidos": 0,

    "revisiones": 0,

    "errores": 0,

    "requiere_revision": False,

    "mensaje": "",

    "actualizado_en": time.time(),
}


REVISIONES_CONTADAS = set()


def actualizar_progreso(**cambios):

    PROGRESO.update(
        cambios
    )

    PROGRESO["actualizado_en"] = (
        time.time()
    )

    try:

        guardar_json(
            ARCHIVO_PROGRESO,
            PROGRESO,
        )

    except Exception:

        pass


# ==========================================================
# MENSAJES DEL FORMULARIO
# ==========================================================
def beneficiario_ya_registrado(texto):

    texto = normalizar_texto(
        texto
    )

    mensajes = (

        "este dui ya se encuentra registrado",

        "el dui ya se encuentra registrado",

        "dui ya se encuentra registrado",

        "este dui ya esta registrado",

        "el dui ya esta registrado",

        "dui ya esta registrado",

        "este nie ya se encuentra registrado",

        "el nie ya se encuentra registrado",

        "nie ya se encuentra registrado",

        "este nie ya esta registrado",

        "el nie ya esta registrado",

        "nie ya esta registrado",

        "beneficiario ya se encuentra registrado",

        "beneficiario ya se encuentra registrada",

        "beneficiario ya registrado",

        "beneficiario ya registrada",

        "documento ya registrado",

        "documento ya se encuentra registrado",

        "registrado previamente",

        "registrada previamente",

        "ya existe un beneficiario",
    )

    return any(
        mensaje in texto
        for mensaje in mensajes
    )


def beneficiario_creado(texto):

    texto = normalizar_texto(
        texto
    )

    mensajes = (

        "beneficiario creado correctamente",

        "beneficiado creado correctamente",

        "beneficiario guardado correctamente",

        "beneficiario registrado correctamente",

        "beneficiario creado con exito",

        "beneficiario registrado con exito",
    )

    return any(
        mensaje in texto
        for mensaje in mensajes
    )


# ==========================================================
# ERRORES
# ==========================================================
class SaltarPersona(Exception):
    pass


class CampoRegistroError(Exception):

    def __init__(
        self,
        campo,
        detalle="",
    ):

        self.campo = campo

        self.detalle = str(
            detalle
        )

        super().__init__(
            f"{campo}: {detalle}"
        )


# ==========================================================
# CAMPOS OBLIGATORIOS
#
# IMPORTANTE:
# RESIDENCIA YA NO ES REQUERIDA.
# ==========================================================
def campos_requeridos_faltantes(persona):

    requeridos = {

        "tipo_documento":
            "Tipo de documento",

        "documento":
            "Documento",

        "nombre":
            "Nombre completo",

        "genero":
            "Género",

        "fecha_nacimiento":
            "Fecha de nacimiento",

        "departamento":
            "Departamento",

        "municipio":
            "Municipio",

        "distrito":
            "Distrito",

        "direccion":
            "Dirección",
    }

    return [

        nombre

        for campo, nombre
        in requeridos.items()

        if not valor(
            persona,
            campo,
        )
    ]


# ==========================================================
# REVISIÓN / CORRECCIÓN
# ==========================================================
def solicitar_revision(
    persona,
    numero,
    total,
    motivo,
    campos_faltantes=None,
):

    if campos_faltantes is None:

        campos_faltantes = []


    eliminar_archivo(
        ARCHIVO_CORRECCION
    )


    if numero not in REVISIONES_CONTADAS:

        REVISIONES_CONTADAS.add(
            numero
        )

        actualizar_progreso(
            revisiones=len(
                REVISIONES_CONTADAS
            )
        )


    datos_revision = {

        "estado":
            "requiere_revision",

        "job_id":
            JOB_ID,

        "numero":
            numero,

        "total":
            total,

        "documento":
            valor(
                persona,
                "documento",
            ),

        "tipo_documento":
            valor(
                persona,
                "tipo_documento",
            ),

        "motivo":
            motivo,

        "campos_faltantes":
            campos_faltantes,

        "persona":
            persona,
    }


    guardar_json(
        ARCHIVO_REVISION,
        datos_revision,
    )


    actualizar_progreso(

        estado="requiere_revision",

        actual=numero,

        total=total,

        documento=valor(
            persona,
            "documento",
        ),

        requiere_revision=True,

        mensaje=motivo,
    )


    print()

    print(
        "⏸️ REQUIERE REVISIÓN"
    )

    print(
        "DOCUMENTO:",
        valor(
            persona,
            "documento",
        ),
    )

    print(
        "MOTIVO:",
        motivo,
    )


    if campos_faltantes:

        print(
            "CAMPOS FALTANTES:",
            ", ".join(
                campos_faltantes
            ),
        )


    print(
        "DAVIS está esperando una corrección desde la página web."
    )


    while True:

        if os.path.exists(
            ARCHIVO_CORRECCION
        ):

            try:

                with open(
                    ARCHIVO_CORRECCION,
                    "r",
                    encoding="utf-8",
                ) as archivo:

                    correccion = json.load(
                        archivo
                    )


                if isinstance(
                    correccion,
                    dict,
                ):

                    accion = str(
                        correccion.get(
                            "accion",
                            "",
                        )
                        or ""
                    ).strip().lower()


                    # ==========================================
                    # SALTAR PERSONA
                    # ==========================================
                    if accion == "saltar":

                        eliminar_archivo(
                            ARCHIVO_CORRECCION
                        )

                        eliminar_archivo(
                            ARCHIVO_REVISION
                        )


                        actualizar_progreso(

                            estado="ejecutando",

                            requiere_revision=False,

                            mensaje=(
                                "Persona omitida manualmente. "
                                "Continuando con la siguiente."
                            ),
                        )


                        print()

                        print(
                            "⏭️ PERSONA OMITIDA MANUALMENTE"
                        )

                        print(
                            "DOCUMENTO:",
                            valor(
                                persona,
                                "documento",
                            ),
                        )

                        print(
                            "➡️ Pasando al siguiente registro..."
                        )


                        raise SaltarPersona()


                    cambios = correccion.get(
                        "persona",
                        correccion,
                    )


                    if isinstance(
                        cambios,
                        dict,
                    ):

                        persona_actualizada = dict(
                            persona
                        )

                        persona_actualizada.update(
                            cambios
                        )


                        eliminar_archivo(
                            ARCHIVO_CORRECCION
                        )

                        eliminar_archivo(
                            ARCHIVO_REVISION
                        )


                        actualizar_progreso(

                            estado="ejecutando",

                            requiere_revision=False,

                            mensaje=(
                                "Corrección recibida. "
                                "Reintentando registro."
                            ),
                        )


                        print()

                        print(
                            "▶️ CORRECCIÓN RECIBIDA"
                        )

                        print(
                            "DAVIS volverá a intentar este registro."
                        )


                        return persona_actualizada


            except SaltarPersona:

                raise


            except Exception as error:

                print(
                    "⚠️ No se pudo leer la corrección:",
                    error,
                )


        time.sleep(
            0.20
        )


# ==========================================================
# MENSAJES DE VALIDACIÓN
# ==========================================================
def extraer_mensajes_validacion(page):

    mensajes = []


    selectores = (

        '[role="alert"]',

        ".invalid-feedback",

        ".text-danger",

        '[aria-live="assertive"]',
    )


    for selector in selectores:

        try:

            elementos = page.locator(
                selector
            )

            cantidad = min(
                elementos.count(),
                20,
            )


            for i in range(
                cantidad
            ):

                elemento = elementos.nth(
                    i
                )

                try:

                    if not elemento.is_visible():
                        continue


                    texto = elemento.inner_text().strip()


                    if (
                        not texto
                        or len(texto) > 300
                    ):
                        continue


                    normalizado = normalizar_texto(
                        texto
                    )


                    if (
                        beneficiario_creado(
                            normalizado
                        )
                        or
                        beneficiario_ya_registrado(
                            normalizado
                        )
                    ):
                        continue


                    ignorar = (

                        "toggle theme",

                        "cambiar tema",

                        "navigation",

                        "menu",
                    )


                    if any(
                        palabra in normalizado
                        for palabra in ignorar
                    ):
                        continue


                    if texto not in mensajes:

                        mensajes.append(
                            texto
                        )


                except Exception:

                    pass


        except Exception:

            pass


    try:

        invalidos = page.locator(
            "input:invalid, "
            "textarea:invalid, "
            "select:invalid"
        )


        cantidad = min(
            invalidos.count(),
            20,
        )


        for i in range(
            cantidad
        ):

            campo = invalidos.nth(
                i
            )

            try:

                if not campo.is_visible():
                    continue


                nombre = (

                    campo.get_attribute(
                        "aria-label"
                    )

                    or

                    campo.get_attribute(
                        "placeholder"
                    )

                    or

                    campo.get_attribute(
                        "name"
                    )

                    or

                    "Campo requerido"
                )


                mensaje = (
                    f"Revisar: {nombre}"
                )


                if mensaje not in mensajes:

                    mensajes.append(
                        mensaje
                    )


            except Exception:

                pass


    except Exception:

        pass


    return mensajes


# ==========================================================
# IDENTIFICAR CAMPOS CON ERROR
# ==========================================================
def identificar_campos_error(mensajes):

    campos = []


    mapa = (

        (
            (
                "nombre completo",
                "nombre",
            ),
            "Nombre completo",
        ),

        (
            (
                "genero",
                "género",
            ),
            "Género",
        ),

        (
            (
                "fecha de nacimiento",
                "fecha nacimiento",
            ),
            "Fecha de nacimiento",
        ),

        (
            (
                "whatsapp",
            ),
            "WhatsApp",
        ),

        (
            (
                "telefono",
                "teléfono",
            ),
            "Teléfono",
        ),

        (
            (
                "correo",
                "email",
            ),
            "Correo",
        ),

        (
            (
                "departamento",
            ),
            "Departamento",
        ),

        (
            (
                "municipio",
            ),
            "Municipio",
        ),

        (
            (
                "distrito",
            ),
            "Distrito",
        ),

        (
            (
                "direccion",
                "dirección",
            ),
            "Dirección",
        ),

        (
            (
                "institucion",
                "institución",
            ),
            "Institución",
        ),

        (
            (
                "cargo",
            ),
            "Cargo",
        ),
    )


    for mensaje in mensajes:

        texto = normalizar_texto(
            mensaje
        )


        for palabras, nombre_campo in mapa:

            if any(
                normalizar_texto(
                    palabra
                ) in texto

                for palabra in palabras
            ):

                if nombre_campo not in campos:

                    campos.append(
                        nombre_campo
                    )


    return campos


# ==========================================================
# ESPERA VALIDACIÓN DUI / NIE
# ==========================================================
def esperar_resultado_documento(
    page,
    timeout_ms=5000,
):

    inicio = time.monotonic()

    timeout_s = (
        timeout_ms / 1000
    )


    nombre = page.get_by_role(
        "textbox",
        name="* Nombre Completo",
    )


    formulario_visible_desde = None

    ultima_revision_texto = 0.0


    while (
        time.monotonic()
        - inicio
    ) < timeout_s:

        ahora = time.monotonic()


        if (
            ahora
            - ultima_revision_texto
            >= 0.15
        ):

            if beneficiario_ya_registrado(
                texto_de_pagina(
                    page
                )
            ):

                return "ya_registrado"


            ultima_revision_texto = ahora


        try:

            formulario_disponible = (
                nombre.is_visible()
                and
                nombre.is_enabled()
            )

        except Exception:

            formulario_disponible = False


        if formulario_disponible:

            if formulario_visible_desde is None:

                formulario_visible_desde = ahora


            if (
                ahora
                - formulario_visible_desde
                >= 0.18
            ):

                if beneficiario_ya_registrado(
                    texto_de_pagina(
                        page
                    )
                ):

                    return "ya_registrado"


                return "formulario"


        else:

            formulario_visible_desde = None


        page.wait_for_timeout(
            40
        )


    if beneficiario_ya_registrado(
        texto_de_pagina(
            page
        )
    ):

        return "ya_registrado"


    try:

        if (
            nombre.is_visible()
            and
            nombre.is_enabled()
        ):

            return "formulario"

    except Exception:

        pass


    return "timeout"


# ==========================================================
# ABRIR FORMULARIO
# ==========================================================
def abrir_formulario_listo(
    page,
    tipo,
    intentos=3,
):

    nombre_campo = (
        "DUI"
        if tipo == "DUI"
        else "NIE"
    )


    ultimo_error = None


    for intento in range(
        1,
        intentos + 1,
    ):

        try:

            print(
                f"Abriendo formulario... "
                f"intento {intento} "
                f"de {intentos}"
            )


            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=20000,
            )


            campo_documento = (
                page.get_by_role(
                    "textbox",
                    name=nombre_campo,
                )
            )


            campo_documento.wait_for(
                state="visible",
                timeout=10000,
            )


            boton_validar = (
                page.get_by_role(
                    "button",
                    name="Validar",
                )
            )


            boton_validar.wait_for(
                state="visible",
                timeout=5000,
            )


            return campo_documento


        except Exception as error:

            ultimo_error = error


            print(
                "⚠️ El formulario todavía no está listo."
            )


            if intento < intentos:

                page.wait_for_timeout(
                    500
                )


    if ultimo_error is not None:

        raise ultimo_error


    raise RuntimeError(
        "No se pudo abrir el formulario de registro."
    )


# ==========================================================
# INGRESAR DOCUMENTO
# ==========================================================
def ingresar_documento_y_validar(
    page,
    tipo,
    documento,
    intentos=3,
):

    ultimo_error = None


    for intento in range(
        1,
        intentos + 1,
    ):

        try:

            campo_documento = (
                abrir_formulario_listo(
                    page,
                    tipo,
                    intentos=1,
                )
            )


            print(
                f"{tipo}: {documento}"
            )


            campo_documento.click()

            campo_documento.press(
                "Control+A"
            )

            campo_documento.press(
                "Backspace"
            )


            campo_documento.type(
                documento,
                delay=(
                    45
                    if intento == 1
                    else 70
                ),
            )


            campo_documento.press(
                "Tab"
            )


            boton_validar = (
                page.get_by_role(
                    "button",
                    name="Validar",
                )
            )


            boton_validar.wait_for(
                state="visible",
                timeout=5000,
            )


            inicio = time.monotonic()

            tiempo_maximo = 4.0


            while (
                time.monotonic()
                - inicio
            ) < tiempo_maximo:

                try:

                    if boton_validar.is_enabled():

                        boton_validar.click(
                            timeout=3000
                        )

                        print(
                            "Validando..."
                        )

                        return


                except PlaywrightTimeoutError:

                    pass


                page.wait_for_timeout(
                    100
                )


            raise RuntimeError(
                "El botón Validar permaneció "
                "deshabilitado después de "
                "ingresar el documento."
            )


        except Exception as error:

            ultimo_error = error


            print(
                "⚠️ El botón Validar todavía "
                "no está disponible. "
                f"Reintento {intento} "
                f"de {intentos}."
            )


            if intento < intentos:

                page.wait_for_timeout(
                    300
                )


    if ultimo_error is not None:

        raise ultimo_error


    raise RuntimeError(
        "No se pudo validar el documento."
    )


# ==========================================================
# SELECCIONAR COMBOBOX
# ==========================================================
def seleccionar_combobox(
    page,
    nombre,
    opcion,
    timeout=5000,
):

    opcion = str(
        opcion or ""
    ).strip()


    if not opcion:

        raise ValueError(
            f"No existe valor para: {nombre}"
        )


    combo = page.get_by_role(
        "combobox",
        name=nombre,
    )


    combo.wait_for(
        state="visible",
        timeout=timeout,
    )


    combo.click()


    try:

        opcion_role = (
            page.get_by_role(
                "option",
                name=opcion,
                exact=True,
            )
        )


        if opcion_role.count() > 0:

            opcion_role.last.wait_for(

                state="visible",

                timeout=min(
                    timeout,
                    2000,
                ),
            )


            opcion_role.last.click()

            return


    except Exception:

        pass


    opcion_texto = (
        page.get_by_text(
            opcion,
            exact=True,
        ).last
    )


    opcion_texto.wait_for(
        state="visible",
        timeout=timeout,
    )


    opcion_texto.click()


# ==========================================================
# LLENAR CAMPO OPCIONAL
# ==========================================================
def llenar_opcional(
    page,
    nombre,
    dato,
    nombre_error,
):

    dato = str(
        dato or ""
    ).strip()


    if not dato:
        return


    try:

        campo = page.get_by_role(
            "textbox",
            name=nombre,
        )


        campo.wait_for(
            state="visible",
            timeout=3500,
        )


        campo.fill(
            dato
        )


    except Exception as error:

        raise CampoRegistroError(
            nombre_error,
            error,
        ) from error


# ==========================================================
# LLENAR FORMULARIO
#
# FORMULARIO MAE ACTUAL:
#
# Nombre
# Género
# Fecha nacimiento
# Teléfono
# WhatsApp
# Correo
# Departamento
# Municipio
# Distrito
# Dirección
# Institución
# Cargo
#
# YA NO EXISTE:
# Cantón / Caserío / Barrio / Residencia
# ==========================================================
def llenar_formulario(
    page,
    persona,
):

    # ======================================================
    # NOMBRE
    # ======================================================
    try:

        page.get_by_role(
            "textbox",
            name="* Nombre Completo",
        ).fill(
            valor(
                persona,
                "nombre",
            )
        )

    except Exception as error:

        raise CampoRegistroError(
            "Nombre completo",
            error,
        ) from error


    # ======================================================
    # GÉNERO
    # ======================================================
    try:

        seleccionar_combobox(
            page,
            "* Género",
            valor(
                persona,
                "genero",
            ),
            timeout=5000,
        )

    except Exception as error:

        raise CampoRegistroError(
            "Género",
            error,
        ) from error


    # ======================================================
    # FECHA DE NACIMIENTO
    # ======================================================
    try:

        campo_fecha = page.get_by_role(
            "textbox",
            name="* Fecha de nacimiento",
        )


        campo_fecha.wait_for(
            state="visible",
            timeout=4000,
        )


        fecha = valor(
            persona,
            "fecha_nacimiento",
        )


        if not fecha:

            raise ValueError(
                "La fecha de nacimiento está vacía."
            )


        campo_fecha.click()

        campo_fecha.press(
            "Control+A"
        )

        campo_fecha.press(
            "Backspace"
        )


        campo_fecha.type(
            fecha,
            delay=60,
        )


        campo_fecha.press(
            "Enter"
        )

        campo_fecha.press(
            "Tab"
        )


        page.wait_for_timeout(
            150
        )


        valor_fecha = (
            campo_fecha
            .input_value()
            .strip()
        )


        if not valor_fecha:

            campo_fecha.click()

            campo_fecha.press(
                "Control+A"
            )

            campo_fecha.press(
                "Backspace"
            )


            campo_fecha.type(
                fecha,
                delay=90,
            )


            campo_fecha.press(
                "Tab"
            )


            page.wait_for_timeout(
                200
            )


            valor_fecha = (
                campo_fecha
                .input_value()
                .strip()
            )


        if not valor_fecha:

            raise ValueError(
                "El formulario no aceptó "
                "la fecha de nacimiento: "
                f"{fecha}"
            )


    except Exception as error:

        raise CampoRegistroError(
            "Fecha de nacimiento",
            error,
        ) from error


    # ======================================================
    # TELÉFONOS / CORREO
    # ======================================================
    llenar_opcional(
        page,
        "Teléfono de Llamadas",
        valor(
            persona,
            "telefono",
        ),
        "Teléfono",
    )


    llenar_opcional(
        page,
        "Teléfono de WhatsApp",
        valor(
            persona,
            "whatsapp",
        ),
        "WhatsApp",
    )


    llenar_opcional(
        page,
        "Correo Personal",
        valor(
            persona,
            "correo",
        ),
        "Correo",
    )


    # ======================================================
    # DEPARTAMENTO
    # ======================================================
    try:

        seleccionar_combobox(
            page,
            "* Departamento dónde reside",
            valor(
                persona,
                "departamento",
            ),
            timeout=6000,
        )

    except Exception as error:

        raise CampoRegistroError(
            "Departamento",
            error,
        ) from error


    # ======================================================
    # MUNICIPIO
    # ======================================================
    try:

        seleccionar_combobox(
            page,
            "* Municipio dónde reside",
            valor(
                persona,
                "municipio",
            ),
            timeout=6500,
        )

    except Exception as error:

        raise CampoRegistroError(
            "Municipio",
            error,
        ) from error


    # ======================================================
    # DISTRITO
    # ======================================================
    try:

        seleccionar_combobox(
            page,
            "* Distrito dónde reside",
            valor(
                persona,
                "distrito",
            ),
            timeout=6500,
        )

    except Exception as error:

        raise CampoRegistroError(
            "Distrito",
            error,
        ) from error


    # ======================================================
    # DIRECCIÓN DE RESIDENCIA
    #
    # AQUÍ YA NO SE LLENA RESIDENCIA/CANTÓN/CASERÍO/BARRIO.
    # ======================================================
    try:

        campo_direccion = page.get_by_role(
            "textbox",
            name="* Dirección de residencia",
        )


        campo_direccion.wait_for(
            state="visible",
            timeout=4000,
        )


        campo_direccion.fill(
            valor(
                persona,
                "direccion",
            )
        )


    except Exception as error:

        raise CampoRegistroError(
            "Dirección",
            error,
        ) from error


    # ======================================================
    # INSTITUCIÓN / ORGANIZACIÓN
    # ======================================================
    llenar_opcional(
        page,
        "Institución / Organización",
        valor(
            persona,
            "institucion",
        ),
        "Institución",
    )


    # ======================================================
    # CARGO
    # ======================================================
    llenar_opcional(
        page,
        "Cargo",
        valor(
            persona,
            "cargo",
        ),
        "Cargo",
    )


# ==========================================================
# ESPERA RESULTADO GUARDADO
# ==========================================================
def esperar_resultado_guardado(
    page,
    timeout_ms=4500,
):

    inicio = time.monotonic()

    timeout_s = (
        timeout_ms / 1000
    )


    siguiente_revision_errores = (
        inicio + 0.30
    )


    while (
        time.monotonic()
        - inicio
    ) < timeout_s:

        texto = texto_de_pagina(
            page
        )


        if beneficiario_creado(
            texto
        ):

            return "creado", []


        ahora = time.monotonic()


        if (
            ahora
            >= siguiente_revision_errores
        ):

            mensajes = (
                extraer_mensajes_validacion(
                    page
                )
            )


            if mensajes:

                return (
                    "revision",
                    mensajes,
                )


            siguiente_revision_errores = (
                ahora + 0.25
            )


        page.wait_for_timeout(
            80
        )


    texto = texto_de_pagina(
        page
    )


    if beneficiario_creado(
        texto
    ):

        return "creado", []


    return (
        "revision",
        extraer_mensajes_validacion(
            page
        ),
    )


# ==========================================================
# PROCESAR UNA PERSONA
# ==========================================================
def procesar_persona(
    page,
    persona_original,
    numero,
    total,
):

    persona = dict(
        persona_original
    )

    requirio_revision = False


    while True:

        tipo = valor(
            persona,
            "tipo_documento",
        ).upper()


        documento = valor(
            persona,
            "documento",
        )


        actualizar_progreso(

            estado="ejecutando",

            actual=numero,

            total=total,

            documento=documento,

            requiere_revision=False,

            mensaje="Validando documento.",
        )


        problemas_identidad = []


        if tipo not in (
            "DUI",
            "NIE",
        ):

            problemas_identidad.append(
                "Tipo de documento"
            )


        if not documento:

            problemas_identidad.append(
                "Documento"
            )


        if problemas_identidad:

            requirio_revision = True


            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=(
                    "Faltan datos necesarios "
                    "para validar al beneficiario."
                ),

                campos_faltantes=(
                    problemas_identidad
                ),
            )


            continue


        # ==================================================
        # VALIDAR DUI / NIE
        # ==================================================
        try:

            ingresar_documento_y_validar(

                page=page,

                tipo=tipo,

                documento=documento,

                intentos=3,
            )


        except Exception as error:

            requirio_revision = True


            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=(

                    "DAVIS ingresó el documento, "
                    "pero el botón Validar no logró "
                    "habilitarse después de 3 intentos. "

                    "DAVIS NO pasará automáticamente "
                    "a la siguiente persona. "

                    "Puedes usar Guardar corrección "
                    "y continuar para reintentar esta "
                    "misma persona, o Saltar persona "
                    "para omitirla manualmente. "

                    f"Detalle: {error}"
                ),

                campos_faltantes=[
                    "Documento"
                ],
            )


            continue


        resultado_documento = (
            esperar_resultado_documento(
                page,
                timeout_ms=5000,
            )
        )


        # ==================================================
        # YA REGISTRADO
        # ==================================================
        if (
            resultado_documento
            == "ya_registrado"
        ):

            print()

            print(
                "⚠️ YA REGISTRADO"
            )

            print(
                "DOCUMENTO:",
                documento,
            )

            print(
                "➡️ Pasando al siguiente registro..."
            )


            return (
                "ya_registrado",
                requirio_revision,
            )


        # ==================================================
        # FORMULARIO NO DISPONIBLE
        # ==================================================
        if (
            resultado_documento
            != "formulario"
        ):

            print()

            print(
                "⚠️ NO SE HABILITÓ EL FORMULARIO"
            )

            print(
                "DOCUMENTO:",
                documento,
            )

            print(
                "DAVIS mantendrá esta misma persona "
                "en revisión."
            )


            requirio_revision = True


            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=(

                    "Después de validar el documento "
                    "no se habilitó el formulario. "

                    "DAVIS no pasará automáticamente "
                    "a la siguiente persona. "

                    "Puedes reintentar con Guardar "
                    "corrección y continuar, o usar "
                    "Saltar persona."
                ),

                campos_faltantes=[],
            )


            continue


        print(
            "✅ Documento validado."
        )


        actualizar_progreso(
            mensaje=(
                "Documento validado. "
                "Completando formulario."
            )
        )


        # ==================================================
        # CAMPOS REQUERIDOS
        # ==================================================
        faltantes = (
            campos_requeridos_faltantes(
                persona
            )
        )


        if faltantes:

            requirio_revision = True


            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=(
                    "El registro tiene campos "
                    "requeridos sin información."
                ),

                campos_faltantes=(
                    faltantes
                ),
            )


            continue


        # ==================================================
        # LLENAR FORMULARIO
        # ==================================================
        try:

            llenar_formulario(
                page,
                persona,
            )


        except CampoRegistroError as error:

            requirio_revision = True


            print()

            print(
                "⚠️ ERROR EN CAMPO:"
            )

            print(
                error.campo
            )


            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=(
                    "DAVIS no pudo completar "
                    f"el campo: {error.campo}."
                ),

                campos_faltantes=[
                    error.campo
                ],
            )


            continue


        except Exception:

            requirio_revision = True


            mensajes = (
                extraer_mensajes_validacion(
                    page
                )
            )


            campos_error = (
                identificar_campos_error(
                    mensajes
                )
            )


            motivo = (
                "DAVIS no pudo completar "
                "correctamente el formulario."
            )


            if mensajes:

                motivo += (
                    " "
                    + " | ".join(
                        mensajes[:5]
                    )
                )


            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=motivo,

                campos_faltantes=(
                    campos_error
                ),
            )


            continue


        # ==================================================
        # GUARDAR
        # ==================================================
        print(
            "Guardando beneficiario..."
        )


        actualizar_progreso(
            mensaje="Guardando beneficiario."
        )


        boton_guardar = (
            page.get_by_role(
                "button",
                name="Guardar Beneficiario",
            )
        )


        boton_guardar.wait_for(
            state="visible",
            timeout=4000,
        )


        boton_guardar.click()


        resultado_guardado, mensajes = (
            esperar_resultado_guardado(
                page,
                timeout_ms=4500,
            )
        )


        # ==================================================
        # CREADO
        # ==================================================
        if (
            resultado_guardado
            == "creado"
        ):

            print()

            print(
                "✅ BENEFICIARIO CREADO CORRECTAMENTE"
            )

            print(
                "DOCUMENTO:",
                documento,
            )

            print(
                "➡️ Pasando al siguiente registro..."
            )


            return (
                "creado",
                requirio_revision,
            )


        # ==================================================
        # ERROR AL GUARDAR
        # ==================================================
        campos_error = (
            identificar_campos_error(
                mensajes
            )
        )


        if mensajes:

            motivo = (
                "No se pudo guardar "
                "el beneficiario. "
                + " | ".join(
                    mensajes[:8]
                )
            )

        else:

            motivo = (

                "No se detectó el mensaje "
                "'Beneficiario creado correctamente'. "

                "Revisa los datos del formulario."
            )


        requirio_revision = True


        persona = solicitar_revision(

            persona=persona,

            numero=numero,

            total=total,

            motivo=motivo,

            campos_faltantes=(
                campos_error
            ),
        )


# ==========================================================
# CARGAR JSON
# ==========================================================
def cargar_personas():

    if not URL:

        raise RuntimeError(
            "DAVIS no recibió la URL "
            "del formulario de registro."
        )


    if not ARCHIVO_JSON:

        raise RuntimeError(
            "DAVIS no recibió el archivo JSON."
        )


    if not os.path.exists(
        ARCHIVO_JSON
    ):

        raise FileNotFoundError(
            "No existe el archivo JSON: "
            f"{ARCHIVO_JSON}"
        )


    with open(
        ARCHIVO_JSON,
        "r",
        encoding="utf-8-sig",
    ) as archivo:

        datos = json.load(
            archivo
        )


    if (
        isinstance(
            datos,
            dict,
        )
        and
        isinstance(
            datos.get(
                "personas"
            ),
            list,
        )
    ):

        datos = datos[
            "personas"
        ]


    if not isinstance(
        datos,
        list,
    ):

        raise ValueError(
            "El JSON debe contener "
            "una lista de personas."
        )


    if not datos:

        raise ValueError(
            "No existen personas "
            "para registrar."
        )


    return datos


# ==========================================================
# MAIN
# ==========================================================
def main():

    personas = cargar_personas()

    total = len(
        personas
    )


    actualizar_progreso(

        estado="iniciando",

        actual=0,

        total=total,

        mensaje="Preparando navegador.",
    )


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

    print(
        "MÓDULO: REGISTRO"
    )

    print()

    print(
        "Registros recibidos:",
        total,
    )

    print(
        "Navegador oculto:",
        HEADLESS,
    )

    print(
        "JOB:",
        JOB_ID,
    )

    print(
        "======================================"
    )


    creados = 0

    ya_registrados = 0

    omitidos = 0

    errores = 0


    browser = None

    context = None


    try:

        with sync_playwright() as p:

            opciones_navegador = {
                "headless": HEADLESS
            }


            if os.name != "nt":

                opciones_navegador[
                    "args"
                ] = [

                    "--no-sandbox",

                    "--disable-dev-shm-usage",
                ]


            browser = (
                p.chromium.launch(
                    **opciones_navegador
                )
            )


            context = (
                browser.new_context()
            )


            page = (
                context.new_page()
            )


            page.set_default_timeout(
                8000
            )


            actualizar_progreso(

                estado="ejecutando",

                mensaje="Navegador listo.",
            )


            for numero, persona in enumerate(
                personas,
                start=1,
            ):

                print()

                print(
                    "======================================"
                )

                print(
                    f"REGISTRO {numero} DE {total}"
                )

                print(
                    "======================================"
                )


                documento_inicial = valor(
                    persona,
                    "documento",
                )


                print(
                    "DOCUMENTO:",
                    (
                        documento_inicial
                        if documento_inicial
                        else "VACÍO"
                    ),
                )


                actualizar_progreso(

                    estado="ejecutando",

                    actual=numero,

                    total=total,

                    documento=(
                        documento_inicial
                    ),

                    requiere_revision=False,

                    mensaje="Iniciando registro.",
                )


                try:

                    resultado, _ = (
                        procesar_persona(

                            page=page,

                            persona_original=persona,

                            numero=numero,

                            total=total,
                        )
                    )


                    if resultado == "creado":

                        creados += 1


                    elif (
                        resultado
                        == "ya_registrado"
                    ):

                        ya_registrados += 1


                    elif resultado == "error":

                        errores += 1


                except SaltarPersona:

                    omitidos += 1


                    actualizar_progreso(

                        omitidos=omitidos,

                        creados=creados,

                        ya_registrados=(
                            ya_registrados
                        ),

                        revisiones=len(
                            REVISIONES_CONTADAS
                        ),

                        errores=errores,

                        requiere_revision=False,

                        mensaje=(
                            "Persona omitida manualmente. "
                            "Continuando con la siguiente."
                        ),
                    )


                    continue


                except PlaywrightTimeoutError as error:

                    print()

                    print(
                        "❌ ERROR DE TIEMPO DE ESPERA"
                    )

                    print(
                        "DOCUMENTO:",
                        documento_inicial,
                    )

                    print(
                        "Error:",
                        error,
                    )


                    errores += 1


                except Exception as error:

                    print()

                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )

                    print(
                        "DOCUMENTO:",
                        documento_inicial,
                    )

                    print(
                        "Error:",
                        error,
                    )


                    errores += 1


                actualizar_progreso(

                    creados=creados,

                    ya_registrados=(
                        ya_registrados
                    ),

                    omitidos=omitidos,

                    revisiones=len(
                        REVISIONES_CONTADAS
                    ),

                    errores=errores,

                    requiere_revision=False,
                )


            # ==================================================
            # FINAL
            # ==================================================
            print()

            print()

            print(
                "======================================"
            )

            print(
                "          PROCESO FINALIZADO"
            )

            print(
                "======================================"
            )

            print(
                "Total revisados:",
                total,
            )

            print()

            print(
                "✅ Beneficiarios creados:",
                creados,
            )

            print(
                "⚠️ Ya registrados:",
                ya_registrados,
            )

            print(
                "⏭️ Omitidos manualmente:",
                omitidos,
            )

            print(
                "⏸️ Requirieron revisión:",
                len(
                    REVISIONES_CONTADAS
                ),
            )

            print(
                "❌ Errores:",
                errores,
            )

            print(
                "======================================"
            )


            actualizar_progreso(

                estado="finalizado",

                actual=total,

                total=total,

                creados=creados,

                ya_registrados=(
                    ya_registrados
                ),

                omitidos=omitidos,

                revisiones=len(
                    REVISIONES_CONTADAS
                ),

                errores=errores,

                requiere_revision=False,

                mensaje="Proceso finalizado.",
            )


    except Exception as error:

        actualizar_progreso(

            estado="error",

            errores=max(
                errores,
                PROGRESO.get(
                    "errores",
                    0,
                ),
            ),

            requiere_revision=False,

            mensaje=str(
                error
            ),
        )


        print()

        print(
            "❌ ERROR GENERAL DEL PROCESO"
        )

        print(
            error
        )


        raise


    finally:

        eliminar_archivo(
            ARCHIVO_REVISION
        )

        eliminar_archivo(
            ARCHIVO_CORRECCION
        )


        if context:

            try:

                context.close()

            except Exception:

                pass


        if browser:

            try:

                browser.close()

            except Exception:

                pass


# ==========================================================
# EJECUCIÓN
# ==========================================================
if __name__ == "__main__":

    main()