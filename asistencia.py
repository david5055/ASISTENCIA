import os
import sys
import json
import re
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
# CONFIGURACIÓN DESDE DAVIS
# ==========================================================

URL = os.getenv("DAVIS_ASISTENCIA_URL", "").strip()

CODIGO_VERIFICACION = os.getenv(
    "DAVIS_CODIGO_INTEGRACION",
    ""
).strip()

ARCHIVO_JSON = os.getenv(
    "DAVIS_ARCHIVO_JSON",
    ""
).strip()

HEADLESS = os.getenv(
    "HEADLESS",
    "false"
).lower() == "true"


# ==========================================================
# VALIDACIONES INICIALES
# ==========================================================

if not URL:
    print(
        "❌ DAVIS no recibió el enlace de asistencia."
    )
    sys.exit(1)


if not CODIGO_VERIFICACION:
    print(
        "❌ DAVIS no recibió el código de integración."
    )
    sys.exit(1)


if (
    not ARCHIVO_JSON
    or
    not os.path.exists(
        ARCHIVO_JSON
    )
):
    print(
        "❌ DAVIS no recibió un archivo JSON válido."
    )
    sys.exit(1)


# ==========================================================
# LEER PERSONAS
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

    print(
        "❌ ERROR LEYENDO EL JSON"
    )

    print(
        error
    )

    sys.exit(1)


if (
    not isinstance(
        personas,
        list
    )
    or
    not personas
):

    print(
        "❌ El JSON debe contener una lista de personas."
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
    "MÓDULO: ASISTENCIA"
)

print(
    "Registros recibidos:",
    len(
        personas
    )
)

print(
    "Enlace recibido correctamente."
)

print(
    "Código recibido: ********"
)

