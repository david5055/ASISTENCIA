import os
import sys
import json
import time
import unicodedata

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError
)


# ==========================================================
# UTF-8
# ==========================================================

if hasattr(sys.stdout, "reconfigure"):

    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace",
        line_buffering=True
    )


if hasattr(sys.stderr, "reconfigure"):

    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace",
        line_buffering=True
    )


# ==========================================================
# CONFIGURACIÓN RECIBIDA DESDE DAVIS
# ==========================================================

URL = (

    os.getenv(
        "DAVIS_REGISTRO_URL",
        ""
    ).strip()

    or

    os.getenv(
        "REGISTRO_URL",
        ""
    ).strip()

)


ARCHIVO_JSON = os.getenv(
    "DAVIS_ARCHIVO_JSON",
    ""
).strip()


JOB_ID = os.getenv(
    "DAVIS_REGISTRO_JOB_ID",
    "registro"
).strip()


HEADLESS = os.getenv(
    "HEADLESS",
    "false"
).lower() == "true"


# ==========================================================
# CARPETA DE CONTROL
# ==========================================================

CONTROL_DIR = os.getenv(
    "DAVIS_REGISTRO_CONTROL_DIR",
    ""
).strip()


if not CONTROL_DIR:

    if ARCHIVO_JSON:

        CONTROL_DIR = os.path.join(

            os.path.dirname(
                os.path.abspath(
                    ARCHIVO_JSON
                )
            ),

            f"control_{JOB_ID}"

        )

    else:

        CONTROL_DIR = os.path.join(

            os.getcwd(),

            "temp",

            f"control_{JOB_ID}"

        )


os.makedirs(
    CONTROL_DIR,
    exist_ok=True
)


ARCHIVO_REVISION = os.path.join(
    CONTROL_DIR,
    "revision_pendiente.json"
)


ARCHIVO_CORRECCION = os.path.join(
    CONTROL_DIR,
    "correccion.json"
)


# ==========================================================
# VALIDAR CONFIGURACIÓN
# ==========================================================

if not URL:

    print(
        "❌ DAVIS no recibió la URL del formulario de registro."
    )

    sys.exit(1)


if not ARCHIVO_JSON:

    print(
        "❌ DAVIS no recibió el archivo JSON."
    )

    sys.exit(1)


if not os.path.exists(
    ARCHIVO_JSON
):

    print(
        "❌ No existe el archivo JSON:"
    )

    print(
        ARCHIVO_JSON
    )

    sys.exit(1)


# ==========================================================
# LEER JSON
# ==========================================================

try:

    with open(
        ARCHIVO_JSON,
        "r",
        encoding="utf-8"
    ) as archivo:

        personas = json.load(
            archivo
        )


except Exception as error:

    print()

    print(
        "❌ ERROR LEYENDO EL JSON"
    )

    print(
        error
    )

    sys.exit(1)


if not isinstance(
    personas,
    list
):

    print(
        "❌ El JSON debe contener una lista de personas."
    )

    sys.exit(1)


if len(personas) == 0:

    print(
        "❌ No existen personas para registrar."
    )

    sys.exit(1)


# ==========================================================
# INFORMACIÓN INICIAL
# ==========================================================

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
    len(personas)
)

print(
    "Navegador oculto:",
    HEADLESS
)

print(
    "JOB:",
    JOB_ID
)

print(
    "======================================"
)


# ==========================================================
# NORMALIZAR TEXTO
# ==========================================================

def normalizar_texto(
    texto
):

    texto = str(
        texto
    ).lower()


    texto = unicodedata.normalize(
        "NFD",
        texto
    )


    texto = "".join(

        caracter

        for caracter in texto

        if unicodedata.category(
            caracter
        ) != "Mn"

    )


    return texto.strip()


# ==========================================================
# ERROR DE CAMPO ESPECÍFICO
# ==========================================================

