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
#
# Aquí DAVIS y registro.py se comunicarán cuando
# una persona necesite corrección manual.
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
# VALOR SEGURO DEL JSON
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
# TEXTO DE LA PÁGINA
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

        "ya esta registrado",

        "ya esta registrada",

        "ya se encuentra registrado",

        "ya se encuentra registrada",

        "ya existe",

        "registrado previamente",

        "registrada previamente",

        "beneficiario ya registrado",

        "beneficiario ya se encuentra registrado",

        "documento ya registrado"

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# BENEFICIARIO CREADO CORRECTAMENTE
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
# CAMPOS REQUERIDOS DEL JSON
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
# ESCRIBIR JSON DE FORMA SEGURA
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
# SOLICITAR REVISIÓN DESDE DAVIS WEB
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
    # EVITAR CORRECCIÓN VIEJA
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
    # ESPERAR CORRECCIÓN
    #
    # NO usa input().
    #
    # Flask creará correccion.json cuando el usuario
    # presione "Guardar corrección y continuar".
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


                # ==========================================
                # PUEDE RECIBIR:
                #
                # {
                #   "persona": {...}
                # }
                #
                # o directamente:
                #
                # {
                #   "genero": "Masculino"
                # }
                # ==========================================

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


        # Revisa dos veces por segundo.
        time.sleep(
            0.5
        )


# ==========================================================
# EXTRAER MENSAJES DE VALIDACIÓN
# ==========================================================

def extraer_mensajes_validacion(
    page
):

    mensajes = []


    selectores = (

        '[role="alert"]',

        '.invalid-feedback',

        '.text-danger',

        '[class*="error"]',

        '[class*="invalid"]',

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


                    if (
                        texto
                        and
                        len(texto) <= 300
                        and
                        texto not in mensajes
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
            "input:invalid, textarea:invalid, select:invalid"
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
# ESPERAR RESULTADO AL VALIDAR DUI / NIE
# ==========================================================

def esperar_resultado_documento(
    page,
    timeout_ms=6000
):

    transcurrido = 0

    intervalo = 100


    while transcurrido < timeout_ms:

        texto = texto_de_pagina(
            page
        )


        # ==================================================
        # YA EXISTE
        # ==================================================

        if beneficiario_ya_registrado(
            texto
        ):

            return "ya_registrado"


        # ==================================================
        # FORMULARIO HABILITADO
        # ==================================================

        try:

            nombre = page.get_by_role(
                "textbox",
                name="* Nombre Completo"
            )


            if nombre.is_visible():

                return "formulario"


        except Exception:

            pass


        page.wait_for_timeout(
            intervalo
        )


        transcurrido += intervalo


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
    dato
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


        if campo.count() > 0:

            campo.fill(
                dato
            )


    except Exception:

        pass


# ==========================================================
# LLENAR FORMULARIO DEL BENEFICIARIO
# ==========================================================

def llenar_formulario(
    page,
    persona
):

    # ======================================================
    # NOMBRE
    # ======================================================

    page.get_by_role(
        "textbox",
        name="* Nombre Completo"
    ).fill(
        valor(
            persona,
            "nombre"
        )
    )


    # ======================================================
    # GÉNERO
    # ======================================================

    seleccionar_combobox(

        page,

        "* Género",

        valor(
            persona,
            "genero"
        )

    )


    # ======================================================
    # FECHA DE NACIMIENTO
    # ======================================================

    campo_fecha = page.get_by_role(
        "textbox",
        name="* Fecha de nacimiento"
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


    # ======================================================
    # TELÉFONO
    # ======================================================

    llenar_opcional(

        page,

        "Teléfono de Llamadas",

        valor(
            persona,
            "telefono"
        )

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
        )

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
        )

    )


    # ======================================================
    # DEPARTAMENTO
    # ======================================================

    seleccionar_combobox(

        page,

        "* Departamento dónde reside",

        valor(
            persona,
            "departamento"
        ),

        timeout=6000

    )


    # ======================================================
    # MUNICIPIO
    #
    # Ya no usamos wait_for_timeout(700).
    # Esperamos directamente a que aparezca la opción.
    # ======================================================

    seleccionar_combobox(

        page,

        "* Municipio dónde reside",

        valor(
            persona,
            "municipio"
        ),

        timeout=7000

    )


    # ======================================================
    # DISTRITO
    # ======================================================

    seleccionar_combobox(

        page,

        "* Distrito dónde reside",

        valor(
            persona,
            "distrito"
        ),

        timeout=7000

    )


    # ======================================================
    # RESIDENCIA
    # ======================================================

    page.get_by_role(
        "textbox",
        name="* Cantón/Caserío/Barrio/"
    ).fill(
        valor(
            persona,
            "residencia"
        )
    )


    # ======================================================
    # DIRECCIÓN
    # ======================================================

    page.get_by_role(
        "textbox",
        name="* Dirección de residencia"
    ).fill(
        valor(
            persona,
            "direccion"
        )
    )


    # ======================================================
    # INSTITUCIÓN OPCIONAL
    # ======================================================

    llenar_opcional(

        page,

        "Institución / Organización",

        valor(
            persona,
            "institucion"
        )

    )


    # ======================================================
    # CARGO OPCIONAL
    # ======================================================

    llenar_opcional(

        page,

        "Cargo",

        valor(
            persona,
            "cargo"
        )

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
    # ESTE WHILE GARANTIZA QUE DAVIS NO PASE AL
    # SIGUIENTE REGISTRO HASTA RESOLVER ESTE.
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
                    "Faltan datos necesarios "
                    "para validar al beneficiario."
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
        # COMPROBAR DATOS REQUERIDOS
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


            # Se reinicia desde un formulario limpio.
            continue


        # ==================================================
        # LLENAR FORMULARIO
        # ==================================================

        try:

            llenar_formulario(
                page,
                persona
            )


        except Exception as error:

            requirio_revision = True


            mensajes = extraer_mensajes_validacion(
                page
            )


            motivo = (
                "DAVIS no pudo completar uno "
                "de los campos del formulario."
            )


            if mensajes:

                motivo += (
                    " "
                    +
                    " | ".join(
                        mensajes[:5]
                    )
                )


            else:

                motivo += (
                    f" Detalle: {error}"
                )


            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=motivo,

                campos_faltantes=[]

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
        # ESPERAR RESULTADO REAL
        # ==================================================

        resultado_guardado = esperar_resultado_guardado(
            page,
            timeout_ms=5000
        )


        # ==================================================
        # CREADO CORRECTAMENTE
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
        # NO SE DETECTÓ ÉXITO
        #
        # NO ES ERROR.
        # NO PASAMOS AL SIGUIENTE.
        #
        # PAUSAMOS Y PEDIMOS CORRECCIÓN.
        # ==================================================

        mensajes = extraer_mensajes_validacion(
            page
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

            campos_faltantes=[]

        )


        # ==================================================
        # AL RECIBIR LA CORRECCIÓN NO PASAMOS
        # AL SIGUIENTE.
        #
        # VOLVEMOS ARRIBA Y REINTENTAMOS
        # ESTA MISMA PERSONA DESDE CERO.
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
        # LIMPIAR ARCHIVO DE REVISIÓN AL TERMINAR
        # ==================================================

        eliminar_archivo(
            ARCHIVO_REVISION
        )


        eliminar_archivo(
            ARCHIVO_CORRECCION
        )


        # ==================================================
        # CERRAR NAVEGADOR
        #
        # NO usamos input() porque Railway no tiene
        # una consola interactiva para el usuario.
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