print(
    "Navegador oculto:",
    HEADLESS
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

    texto = unicodedata.normalize(

        "NFD",

        str(
            texto
            or
            ""
        ).lower()

    )


    return "".join(

        caracter

        for caracter in texto

        if unicodedata.category(
            caracter
        ) != "Mn"

    )


# ==========================================================
# TEXTO DE FRAME
# ==========================================================

def texto_de_frame(
    frame
):

    try:

        return normalizar_texto(

            frame.locator(
                "body"
            ).inner_text(
                timeout=1200
            )

        )

    except Exception:

        return ""


# ==========================================================
# TEXTO DE TODA LA PÁGINA
# ==========================================================

def texto_de_pagina(
    page
):

    return "\n".join(

        texto_de_frame(
            frame
        )

        for frame in page.frames

    )


# ==========================================================
# PANTALLA PIDE CÓDIGO
# ==========================================================

def pagina_pide_codigo(
    texto
):

    texto = normalizar_texto(
        texto
    )


    mensajes = (

        "ya existe una asistencia registrada en este dispositivo",

        "ingresa el codigo de verificacion",

        "codigo de verificacion",

        "pidele el codigo a tu tecnico asignado",

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# ASISTENCIA YA REGISTRADA
# ==========================================================

def asistencia_ya_registrada(
    texto
):

    texto = normalizar_texto(
        texto
    )


    mensajes = (

        "el beneficiario ya tiene una asistencia registrada para esta jornada",

        "beneficiario ya tiene una asistencia registrada para esta jornada",

        "ya tiene una asistencia registrada para esta jornada",

        "asistencia registrada para esta jornada",

        "ya existe una asistencia registrada en esta actividad",

        "ya existe asistencia registrada en esta actividad",

        "asistencia ya registrada en esta actividad",

        "ya tiene una asistencia registrada en esta actividad",

        "ya se registro asistencia en esta actividad",

        "ya tiene una asistencia registrada",

        "asistencia ya registrada",

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# DOCUMENTO NO ENCONTRADO
# ==========================================================

def documento_no_encontrado(
    texto
):

    texto = normalizar_texto(
        texto
    )


    mensajes = (

        "beneficiario no encontrado",

        "documento no encontrado",

        "no existe el beneficiario",

        "no se encontro el beneficiario",

        "persona no encontrada",

        "nie no encontrado",

        "no se encontro el nie",

        "dui no encontrado",

        "no se encontro el dui",

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# DOCUMENTO INVÁLIDO
# ==========================================================

def documento_invalido(
    texto
):

    texto = normalizar_texto(
        texto
    )


    mensajes = (

        "documento invalido",

        "documento incorrecto",

        "nie invalido",

        "nie incorrecto",

        "dui invalido",

        "dui incorrecto",

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# ASISTENCIA EXITOSA
# ==========================================================

def asistencia_exitosa(
    texto
):

    texto = normalizar_texto(
        texto
    )


    mensajes = (

        "asistencia registrada correctamente",

        "asistencia guardada correctamente",

        "asistencia enviada correctamente",

        "asistencia registrada con exito",

        "asistencia guardada con exito",

        "registro de asistencia exitoso",

        "asistencia registrada exitosamente",

        "asistencia validada correctamente",

        "asistencia creada correctamente",

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# BUSCAR FRAME DEL FORMULARIO
# ==========================================================

def buscar_frame_formulario(
    page
):

    for frame in page.frames:

        texto = texto_de_frame(
            frame
        )


        # ==================================================
        # DETECCIÓN PRINCIPAL POR TEXTO
        # ==================================================

        if (

            "tipo de documento"
            in texto

            and

            (
                "valida tu asistencia"
                in texto

                or

                "verifica tu asistencia"
                in texto
            )

        ):

            return frame


        # ==================================================
        # COMBOBOX CON NOMBRE
        # ==================================================

        try:

            combo = frame.get_by_role(

                "combobox",

                name=re.compile(

                    r"tipo\s+de\s+documento",

                    re.IGNORECASE,

                ),

            ).first


            if (

                combo.count()

                and

                combo.is_visible()

            ):

                return frame

        except Exception:

            pass


        # ==================================================
        # COMBOBOX VISIBLE
        # ==================================================

        try:

            combos = frame.locator(

                '[role="combobox"]:visible'

            )


            for indice in range(
                combos.count()
            ):

                combo = combos.nth(
                    indice
                )


                contenido = normalizar_texto(

                    (
                        combo.inner_text(
                            timeout=500
                        )
                        or
                        ""
                    )

                    +

                    " "

                    +

                    (
                        combo.get_attribute(
                            "aria-label"
                        )
                        or
                        ""
                    )

                    +

                    " "

                    +

                    (
                        combo.get_attribute(
                            "placeholder"
                        )
                        or
                        ""
                    )

                )


                if (

                    "tipo de documento"
                    in contenido

                    or

                    "nie"
                    in contenido

                    or

                    "dui"
                    in contenido

                ):

                    return frame

        except Exception:

            pass


        # ==================================================
        # SELECT NATIVO
        # ==================================================

        try:

            selects = frame.locator(
                "select:visible"
            )


            for indice in range(
                selects.count()
            ):

                contenido = normalizar_texto(

                    selects.nth(
                        indice
                    ).inner_text(
                        timeout=500
                    )

                )


                if (

                    "nie"
                    in contenido

                    and

                    "dui"
                    in contenido

                ):

                    return frame

        except Exception:

            pass


    return None


# ==========================================================
# BUSCAR FRAME DEL CÓDIGO
# ==========================================================

def buscar_frame_codigo(
    page
):

    for frame in page.frames:


        if pagina_pide_codigo(

            texto_de_frame(
                frame
            )

        ):

            return frame


        # ==================================================
        # CAMPOS DE UN CARÁCTER
        # ==================================================

        try:

            campos = frame.locator(

                'input[maxlength="1"]:visible'

            )


            if (

                campos.count()

                >=

                min(
                    len(
                        CODIGO_VERIFICACION
                    ),
                    4
                )

            ):

                return frame

        except Exception:

            pass


        # ==================================================
        # BOTÓN VALIDAR CÓDIGO
        # ==================================================

        try:

            boton = frame.get_by_role(

                "button",

                name=re.compile(

                    r"validar\s*c[oó]digo",

                    re.IGNORECASE,

                ),

            ).first


            if (

                boton.count()

                and

                boton.is_visible()

            ):

                return frame

        except Exception:

            pass


    return None


# ==========================================================
# DIAGNÓSTICO
# ==========================================================

def imprimir_diagnostico(
    page
):

    print()

    print(
        "======================================"
    )

    print(
        "DIAGNÓSTICO DE LA PÁGINA"
    )

    print(
        "======================================"
    )


    try:

        print(
            "URL REAL:",
            page.url
        )

    except Exception:

        pass


    try:

        print(
            "TÍTULO:",
            page.title()
        )

    except Exception:

        pass


    print(

        "CANTIDAD DE FRAMES:",

        len(
            page.frames
        )

    )


    for indice, frame in enumerate(
        page.frames
    ):

        print()

        print(

            f"--- FRAME {indice} ---"

        )


        try:

            print(

                "URL FRAME:",

                frame.url

            )

        except Exception:

            pass


        try:

            texto = frame.locator(
                "body"
            ).inner_text(
                timeout=1500
            )


            print(

                texto[
                    :1800
                ]

            )

        except Exception as error:

            print(

                "No se pudo leer este frame:",

                error

            )


    print(
        "======================================"
    )


# ==========================================================
# ESPERAR FORMULARIO O CÓDIGO
# ==========================================================

def esperar_estado_formulario(

    page,

    timeout_ms=15000

):

    transcurrido = 0


    while transcurrido < timeout_ms:


        # ==================================================
        # FORMULARIO
        # ==================================================

        frame_formulario = buscar_frame_formulario(
            page
        )


        if frame_formulario is not None:

            return (
                "formulario",
                frame_formulario
            )


        # ==================================================
        # CÓDIGO
        # ==================================================

        frame_codigo = buscar_frame_codigo(
            page
        )


        if frame_codigo is not None:

            return (
                "codigo",
                frame_codigo
            )


        page.wait_for_timeout(
            150
        )


        transcurrido += 150


    imprimir_diagnostico(
        page
    )


    return (
        "timeout",
        None
    )


# ==========================================================
# INGRESAR CÓDIGO
# ==========================================================

def ingresar_codigo_en_frame(

    page,

    frame

):

    print()

    print(
        "======================================"
    )

    print(
        "🔐 DESBLOQUEO DEL FORMULARIO"
    )

    print(
        "======================================"
    )

    print(
        "Código recibido desde DAVIS: ********"
    )


    campos = frame.locator(

        'input[maxlength="1"]:visible'

    )


    try:

        campos.first.wait_for(

            state="visible",

            timeout=3000

        )

    except Exception:

        pass


    cantidad = campos.count()


    print(

        "Campos encontrados:",

        cantidad

    )


    # ======================================================
    # MÉTODO PRINCIPAL
    # ======================================================

    if cantidad >= len(
        CODIGO_VERIFICACION
    ):

        for indice, caracter in enumerate(
            CODIGO_VERIFICACION
        ):

            campo = campos.nth(
                indice
            )


            campo.click()


            campo.fill(
                caracter
            )


    # ======================================================
    # MÉTODO ALTERNATIVO
    # ======================================================

    else:

        inputs = frame.locator(
            "input:visible"
        )


        candidatos = []


        for indice in range(
            inputs.count()
        ):

            campo = inputs.nth(
                indice
            )


            try:

                caja = campo.bounding_box()


                if (

                    caja

                    and

                    caja[
                        "width"
                    ] <= 100

                ):

                    candidatos.append(
                        campo
                    )

            except Exception:

                pass


        if len(
            candidatos
        ) < len(
            CODIGO_VERIFICACION
        ):

            print(

                "❌ No se encontraron suficientes "
                "campos para el código."

            )


            return False


        for indice, caracter in enumerate(
            CODIGO_VERIFICACION
        ):

            candidatos[
                indice
            ].click()


            candidatos[
                indice
            ].fill(
                caracter
            )


    print(
        "✅ Código ingresado."
    )


    # ======================================================
    # BOTÓN VALIDAR CÓDIGO
    # ======================================================

    boton_codigo = None


    try:

        boton_codigo = frame.get_by_role(

            "button",

            name=re.compile(

                r"validar\s*c[oó]digo",

                re.IGNORECASE,

            ),

        ).first


        boton_codigo.wait_for(

            state="visible",

            timeout=4000

        )

    except Exception:

        try:

            boton_codigo = frame.locator(

                "button:visible"

            ).filter(

                has_text=re.compile(

                    r"validar\s*c[oó]digo",

                    re.IGNORECASE,

                )

            ).first


            boton_codigo.wait_for(

                state="visible",

                timeout=3000

            )

        except Exception:

            print(

                "❌ No se encontró el botón "
                "Validar código."

            )


            return False


    # ======================================================
    # ESPERAR BOTÓN HABILITADO
    # ======================================================

    habilitado = False


    for _ in range(
        50
    ):

        try:

            if boton_codigo.is_enabled():

                habilitado = True


                break

        except Exception:

            pass


        page.wait_for_timeout(
            100
        )


    if not habilitado:

        print(

            "❌ El botón Validar código "
            "no se habilitó."

        )


        return False


    print(
        "🔓 Validando código..."
    )


    boton_codigo.click()


    return True


# ==========================================================
# DESBLOQUEAR FORMULARIO
# ==========================================================

def desbloquear_formulario(
    page
):

    estado, frame = esperar_estado_formulario(

        page,

        timeout_ms=12000

    )


    # ======================================================
    # FORMULARIO YA DISPONIBLE
    # ======================================================

    if estado == "formulario":

        print(
            "✅ Formulario de asistencia detectado."
        )


        return frame


    # ======================================================
    # TIMEOUT
    # ======================================================

    if estado == "timeout":

        print(

            "❌ No apareció el formulario "
            "ni la pantalla del código."

        )


        return None


    # ======================================================
    # PANTALLA DE CÓDIGO
    # ======================================================

    try:

        if not ingresar_codigo_en_frame(

            page,

            frame

        ):

            return None


        # ==================================================
        # PRIMERO ESPERAR SI EL PORTAL CAMBIA SOLO AL
        # FORMULARIO DESPUÉS DE VALIDAR EL CÓDIGO
        # ==================================================

        transcurrido = 0


        while transcurrido < 7000:

            texto = texto_de_pagina(
                page
            )


            # ==============================================
            # CÓDIGO INCORRECTO
            # ==============================================

            if (

                "codigo incorrecto"
                in texto

                or

                "codigo invalido"
                in texto

                or

                "codigo no valido"
                in texto

            ):

                print(
                    "❌ Código de integración incorrecto."
                )


                return None


            # ==============================================
            # FORMULARIO DISPONIBLE
            # ==============================================

            frame_formulario = buscar_frame_formulario(
                page
            )


            if frame_formulario is not None:

                print(
                    "✅ Código validado."
                )


                print(
                    "✅ Formulario listo."
                )


                print(

                    "➡️ Ya puede procesarse "
                    "el siguiente NIE o DUI."

                )


                return frame_formulario


            page.wait_for_timeout(
                150
            )


            transcurrido += 150


        # ==================================================
        # SI EL PORTAL NO MOSTRÓ AUTOMÁTICAMENTE
        # EL FORMULARIO, ABRIMOS DE NUEVO LA URL.
        # ==================================================

        print(
            "✅ Código validado."
        )


        print(

            "🔄 Cargando nuevamente "
            "el formulario de asistencia..."

        )


        page.goto(

            URL,

            wait_until="domcontentloaded",

            timeout=20000

        )


        page.wait_for_timeout(
            700
        )


        # ==================================================
        # ESPERAR NIE / DUI
        # ==================================================

        estado_nuevo, frame_nuevo = esperar_estado_formulario(

            page,

            timeout_ms=12000

        )


        if estado_nuevo == "formulario":

            print(
                "✅ Formulario listo."
            )


            print(

                "➡️ Ya puede procesarse "
                "el siguiente NIE o DUI."

            )


            return frame_nuevo


        # ==================================================
        # VOLVIÓ A PEDIR CÓDIGO
        # ==================================================

        if estado_nuevo == "codigo":

            print(

                "⚠️ El portal volvió a solicitar "
                "el código después de validarlo."

            )


            return None


        print(

            "❌ Después de validar el código "
            "no apareció Tipo de documento."

        )


        imprimir_diagnostico(
            page
        )


        return None


    except Exception as error:

        print(
            "❌ Error desbloqueando formulario:"
        )


        print(
            error
        )


        return None


# ==========================================================
# ABRIR FORMULARIO PARA CADA PERSONA
# ==========================================================

def abrir_formulario_para_persona(

    page,

    intentos=4

):

    for intento in range(

        1,

        intentos + 1

    ):

        try:

            print(

                f"🔄 Preparando formulario "
                f"(intento {intento}/{intentos})..."

            )


            # ==================================================
            # ABRIR SIEMPRE EL ENLACE ORIGINAL
            # ==================================================

            page.goto(

                URL,

                wait_until="domcontentloaded",

                timeout=20000

            )


            page.wait_for_timeout(
                500
            )


            # ==================================================
            # FORMULARIO O CÓDIGO
            # ==================================================

            frame = desbloquear_formulario(
                page
            )


            if frame is not None:

                frame_confirmado = buscar_frame_formulario(
                    page
                )


                if frame_confirmado is not None:

                    print(
                        "✅ Tipo de documento disponible."
                    )


                    return frame_confirmado


                print(

                    "⚠️ El formulario abrió, "
                    "pero aún no aparece NIE/DUI."

                )

        except Exception as error:

            print(

                f"⚠️ Intento {intento} falló:",

                error

            )


        page.wait_for_timeout(
            700
        )


    print(

        "❌ DAVIS no pudo dejar disponible "
        "el selector NIE/DUI."

    )


    return None


# ==========================================================
# BUSCAR SELECTOR DE TIPO DE DOCUMENTO
# ==========================================================

def obtener_selector_tipo_documento(
    frame
):

    # ======================================================
    # POR NOMBRE
    # ======================================================

    try:

        selector = frame.get_by_role(

            "combobox",

            name=re.compile(

                r"tipo\s+de\s+documento",

                re.IGNORECASE,

            ),

        ).first


        if (

            selector.count()

            and

            selector.is_visible()

        ):

            return selector

    except Exception:

        pass


    # ======================================================
    # CUALQUIER COMBOBOX
    # ======================================================

    try:

        combos = frame.locator(

            '[role="combobox"]:visible'

        )


        if combos.count():

            return combos.first

    except Exception:

        pass


    # ======================================================
    # SELECT NATIVO
    # ======================================================

    try:

        selects = frame.locator(
            "select:visible"
        )


        for indice in range(
            selects.count()
        ):

            contenido = normalizar_texto(

                selects.nth(
                    indice
                ).inner_text(
                    timeout=500
                )

            )


            if (

                "nie"
                in contenido

                and

                "dui"
                in contenido

            ):

                return selects.nth(
                    indice
                )

    except Exception:

        pass


    return None


# ==========================================================
# SELECCIONAR NIE O DUI
# ==========================================================

def seleccionar_tipo_documento(

    frame,

    page,

    tipo_documento

):

    tipo_documento = str(
        tipo_documento
    ).strip().upper()


    if tipo_documento not in (

        "NIE",

        "DUI"

    ):

        raise ValueError(

            "Tipo de documento inválido: "
            +
            tipo_documento

        )


    print(

        "📄 Seleccionando tipo de documento:",

        tipo_documento

    )


    selector = obtener_selector_tipo_documento(
        frame
    )


    if selector is None:

        raise Exception(

            "No se encontró el menú "
            "Tipo de documento."

        )


    selector.wait_for(

        state="visible",

        timeout=4000

    )


    # ======================================================
    # SELECT HTML
    # ======================================================

    try:

        tag = selector.evaluate(

            "(el) => el.tagName.toLowerCase()"

        )


        if tag == "select":

            selector.select_option(

                label=tipo_documento

            )


            print(

                "✅ Tipo de documento seleccionado:",

                tipo_documento

            )


            return

    except Exception:

        pass


    # ======================================================
    # MENÚ PERSONALIZADO
    # ======================================================

    selector.click()


    page.wait_for_timeout(
        250
    )


    seleccionado = False


    # ======================================================
    # MÉTODO 1 - ROLE OPTION
    # ======================================================

    try:

        opcion = frame.get_by_role(

            "option",

            name=tipo_documento,

            exact=True,

        ).last


        opcion.wait_for(

            state="visible",

            timeout=2000

        )


        opcion.click()


        seleccionado = True

    except Exception:

        pass


    # ======================================================
    # MÉTODO 2 - TEXTO EXACTO DENTRO DEL FRAME
    # ======================================================

    if not seleccionado:

        try:

            opciones = frame.get_by_text(

                tipo_documento,

                exact=True,

            )


            for indice in range(

                opciones.count() - 1,

                -1,

                -1,

            ):

                opcion = opciones.nth(
                    indice
                )


                if opcion.is_visible():

                    opcion.click()


                    seleccionado = True


                    break

        except Exception:

            pass


    # ======================================================
    # MÉTODO 3 - TEXTO EXACTO EN PÁGINA PRINCIPAL
    # ======================================================

    if not seleccionado:

        try:

            opciones = page.get_by_text(

                tipo_documento,

                exact=True,

            )


            for indice in range(

                opciones.count() - 1,

                -1,

                -1,

            ):

                opcion = opciones.nth(
                    indice
                )


                if opcion.is_visible():

                    opcion.click()


                    seleccionado = True


                    break

        except Exception:

            pass


    if not seleccionado:

        raise Exception(

            f"No se pudo seleccionar "
            f"{tipo_documento} "
            f"en Tipo de documento."

        )


    page.wait_for_timeout(
        300
    )


    print(

        "✅ Tipo de documento seleccionado:",

        tipo_documento

    )


# ==========================================================
# CAMPO NIE / DUI
# ==========================================================

def obtener_campo_documento(

    frame,

    tipo_documento

):

    # ======================================================
    # ROLE
    # ======================================================

    try:

        campo = frame.get_by_role(

            "textbox",

            name=tipo_documento,

            exact=True,

        ).first


        campo.wait_for(

            state="visible",

            timeout=2500

        )


        return campo

    except Exception:

        pass


    # ======================================================
    # PLACEHOLDER
    # ======================================================

    try:

        campo = frame.locator(

            f'input[placeholder*="{tipo_documento}" i]:visible'

        ).first


        campo.wait_for(

            state="visible",

            timeout=2500

        )


        return campo

    except Exception:

        pass


    # ======================================================
    # ARIA LABEL
    # ======================================================

    try:

        campo = frame.locator(

            f'input[aria-label*="{tipo_documento}" i]:visible'

        ).first


        campo.wait_for(

            state="visible",

            timeout=1800

        )


        return campo

    except Exception:

        pass


    raise Exception(

        f"No apareció el campo "
        f"para ingresar el "
        f"{tipo_documento}."

    )


# ==========================================================
# BOTÓN VERIFICAR
# ==========================================================

def obtener_boton_verificar(
    frame
):

    try:

        boton = frame.get_by_role(

            "button",

            name=re.compile(

                r"verificar",

                re.IGNORECASE,

            ),

        ).first


        if (

            boton.count()

            and

            boton.is_visible()

        ):

            return boton

    except Exception:

        pass


    return None


# ==========================================================
# BOTÓN VALIDAR ASISTENCIA
# ==========================================================

def obtener_boton_asistencia(
    frame
):

    try:

        boton = frame.get_by_role(

            "button",

            name=re.compile(

                r"valida\s+tu\s+asistencia",

                re.IGNORECASE,

            ),

        ).first


        boton.wait_for(

            state="visible",

            timeout=3000

        )


        return boton

    except Exception:

        pass


    try:

        boton = frame.locator(

            "button:visible"

        ).filter(

            has_text=re.compile(

                r"valida\s+tu\s+asistencia",

                re.IGNORECASE,

            )

        ).first


        boton.wait_for(

            state="visible",

            timeout=2500

        )


        return boton

    except Exception:

        return None


# ==========================================================
# ESPERAR RESULTADO DEL DOCUMENTO
# ==========================================================

def esperar_resultado_documento(

    page,

    frame,

    timeout_ms=8000

):

    transcurrido = 0


    while transcurrido < timeout_ms:

        texto = texto_de_pagina(
            page
        )


        # ==================================================
        # YA REGISTRADA
        # ==================================================

        if asistencia_ya_registrada(
            texto
        ):

            return "ya_registrada"


        # ==================================================
        # NO ENCONTRADO
        # ==================================================

        if documento_no_encontrado(
            texto
        ):

            return "no_encontrado"


        # ==================================================
        # INVÁLIDO
        # ==================================================

        if documento_invalido(
            texto
        ):

            return "invalido"


        # ==================================================
        # BOTÓN HABILITADO
        # ==================================================

        boton = obtener_boton_asistencia(
            frame
        )


        if boton is not None:

            try:

                if boton.is_enabled():

                    return "valido"

            except Exception:

                pass


        page.wait_for_timeout(
            80
        )


        transcurrido += 80


    return "timeout"


# ==========================================================
# ENVIAR ASISTENCIA
# ==========================================================

def enviar_asistencia(

    page,

    boton_asistencia

):

    print(
        "📤 Enviando asistencia..."
    )


    respuesta = None


    click_hecho = False


    try:

        with page.expect_response(

            lambda response:

                response.request.method
                in (
                    "POST",
                    "PUT",
                    "PATCH"
                ),

            timeout=4500,

        ) as respuesta_info:


            boton_asistencia.click()


            click_hecho = True


        respuesta = respuesta_info.value

    except PlaywrightTimeoutError:

        click_hecho = True

    except Exception:

        pass


    # ======================================================
    # SI EL CLICK NO SE REALIZÓ
    # ======================================================

    if not click_hecho:

        try:

            boton_asistencia.click()


            click_hecho = True

        except Exception:

            return "error"


    # ======================================================
    # ESPERAR RESULTADO
    # ======================================================

    transcurrido = 0


    while transcurrido < 5000:

        texto = texto_de_pagina(
            page
        )


        if asistencia_ya_registrada(
            texto
        ):

            return "ya_registrada"


        if asistencia_exitosa(
            texto
        ):

            return "enviada"


        if (

            "error al registrar la asistencia"
            in texto

            or

            "no se pudo registrar la asistencia"
            in texto

        ):

            return "error"


        # ==================================================
        # SI APARECE EL CÓDIGO DESPUÉS DE ENVIAR
        # LA ASISTENCIA YA SE ENVIÓ.
        # ==================================================

        if buscar_frame_codigo(
            page
        ) is not None:

            return "enviada"


        page.wait_for_timeout(
            100
        )


        transcurrido += 100


    # ======================================================
    # RESPUESTA HTTP
    # ======================================================

    if respuesta is not None:

        if (

            200
            <=
            respuesta.status
            <
            400

        ):

            return "enviada"


        return "error"


    texto = texto_de_pagina(
        page
    )


    if asistencia_ya_registrada(
        texto
    ):

        return "ya_registrada"


    if asistencia_exitosa(
        texto
    ):

        return "enviada"


    return "sin_confirmacion"


# ==========================================================
# PLAYWRIGHT
# ==========================================================

with sync_playwright() as p:

    browser = None

    context = None


    try:

        # ==================================================
        # ABRIR CHROMIUM
        # ==================================================

        browser = p.chromium.launch(

            headless=HEADLESS

        )


        context = browser.new_context()


        page = context.new_page()


        page.set_default_timeout(
            7000
        )


        # ==================================================
        # CONTADORES
        # ==================================================

        exitosos = 0

        ya_existentes = 0

        no_encontrados = 0

        omitidos = 0

        errores = 0


        # ==================================================
        # RECORRER TODAS LAS PERSONAS
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

                f"ASISTENCIA {numero} "
                f"DE {len(personas)}"

            )

            print(
                "======================================"
            )


            # ==================================================
            # SOLO UTILIZAMOS TIPO + DOCUMENTO
            # ==================================================

            tipo_documento = str(

                persona.get(
                    "tipo_documento",
                    ""
                )

            ).strip().upper()


            documento = str(

                persona.get(
                    "documento",
                    ""
                )

            ).strip()


            print(

                "TIPO_DOCUMENTO:",

                tipo_documento
                if tipo_documento
                else
                "VACÍO"

            )


            print(

                "DOCUMENTO:",

                documento
                if documento
                else
                "VACÍO"

            )


            # ==================================================
            # TIPO INVÁLIDO
            # ==================================================

            if tipo_documento not in (

                "NIE",

                "DUI"

            ):

                print(

                    "⚠️ TIPO DE DOCUMENTO INVÁLIDO"

                )


                print(

                    "Solo se permite NIE o DUI."

                )


                omitidos += 1


                continue


            # ==================================================
            # SIN DOCUMENTO
            # ==================================================

            if not documento:

                print(

                    "⚠️ REGISTRO SIN DOCUMENTO"

                )


                omitidos += 1


                continue


            print(

                f"{tipo_documento}:",

                documento

            )


            try:

                # ==================================================
                # ABRIR FORMULARIO PARA ESTA PERSONA
                # ==================================================

                print()

                print(
                    "======================================"
                )

                print(
                    "ABRIENDO FORMULARIO"
                )

                print(
                    "======================================"
                )


                frame = abrir_formulario_para_persona(

                    page,

                    intentos=4

                )


                if frame is None:

                    print(

                        "❌ ERROR EN EL REGISTRO"

                    )


                    print(

                        "No fue posible abrir el formulario "
                        "para esta persona."

                    )


                    errores += 1


                    continue


                # ==================================================
                # SELECCIONAR NIE O DUI
                # ==================================================

                seleccionar_tipo_documento(

                    frame,

                    page,

                    tipo_documento

                )


                # ==================================================
                # BUSCAR CAMPO
                # ==================================================

                campo = obtener_campo_documento(

                    frame,

                    tipo_documento

                )


                campo.click()


                campo.fill(
                    documento
                )


                print(

                    f"🔍 Verificando "
                    f"{tipo_documento}..."

                )


                # ==================================================
                # VERIFICAR DOCUMENTO
                # ==================================================

                boton_verificar = obtener_boton_verificar(
                    frame
                )


                if boton_verificar is not None:

                    try:

                        boton_verificar.click()

                    except Exception:

                        campo.press(
                            "Tab"
                        )

                else:

                    # ==============================================
                    # EN EL PORTAL ACTUAL PUEDE NO HABER
                    # BOTÓN SEPARADO DE VERIFICAR.
                    # ==============================================

                    campo.press(
                        "Tab"
                    )


                # ==================================================
                # ESPERAR VALIDACIÓN
                # ==================================================

                resultado = esperar_resultado_documento(

                    page,

                    frame,

                    timeout_ms=8000

                )


                # ==================================================
                # YA TENÍA ASISTENCIA
                # ==================================================

                if resultado == "ya_registrada":

                    print(

                        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"

                    )


                    ya_existentes += 1


                    continue


                # ==================================================
                # NO ENCONTRADO / INVÁLIDO
                # ==================================================

                if resultado in (

                    "no_encontrado",

                    "invalido"

                ):

                    print(

                        f"🔎 {tipo_documento} "
                        f"NO ENCONTRADO"

                    )


                    if resultado == "invalido":

                        print(

                            "Motivo: documento inválido."

                        )


                    no_encontrados += 1


                    continue


                # ==================================================
                # TIMEOUT
                # ==================================================

                if resultado == "timeout":

                    texto = texto_de_pagina(
                        page
                    )


                    if asistencia_ya_registrada(
                        texto
                    ):

                        print(

                            "⚠️ YA TENÍA REGISTRADA ASISTENCIA"

                        )


                        ya_existentes += 1


                    elif (

                        documento_no_encontrado(
                            texto
                        )

                        or

                        documento_invalido(
                            texto
                        )

                    ):

                        print(

                            f"🔎 {tipo_documento} "
                            f"NO ENCONTRADO"

                        )


                        no_encontrados += 1


                    else:

                        print(

                            "❌ ERROR DE TIEMPO DE ESPERA"

                        )


                        errores += 1


                    continue


                # ==================================================
                # DOCUMENTO VALIDADO
                # ==================================================

                print(

                    f"✅ {tipo_documento} VALIDADO"

                )


                # ==================================================
                # BOTÓN DE ASISTENCIA
                # ==================================================

                boton_asistencia = obtener_boton_asistencia(
                    frame
                )


                if boton_asistencia is None:

                    print(

                        "❌ ERROR EN EL REGISTRO"

                    )


                    print(

                        "No se encontró el botón "
                        "Valida tu Asistencia."

                    )


                    errores += 1


                    continue


                # ==================================================
                # ESPERAR QUE EL BOTÓN SE HABILITE
                # ==================================================

                habilitado = False


                for _ in range(
                    40
                ):

                    try:

                        if boton_asistencia.is_enabled():

                            habilitado = True


                            break

                    except Exception:

                        pass


                    page.wait_for_timeout(
                        100
                    )


                if not habilitado:

                    texto = texto_de_pagina(
                        page
                    )


                    if asistencia_ya_registrada(
                        texto
                    ):

                        print(

                            "⚠️ YA TENÍA REGISTRADA ASISTENCIA"

                        )


                        ya_existentes += 1


                    elif (

                        documento_no_encontrado(
                            texto
                        )

                        or

                        documento_invalido(
                            texto
                        )

                    ):

                        print(

                            f"🔎 {tipo_documento} "
                            f"NO ENCONTRADO"

                        )


                        no_encontrados += 1


                    else:

                        print(

                            "❌ ERROR EN EL REGISTRO"

                        )


                        print(

                            "El botón Valida tu Asistencia "
                            "no se habilitó."

                        )


                        errores += 1


                    continue


                # ==================================================
                # ENVIAR ASISTENCIA
                # ==================================================

                resultado_envio = enviar_asistencia(

                    page,

                    boton_asistencia

                )


                # ==================================================
                # YA TENÍA
                # ==================================================

                if resultado_envio == "ya_registrada":

                    print(

                        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"

                    )


                    ya_existentes += 1


                # ==================================================
                # ENVIADA
                # ==================================================

                elif resultado_envio == "enviada":

                    print(

                        "✅ ASISTENCIA ENVIADA"

                    )


                    exitosos += 1


                # ==================================================
                # ERROR
                # ==================================================

                elif resultado_envio == "error":

                    print(

                        "❌ ERROR EN EL REGISTRO"

                    )


                    errores += 1


                # ==================================================
                # SIN CONFIRMACIÓN
                # ==================================================

                else:

                    print(

                        "❌ NO SE PUDO CONFIRMAR EL ENVÍO"

                    )


                    errores += 1


                print(

                    "➡️ Listo para el siguiente documento."

                )


            # ======================================================
            # TIMEOUT PLAYWRIGHT
            # ======================================================

            except PlaywrightTimeoutError as error:

                print(

                    "❌ ERROR DE TIEMPO DE ESPERA"

                )


                print(

                    f"{tipo_documento}:",

                    documento

                )


                print(

                    "Error:",

                    error

                )


                errores += 1


                continue


            # ======================================================
            # ERROR GENERAL
            # ======================================================

            except Exception as error:

                print(

                    "❌ ERROR EN EL REGISTRO"

                )


                print(

                    f"{tipo_documento}:",

                    documento

                )


                print(

                    "Error:",

                    error

                )


                errores += 1


                continue


        # ==========================================================
        # RESUMEN FINAL
        # ==========================================================

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

            len(
                personas
            )

        )


        print(

            "✅ Asistencias enviadas:",

            exitosos

        )


        print(

            "⚠️ Ya tenían registrada asistencia:",

            ya_existentes

        )


        print(

            "🔎 Documentos no encontrados:",

            no_encontrados

        )


        print(

            "⚠️ Omitidos:",

            omitidos

        )


        print(

            "❌ Errores:",

            errores

        )


        print(
            "======================================"
        )


    # ==========================================================
    # CERRAR NAVEGADOR SOLO AL TERMINAR TODA LA LISTA
    # ==========================================================

    finally:

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