class CampoRegistroError(
    Exception
):

    def __init__(
        self,
        campo,
        detalle=""
    ):

        self.campo = campo

        self.detalle = str(
            detalle
        )

        super().__init__(

            f"{campo}: {detalle}"

        )


# ==========================================================
# VALOR SEGURO
# ==========================================================

def valor(
    persona,
    campo
):

    dato = persona.get(
        campo,
        ""
    )


    if dato is None:

        return ""


    return str(
        dato
    ).strip()


# ==========================================================
# TEXTO DE PÁGINA
# ==========================================================

def texto_de_pagina(
    page
):

    try:

        return normalizar_texto(

            page.locator(
                "body"
            ).inner_text()

        )


    except Exception:

        return ""


# ==========================================================
# BENEFICIARIO YA REGISTRADO
# ==========================================================

def beneficiario_ya_registrado(
    texto
):

    texto = normalizar_texto(
        texto
    )


    mensajes = (

        # ==================================================
        # DUI
        # ==================================================

        "este dui ya se encuentra registrado",

        "el dui ya se encuentra registrado",

        "dui ya se encuentra registrado",

        "este dui ya esta registrado",

        "el dui ya esta registrado",

        "dui ya esta registrado",


        # ==================================================
        # NIE
        # ==================================================

        "este nie ya se encuentra registrado",

        "el nie ya se encuentra registrado",

        "nie ya se encuentra registrado",

        "este nie ya esta registrado",

        "el nie ya esta registrado",

        "nie ya esta registrado",


        # ==================================================
        # GENERALES
        # ==================================================

        "beneficiario ya se encuentra registrado",

        "beneficiario ya se encuentra registrada",

        "beneficiario ya registrado",

        "beneficiario ya registrada",

        "documento ya registrado",

        "documento ya se encuentra registrado",

        "registrado previamente",

        "registrada previamente"

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# BENEFICIARIO CREADO
# ==========================================================

def beneficiario_creado(
    texto
):

    texto = normalizar_texto(
        texto
    )


    mensajes = (

        "beneficiario creado correctamente",

        "beneficiado creado correctamente",

        "beneficiario guardado correctamente",

        "beneficiario registrado correctamente",

        "beneficiario creado con exito",

        "beneficiario registrado con exito"

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# CAMPOS REQUERIDOS
# ==========================================================

def campos_requeridos_faltantes(
    persona
):

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

        "residencia":
            "Residencia",

        "direccion":
            "Dirección"

    }


    faltantes = []


    for campo, nombre in requeridos.items():

        if not valor(
            persona,
            campo
        ):

            faltantes.append(
                nombre
            )


    return faltantes


# ==========================================================
# GUARDAR JSON SEGURO
# ==========================================================

def guardar_json(
    ruta,
    datos
):

    ruta_temporal = (
        ruta
        +
        ".tmp"
    )


    with open(
        ruta_temporal,
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
        ruta_temporal,
        ruta
    )


# ==========================================================
# ELIMINAR ARCHIVO
# ==========================================================

def eliminar_archivo(
    ruta
):

    try:

        if os.path.exists(
            ruta
        ):

            os.remove(
                ruta
            )


    except Exception:

        pass


# ==========================================================
# SOLICITAR REVISIÓN
# ==========================================================

def solicitar_revision(
    persona,
    numero,
    total,
    motivo,
    campos_faltantes=None
):

    if campos_faltantes is None:

        campos_faltantes = []


    # ======================================================
    # ELIMINAR CORRECCIÓN ANTERIOR
    # ======================================================

    eliminar_archivo(
        ARCHIVO_CORRECCION
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
                "documento"
            ),

        "tipo_documento":
            valor(
                persona,
                "tipo_documento"
            ),

        "motivo":
            motivo,

        "campos_faltantes":
            campos_faltantes,

        "persona":
            persona

    }


    guardar_json(
        ARCHIVO_REVISION,
        datos_revision
    )


    print()

    print(
        "⏸️ REQUIERE REVISIÓN"
    )


    print(
        "DOCUMENTO:",
        valor(
            persona,
            "documento"
        )
    )


    print(
        "MOTIVO:",
        motivo
    )


    if campos_faltantes:

        print(
            "CAMPOS FALTANTES:",
            ", ".join(
                campos_faltantes
            )
        )


    print(
        "DAVIS está esperando una corrección desde la página web."
    )


    # ======================================================
    # ESPERAR CORRECCIÓN DESDE LA WEB
    # ======================================================

    while True:

        if os.path.exists(
            ARCHIVO_CORRECCION
        ):

            try:

                with open(
                    ARCHIVO_CORRECCION,
                    "r",
                    encoding="utf-8"
                ) as archivo:

                    correccion = json.load(
                        archivo
                    )


                if isinstance(
                    correccion,
                    dict
                ):

                    cambios = correccion.get(
                        "persona",
                        correccion
                    )


                    if isinstance(
                        cambios,
                        dict
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


                        print()

                        print(
                            "▶️ CORRECCIÓN RECIBIDA"
                        )


                        print(
                            "DAVIS volverá a intentar este registro."
                        )


                        return persona_actualizada


            except Exception as error:

                print(
                    "⚠️ No se pudo leer la corrección:",
                    error
                )


        time.sleep(
            0.5
        )


# ==========================================================
# EXTRAER MENSAJES REALES DE VALIDACIÓN
# ==========================================================

def extraer_mensajes_validacion(
    page
):

    mensajes = []


    # ======================================================
    # SOLO SELECTORES DE ERROR CONFIABLES
    #
    # Ya NO usamos:
    #
    # [class*="error"]
    # [class*="invalid"]
    #
    # porque podían detectar elementos como "Toggle theme".
    # ======================================================

    selectores = (

        '[role="alert"]',

        '.invalid-feedback',

        '.text-danger',

        '[aria-live="assertive"]'

    )


    for selector in selectores:

        try:

            elementos = page.locator(
                selector
            )


            cantidad = min(
                elementos.count(),
                20
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


                    if not texto:

                        continue


                    texto_normalizado = normalizar_texto(
                        texto
                    )


                    # ======================================
                    # IGNORAR COSAS QUE NO SON ERRORES
                    # ======================================

                    ignorar = (

                        "toggle theme",

                        "cambiar tema",

                        "menu",

                        "navigation"

                    )


                    if any(

                        palabra in texto_normalizado

                        for palabra in ignorar

                    ):

                        continue


                    if (
                        texto not in mensajes
                        and
                        len(texto) <= 300
                    ):

                        mensajes.append(
                            texto
                        )


                except Exception:

                    pass


        except Exception:

            pass


    # ======================================================
    # CAMPOS HTML INVÁLIDOS
    # ======================================================

    try:

        invalidos = page.locator(

            "input:invalid, "
            "textarea:invalid, "
            "select:invalid"

        )


        cantidad = min(
            invalidos.count(),
            20
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
# IDENTIFICAR QUÉ CAMPO DIO ERROR
# ==========================================================

def identificar_campos_error(
    mensajes
):

    campos = []


    mapa = (

        (
            (
                "nombre completo",
                "nombre"
            ),
            "Nombre completo"
        ),

        (
            (
                "genero",
                "género"
            ),
            "Género"
        ),

        (
            (
                "fecha de nacimiento",
                "fecha nacimiento"
            ),
            "Fecha de nacimiento"
        ),

        (
            (
                "whatsapp",
            ),
            "WhatsApp"
        ),

        (
            (
                "telefono",
                "teléfono"
            ),
            "Teléfono"
        ),

        (
            (
                "correo",
                "email"
            ),
            "Correo"
        ),

        (
            (
                "departamento",
            ),
            "Departamento"
        ),

        (
            (
                "municipio",
            ),
            "Municipio"
        ),

        (
            (
                "distrito",
            ),
            "Distrito"
        ),

        (
            (
                "canton",
                "cantón",
                "caserio",
                "caserío",
                "barrio",
                "residencia"
            ),
            "Residencia"
        ),

        (
            (
                "direccion",
                "dirección"
            ),
            "Dirección"
        ),

        (
            (
                "institucion",
                "institución"
            ),
            "Institución"
        ),

        (
            (
                "cargo",
            ),
            "Cargo"
        )

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
# ESPERAR RESULTADO AL VALIDAR DUI / NIE
# ==========================================================

def esperar_resultado_documento(
    page,
    timeout_ms=6000
):

    transcurrido = 0

    intervalo = 50

    formulario_detectado = 0


    while transcurrido < timeout_ms:

        texto = texto_de_pagina(
            page
        )


        # ==================================================
        # PRIORIDAD 1:
        # YA REGISTRADO
        # ==================================================

        if beneficiario_ya_registrado(
            texto
        ):

            return "ya_registrado"


        # ==================================================
        # PRIORIDAD 2:
        # FORMULARIO HABILITADO
        # ==================================================

        try:

            nombre = page.get_by_role(
                "textbox",
                name="* Nombre Completo"
            )


            visible = nombre.is_visible()

            habilitado = nombre.is_enabled()


            if (
                visible
                and
                habilitado
            ):

                formulario_detectado += (
                    intervalo
                )


                # ==========================================
                # Esperar unos milisegundos para evitar
                # que el formulario gane la carrera al
                # mensaje "ya registrado".
                # ==========================================

                if formulario_detectado >= 250:

                    texto_final = texto_de_pagina(
                        page
                    )


                    if beneficiario_ya_registrado(
                        texto_final
                    ):

                        return "ya_registrado"


                    return "formulario"


            else:

                formulario_detectado = 0


        except Exception:

            formulario_detectado = 0


        page.wait_for_timeout(
            intervalo
        )


        transcurrido += intervalo


    # ======================================================
    # ÚLTIMA COMPROBACIÓN
    # ======================================================

    texto = texto_de_pagina(
        page
    )


    if beneficiario_ya_registrado(
        texto
    ):

        return "ya_registrado"


    return "timeout"


# ==========================================================
# SELECCIONAR COMBOBOX
# ==========================================================

def seleccionar_combobox(
    page,
    nombre,
    opcion,
    timeout=5000
):

    opcion = str(
        opcion
    ).strip()


    if not opcion:

        raise ValueError(
            f"No existe valor para: {nombre}"
        )


    combo = page.get_by_role(
        "combobox",
        name=nombre
    )


    combo.wait_for(
        state="visible",
        timeout=timeout
    )


    combo.click()


    opcion_elemento = page.get_by_text(
        opcion,
        exact=True
    ).last


    opcion_elemento.wait_for(
        state="visible",
        timeout=timeout
    )


    opcion_elemento.click()


# ==========================================================
# LLENAR CAMPO OPCIONAL
# ==========================================================

def llenar_opcional(
    page,
    nombre,
    dato,
    nombre_error
):

    dato = str(
        dato or ""
    ).strip()


    if not dato:

        return


    try:

        campo = page.get_by_role(
            "textbox",
            name=nombre
        )


        campo.wait_for(
            state="visible",
            timeout=4000
        )


        campo.fill(
            dato
        )


    except Exception as error:

        raise CampoRegistroError(
            nombre_error,
            error
        )


# ==========================================================
# LLENAR FORMULARIO
# ==========================================================

def llenar_formulario(
    page,
    persona
):

    # ======================================================
    # NOMBRE
    # ======================================================

    try:

        page.get_by_role(
            "textbox",
            name="* Nombre Completo"
        ).fill(
            valor(
                persona,
                "nombre"
            )
        )


    except Exception as error:

        raise CampoRegistroError(
            "Nombre completo",
            error
        )


    # ======================================================
    # GÉNERO
    # ======================================================

    try:

        seleccionar_combobox(

            page,

            "* Género",

            valor(
                persona,
                "genero"
            )

        )


    except Exception as error:

        raise CampoRegistroError(
            "Género",
            error
        )


    # ======================================================
    # FECHA DE NACIMIENTO
    # ======================================================

    try:

        campo_fecha = page.get_by_role(
            "textbox",
            name="* Fecha de nacimiento"
        )


        campo_fecha.wait_for(
            state="visible",
            timeout=4000
        )


        campo_fecha.click()


        campo_fecha.press(
            "Control+A"
        )


        campo_fecha.press(
            "Backspace"
        )


        campo_fecha.type(

            valor(
                persona,
                "fecha_nacimiento"
            ),

            delay=35

        )


        campo_fecha.press(
            "Enter"
        )


    except Exception as error:

        raise CampoRegistroError(
            "Fecha de nacimiento",
            error
        )


    # ======================================================
    # TELÉFONO
    # ======================================================

    llenar_opcional(

        page,

        "Teléfono de Llamadas",

        valor(
            persona,
            "telefono"
        ),

        "Teléfono"

    )


    # ======================================================
    # WHATSAPP
    # ======================================================

    llenar_opcional(

        page,

        "Teléfono de WhatsApp",

        valor(
            persona,
            "whatsapp"
        ),

        "WhatsApp"

    )


    # ======================================================
    # CORREO
    # ======================================================

    llenar_opcional(

        page,

        "Correo Personal",

        valor(
            persona,
            "correo"
        ),

        "Correo"

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
                "departamento"
            ),

            timeout=6000

        )


    except Exception as error:

        raise CampoRegistroError(
            "Departamento",
            error
        )


    # ======================================================
    # MUNICIPIO
    # ======================================================

    try:

        seleccionar_combobox(

            page,

            "* Municipio dónde reside",

            valor(
                persona,
                "municipio"
            ),

            timeout=7000

        )


    except Exception as error:

        raise CampoRegistroError(
            "Municipio",
            error
        )


    # ======================================================
    # DISTRITO
    # ======================================================

    try:

        seleccionar_combobox(

            page,

            "* Distrito dónde reside",

            valor(
                persona,
                "distrito"
            ),

            timeout=7000

        )


    except Exception as error:

        raise CampoRegistroError(
            "Distrito",
            error
        )


    # ======================================================
    # RESIDENCIA
    # ======================================================

    try:

        page.get_by_role(
            "textbox",
            name="* Cantón/Caserío/Barrio/"
        ).fill(
            valor(
                persona,
                "residencia"
            )
        )


    except Exception as error:

        raise CampoRegistroError(
            "Residencia",
            error
        )


    # ======================================================
    # DIRECCIÓN
    # ======================================================

    try:

        page.get_by_role(
            "textbox",
            name="* Dirección de residencia"
        ).fill(
            valor(
                persona,
                "direccion"
            )
        )


    except Exception as error:

        raise CampoRegistroError(
            "Dirección",
            error
        )


    # ======================================================
    # INSTITUCIÓN
    # ======================================================

    llenar_opcional(

        page,

        "Institución / Organización",

        valor(
            persona,
            "institucion"
        ),

        "Institución"

    )


    # ======================================================
    # CARGO
    # ======================================================

    llenar_opcional(

        page,

        "Cargo",

        valor(
            persona,
            "cargo"
        ),

        "Cargo"

    )


# ==========================================================
# ESPERAR RESULTADO AL GUARDAR
# ==========================================================

def esperar_resultado_guardado(
    page,
    timeout_ms=5000
):

    transcurrido = 0

    intervalo = 100


    while transcurrido < timeout_ms:

        texto = texto_de_pagina(
            page
        )


        if beneficiario_creado(
            texto
        ):

            return "creado"


        page.wait_for_timeout(
            intervalo
        )


        transcurrido += intervalo


    return "revision"


# ==========================================================
# PROCESAR UNA PERSONA
# ==========================================================

def procesar_persona(
    page,
    persona_original,
    numero,
    total
):

    persona = dict(
        persona_original
    )


    requirio_revision = False


    # ======================================================
    # NO PASAR AL SIGUIENTE HASTA RESOLVER ESTE
    # ======================================================

    while True:

        tipo = valor(
            persona,
            "tipo_documento"
        ).upper()


        documento = valor(
            persona,
            "documento"
        )


        # ==================================================
        # VALIDAR IDENTIFICACIÓN
        # ==================================================

        problemas_identidad = []


        if tipo not in (
            "DUI",
            "NIE"
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
                    "Faltan datos necesarios para "
                    "validar al beneficiario."
                ),

                campos_faltantes=
                    problemas_identidad

            )


            continue


        # ==================================================
        # ABRIR FORMULARIO LIMPIO
        # ==================================================

        print(
            "Abriendo formulario..."
        )


        page.goto(
            URL,
            wait_until="domcontentloaded"
        )


        # ==================================================
        # DUI / NIE
        # ==================================================

        if tipo == "DUI":

            campo_documento = page.get_by_role(
                "textbox",
                name="DUI"
            )


        else:

            campo_documento = page.get_by_role(
                "textbox",
                name="NIE"
            )


        campo_documento.wait_for(
            state="visible",
            timeout=5000
        )


        campo_documento.fill(
            documento
        )


        print(
            f"{tipo}:",
            documento
        )


        # ==================================================
        # VALIDAR DOCUMENTO
        # ==================================================

        boton_validar = page.get_by_role(
            "button",
            name="Validar"
        )


        boton_validar.wait_for(
            state="visible",
            timeout=4000
        )


        boton_validar.click()


        print(
            "Validando..."
        )


        resultado_documento = esperar_resultado_documento(

            page,

            timeout_ms=6000

        )


        # ==================================================
        # YA REGISTRADO
        #
        # IMPORTANTE:
        # NO ABRE FORMULARIO DE CORRECCIÓN.
        # ==================================================

        if resultado_documento == "ya_registrado":

            print()

            print(
                "⚠️ YA REGISTRADO"
            )


            print(
                "DOCUMENTO:",
                documento
            )


            print(
                "➡️ Pasando al siguiente registro..."
            )


            return (
                "ya_registrado",
                requirio_revision
            )


        # ==================================================
        # FORMULARIO NO APARECIÓ
        # ==================================================

        if resultado_documento != "formulario":

            print()

            print(
                "❌ ERROR DE TIEMPO DE ESPERA"
            )


            print(
                "DOCUMENTO:",
                documento
            )


            print(
                "No se habilitó el formulario."
            )


            return (
                "error",
                requirio_revision
            )


        print(
            "✅ Documento validado."
        )


        # ==================================================
        # DATOS FALTANTES EN EL JSON
        # ==================================================

        faltantes = campos_requeridos_faltantes(
            persona
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

                campos_faltantes=faltantes

            )


            continue


        # ==================================================
        # LLENAR FORMULARIO
        # ==================================================

        try:

            llenar_formulario(
                page,
                persona
            )


        # ==================================================
        # ERROR EN UN CAMPO CONOCIDO
        # ==================================================

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
                ]

            )


            continue


        # ==================================================
        # ERROR NO IDENTIFICADO AL LLENAR
        # ==================================================

        except Exception as error:

            requirio_revision = True


            mensajes = extraer_mensajes_validacion(
                page
            )


            campos_error = identificar_campos_error(
                mensajes
            )


            motivo = (
                "DAVIS no pudo completar "
                "correctamente el formulario."
            )


            if mensajes:

                motivo += (

                    " "

                    +

                    " | ".join(
                        mensajes[:5]
                    )

                )


            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=motivo,

                campos_faltantes=
                    campos_error

            )


            continue


        # ==================================================
        # GUARDAR BENEFICIARIO
        # ==================================================

        print(
            "Guardando beneficiario..."
        )


        boton_guardar = page.get_by_role(
            "button",
            name="Guardar Beneficiario"
        )


        boton_guardar.wait_for(
            state="visible",
            timeout=4000
        )


        boton_guardar.click()


        # ==================================================
        # ESPERAR RESULTADO
        # ==================================================

        resultado_guardado = esperar_resultado_guardado(

            page,

            timeout_ms=5000

        )


        # ==================================================
        # CREADO
        # ==================================================

        if resultado_guardado == "creado":

            print()

            print(
                "✅ BENEFICIARIO CREADO CORRECTAMENTE"
            )


            print(
                "DOCUMENTO:",
                documento
            )


            print(
                "➡️ Pasando al siguiente registro..."
            )


            return (
                "creado",
                requirio_revision
            )


        # ==================================================
        # NO SE GUARDÓ
        #
        # AQUÍ SÍ ABRIMOS CORRECCIÓN.
        # ==================================================

        mensajes = extraer_mensajes_validacion(
            page
        )


        campos_error = identificar_campos_error(
            mensajes
        )


        if mensajes:

            motivo = (

                "No se pudo guardar el beneficiario. "

                +

                " | ".join(
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

            campos_faltantes=
                campos_error

        )


        # ==================================================
        # AL RECIBIR CORRECCIÓN
        # REINTENTAMOS ESTA MISMA PERSONA
        # ==================================================


# ==========================================================
# PLAYWRIGHT
# ==========================================================

with sync_playwright() as p:

    browser = None

    context = None


    try:

        browser = p.chromium.launch(
            headless=HEADLESS
        )


        context = browser.new_context()


        page = context.new_page()


        page.set_default_timeout(
            10000
        )


        # ==================================================
        # CONTADORES
        # ==================================================

        creados = 0

        ya_registrados = 0

        errores = 0

        revisiones = 0


        # ==================================================
        # RECORRER PERSONAS
        # ==================================================

        for numero, persona in enumerate(
            personas,
            start=1
        ):

            print()

            print(
                "======================================"
            )


            print(
                f"REGISTRO {numero} DE {len(personas)}"
            )


            print(
                "======================================"
            )


            documento_inicial = valor(
                persona,
                "documento"
            )


            print(
                "DOCUMENTO:",
                documento_inicial
                if documento_inicial
                else "VACÍO"
            )


            try:

                resultado, revisado = procesar_persona(

                    page=page,

                    persona_original=persona,

                    numero=numero,

                    total=len(
                        personas
                    )

                )


                if revisado:

                    revisiones += 1


                if resultado == "creado":

                    creados += 1


                elif resultado == "ya_registrado":

                    ya_registrados += 1


                elif resultado == "error":

                    errores += 1


            # ==================================================
            # TIMEOUT
            # ==================================================

            except PlaywrightTimeoutError as error:

                print()

                print(
                    "❌ ERROR DE TIEMPO DE ESPERA"
                )


                print(
                    "DOCUMENTO:",
                    documento_inicial
                )


                print(
                    "Error:",
                    error
                )


                errores += 1


                continue


            # ==================================================
            # ERROR GENERAL
            # ==================================================

            except Exception as error:

                print()

                print(
                    "❌ ERROR EN EL REGISTRO"
                )


                print(
                    "DOCUMENTO:",
                    documento_inicial
                )


                print(
                    "Error:",
                    error
                )


                errores += 1


                continue


        # ==================================================
        # RESULTADO FINAL
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
            len(personas)
        )


        print()


        print(
            "✅ Beneficiarios creados:",
            creados
        )


        print(
            "⚠️ Ya registrados:",
            ya_registrados
        )


        print(
            "⏸️ Requirieron revisión:",
            revisiones
        )


        print(
            "❌ Errores:",
            errores
        )


        print(
            "======================================"
        )


    finally:

        # ==================================================
        # LIMPIAR ARCHIVOS
        # ==================================================

        eliminar_archivo(
            ARCHIVO_REVISION
        )


        eliminar_archivo(
            ARCHIVO_CORRECCION
        )


        # ==================================================
        # CERRAR NAVEGADOR
        # ==================================================

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