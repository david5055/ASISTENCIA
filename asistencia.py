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
# CONFIGURACIÓN
# ==========================================================

URL = os.getenv(
    "DAVIS_ASISTENCIA_URL",
    ""
).strip()

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
# ESTOS NO SON TIEMPOS DE ESPERA ENTRE PERSONAS
#
# SON SOLO LÍMITES DE SEGURIDAD.
#
# SI ALGO APARECE EN 50 MS, DAVIS CONTINÚA EN 50 MS.
# ==========================================================

TIMEOUT_NAVEGACION = 20000
TIMEOUT_ELEMENTO = 8000
TIMEOUT_RESULTADO = 12000

POLL_MS = 25


# ==========================================================
# VALIDACIONES
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
# INFORMACIÓN
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
                timeout=1000
            )

        )


    except Exception:

        return ""


# ==========================================================
# TEXTO DE PÁGINA
# ==========================================================

def texto_de_pagina(
    page
):

    textos = []


    for frame in page.frames:

        texto = texto_de_frame(
            frame
        )


        if texto:

            textos.append(
                texto
            )


    return "\n".join(
        textos
    )


# ==========================================================
# PANTALLA DE CÓDIGO
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
# YA TENÍA ASISTENCIA
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
# BUSCAR FRAME FORMULARIO
# ==========================================================

def buscar_frame_formulario(
    page
):

    for frame in page.frames:

        texto = texto_de_frame(
            frame
        )


        # ==================================================
        # DETECCIÓN PRINCIPAL
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
        # COMBOBOX
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
        # SELECT
        # ==================================================

        try:

            selects = frame.locator(
                "select:visible"
            )


            for indice in range(
                selects.count()
            ):

                texto_select = normalizar_texto(

                    selects.nth(
                        indice
                    ).inner_text(
                        timeout=500
                    )

                )


                if (

                    "nie"
                    in texto_select

                    and

                    "dui"
                    in texto_select

                ):

                    return frame


        except Exception:

            pass


    return None


# ==========================================================
# BUSCAR FRAME CÓDIGO
# ==========================================================

def buscar_frame_codigo(
    page
):

    for frame in page.frames:

        texto = texto_de_frame(
            frame
        )


        if pagina_pide_codigo(
            texto
        ):

            return frame


        # ==================================================
        # CAMPOS DE CÓDIGO
        # ==================================================

        try:

            campos = frame.locator(

                'input[maxlength="1"]:visible'

            )


            if campos.count() >= 4:

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
# ESPERAR FORMULARIO O CÓDIGO
#
# NO ESPERA UN TIEMPO FIJO.
# REVISA CADA 25 MILISEGUNDOS.
# ==========================================================

def esperar_estado(
    page
):

    transcurrido = 0


    while transcurrido < TIMEOUT_RESULTADO:

        frame_formulario = buscar_frame_formulario(
            page
        )


        if frame_formulario is not None:

            return (
                "formulario",
                frame_formulario
            )


        frame_codigo = buscar_frame_codigo(
            page
        )


        if frame_codigo is not None:

            return (
                "codigo",
                frame_codigo
            )


        page.wait_for_timeout(
            POLL_MS
        )


        transcurrido += POLL_MS


    return (
        "timeout",
        None
    )


# ==========================================================
# INGRESAR CÓDIGO
# ==========================================================

def ingresar_codigo(
    page,
    frame
):

    print()

    print(
        "🔐 Ingresando código..."
    )


    campos = frame.locator(

        'input[maxlength="1"]:visible'

    )


    try:

        campos.first.wait_for(

            state="visible",

            timeout=TIMEOUT_ELEMENTO

        )

    except Exception:

        pass


    cantidad = campos.count()


    # ======================================================
    # MÉTODO NORMAL
    # ======================================================

    if cantidad >= len(
        CODIGO_VERIFICACION
    ):

        for indice, caracter in enumerate(
            CODIGO_VERIFICACION
        ):

            campos.nth(
                indice
            ).fill(
                caracter
            )


    # ======================================================
    # FALLBACK
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
                    caja["width"] <= 100

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
                "❌ No se encontraron los campos del código."
            )

            return False


        for indice, caracter in enumerate(
            CODIGO_VERIFICACION
        ):

            candidatos[
                indice
            ].fill(
                caracter
            )


    # ======================================================
    # BOTÓN VALIDAR
    # ======================================================

    boton = None


    try:

        boton = frame.get_by_role(

            "button",

            name=re.compile(

                r"validar\s*c[oó]digo",

                re.IGNORECASE,

            ),

        ).first


        boton.wait_for(

            state="visible",

            timeout=TIMEOUT_ELEMENTO

        )


    except Exception:

        try:

            boton = frame.locator(

                "button:visible"

            ).filter(

                has_text=re.compile(

                    r"validar\s*c[oó]digo",

                    re.IGNORECASE,

                )

            ).first


            boton.wait_for(

                state="visible",

                timeout=TIMEOUT_ELEMENTO

            )


        except Exception:

            print(
                "❌ No se encontró Validar código."
            )

            return False


    # ======================================================
    # ESPERAR HABILITADO
    # ======================================================

    transcurrido = 0


    while transcurrido < TIMEOUT_ELEMENTO:

        try:

            if boton.is_enabled():

                break


        except Exception:

            pass


        page.wait_for_timeout(
            POLL_MS
        )


        transcurrido += POLL_MS


    else:

        print(
            "❌ Validar código no se habilitó."
        )

        return False


    boton.click()


    print(
        "✅ Código enviado."
    )


    return True


# ==========================================================
# DESBLOQUEAR FORMULARIO
# ==========================================================

def desbloquear_formulario(
    page
):

    estado, frame = esperar_estado(
        page
    )


    # ======================================================
    # YA ESTÁ ABIERTO
    # ======================================================

    if estado == "formulario":

        return frame


    # ======================================================
    # NO APARECIÓ
    # ======================================================

    if estado == "timeout":

        return None


    # ======================================================
    # CÓDIGO
    # ======================================================

    if not ingresar_codigo(
        page,
        frame
    ):

        return None


    # ======================================================
    # ESPERAR RESULTADO DEL CÓDIGO
    #
    # APENAS APAREZCA EL FORMULARIO CONTINÚA.
    # ======================================================

    transcurrido = 0


    while transcurrido < TIMEOUT_RESULTADO:

        texto = texto_de_pagina(
            page
        )


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
                "❌ Código incorrecto."
            )

            return None


        frame_formulario = buscar_frame_formulario(
            page
        )


        if frame_formulario is not None:

            print(
                "✅ Código validado."
            )

            return frame_formulario


        page.wait_for_timeout(
            POLL_MS
        )


        transcurrido += POLL_MS


    # ======================================================
    # SI NO VOLVIÓ SOLO, CARGAR NUEVAMENTE EL ENLACE
    # ======================================================

    page.goto(

        URL,

        wait_until="domcontentloaded",

        timeout=TIMEOUT_NAVEGACION

    )


    estado, frame = esperar_estado(
        page
    )


    if estado == "formulario":

        return frame


    return None


# ==========================================================
# ABRIR FORMULARIO PARA CADA PERSONA
#
# NO HAY PAUSA ENTRE PERSONAS.
# ==========================================================

def abrir_formulario_para_persona(
    page
):

    for intento in range(
        1,
        5
    ):

        try:

            page.goto(

                URL,

                wait_until="domcontentloaded",

                timeout=TIMEOUT_NAVEGACION

            )


            frame = desbloquear_formulario(
                page
            )


            if frame is not None:

                return frame


        except Exception as error:

            print(

                f"⚠️ Intento {intento}/4 falló:",

                error

            )


    return None


# ==========================================================
# OBTENER SELECTOR DOCUMENTO
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
    # SELECT NATIVO
    # ======================================================

    try:

        selects = frame.locator(
            "select:visible"
        )


        for indice in range(
            selects.count()
        ):

            selector = selects.nth(
                indice
            )


            texto = normalizar_texto(

                selector.inner_text(
                    timeout=500
                )

            )


            if (

                "nie"
                in texto

                and

                "dui"
                in texto

            ):

                return selector


    except Exception:

        pass


    # ======================================================
    # COMBOBOX VISIBLE
    # ======================================================

    try:

        combos = frame.locator(

            '[role="combobox"]:visible'

        )


        if combos.count():

            return combos.first


    except Exception:

        pass


    return None


# ==========================================================
# CONFIRMAR NIE / DUI
# ==========================================================

def tipo_documento_seleccionado(
    frame,
    selector,
    tipo_documento
):

    tipo_documento = tipo_documento.upper()


    # ======================================================
    # VALOR DEL SELECTOR
    # ======================================================

    try:

        valor = selector.input_value()


        if str(
            valor
        ).strip().upper() == tipo_documento:

            return True


    except Exception:

        pass


    # ======================================================
    # VALUE
    # ======================================================

    try:

        valor = selector.get_attribute(
            "value"
        )


        if str(
            valor
            or
            ""
        ).strip().upper() == tipo_documento:

            return True


    except Exception:

        pass


    # ======================================================
    # CAMPO RESULTANTE
    # ======================================================

    try:

        campo = frame.get_by_role(

            "textbox",

            name=tipo_documento,

            exact=True,

        ).first


        if (

            campo.count()
            and
            campo.is_visible()

        ):

            return True


    except Exception:

        pass


    try:

        campo = frame.locator(

            f'input[placeholder*="{tipo_documento}" i]:visible'

        ).first


        if (

            campo.count()
            and
            campo.is_visible()

        ):

            return True


    except Exception:

        pass


    return False


# ==========================================================
# SELECCIONAR NIE O DUI
#
# DUI:
# ABRE MENÚ
# ↓
# SELECCIONA DUI
# ↓
# CONFIRMA QUE REALMENTE CAMBIÓ
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
            "Solo se permite NIE o DUI."
        )


    print(

        "📄 Seleccionando:",

        tipo_documento

    )


    selector = obtener_selector_tipo_documento(
        frame
    )


    if selector is None:

        raise Exception(
            "No se encontró Tipo de documento."
        )


    selector.wait_for(

        state="visible",

        timeout=TIMEOUT_ELEMENTO

    )


    # ======================================================
    # SELECT HTML NATIVO
    # ======================================================

    try:

        tag = selector.evaluate(

            "(el) => el.tagName.toLowerCase()"

        )


        if tag == "select":

            try:

                selector.select_option(
                    label=tipo_documento
                )


            except Exception:

                opciones = selector.locator(
                    "option"
                )


                encontrado = False


                for indice in range(
                    opciones.count()
                ):

                    opcion = opciones.nth(
                        indice
                    )


                    texto_opcion = normalizar_texto(

                        opcion.inner_text()

                    ).strip().upper()


                    if texto_opcion == tipo_documento:

                        valor = opcion.get_attribute(
                            "value"
                        )


                        selector.select_option(
                            value=valor
                        )


                        encontrado = True

                        break


                if not encontrado:

                    raise Exception(
                        "Opción no encontrada."
                    )


            print(

                "✅ Seleccionado:",

                tipo_documento

            )


            return True


    except Exception:

        pass


    # ======================================================
    # SELECTOR PERSONALIZADO
    # ======================================================

    for intento in range(
        1,
        5
    ):

        try:

            selector.click()


            seleccionado = False


            # ==================================================
            # ROLE OPTION
            # ==================================================

            try:

                opcion = frame.get_by_role(

                    "option",

                    name=tipo_documento,

                    exact=True,

                ).last


                opcion.wait_for(

                    state="visible",

                    timeout=3000

                )


                opcion.dispatch_event(
                    "mousedown"
                )


                opcion.dispatch_event(
                    "mouseup"
                )


                opcion.click(
                    force=True
                )


                seleccionado = True


            except Exception:

                pass


            # ==================================================
            # TEXTO EXACTO
            # ==================================================

            if not seleccionado:

                try:

                    opciones = frame.get_by_text(

                        re.compile(

                            rf"^\s*{re.escape(tipo_documento)}\s*$",

                            re.IGNORECASE,

                        )

                    )


                    for indice in range(

                        opciones.count() - 1,

                        -1,

                        -1

                    ):

                        opcion = opciones.nth(
                            indice
                        )


                        if opcion.is_visible():

                            opcion.dispatch_event(
                                "mousedown"
                            )


                            opcion.dispatch_event(
                                "mouseup"
                            )


                            opcion.click(
                                force=True
                            )


                            seleccionado = True

                            break


                except Exception:

                    pass


            # ==================================================
            # ESPERAR CONFIRMACIÓN
            # ==================================================

            transcurrido = 0


            while transcurrido < 3000:

                if tipo_documento_seleccionado(

                    frame,

                    selector,

                    tipo_documento

                ):

                    print(

                        "✅ Selección confirmada:",

                        tipo_documento

                    )


                    return True


                page.wait_for_timeout(
                    POLL_MS
                )


                transcurrido += POLL_MS


        except Exception:

            pass


        # ==================================================
        # FALLBACK TECLADO
        #
        # MENÚ:
        #
        # NIE
        # DUI
        # CÓDIGO INTEGRACIÓN
        # ======================================================

        try:

            page.keyboard.press(
                "Escape"
            )


            selector.click()


            page.keyboard.press(
                "Home"
            )


            if tipo_documento == "DUI":

                page.keyboard.press(
                    "ArrowDown"
                )


            page.keyboard.press(
                "Enter"
            )


            transcurrido = 0


            while transcurrido < 3000:

                if tipo_documento_seleccionado(

                    frame,

                    selector,

                    tipo_documento

                ):

                    print(

                        "✅ Selección confirmada:",

                        tipo_documento

                    )


                    return True


                page.wait_for_timeout(
                    POLL_MS
                )


                transcurrido += POLL_MS


        except Exception:

            pass


    raise Exception(

        f"No se pudo seleccionar "
        f"{tipo_documento}."

    )


# ==========================================================
# OBTENER CAMPO NIE / DUI
# ==========================================================

def obtener_campo_documento(
    frame,
    tipo_documento
):

    try:

        campo = frame.get_by_role(

            "textbox",

            name=tipo_documento,

            exact=True,

        ).first


        campo.wait_for(

            state="visible",

            timeout=TIMEOUT_ELEMENTO

        )


        return campo


    except Exception:

        pass


    try:

        campo = frame.locator(

            f'input[placeholder*="{tipo_documento}" i]:visible'

        ).first


        campo.wait_for(

            state="visible",

            timeout=TIMEOUT_ELEMENTO

        )


        return campo


    except Exception:

        pass


    try:

        campo = frame.locator(

            f'input[aria-label*="{tipo_documento}" i]:visible'

        ).first


        campo.wait_for(

            state="visible",

            timeout=TIMEOUT_ELEMENTO

        )


        return campo


    except Exception:

        pass


    raise Exception(

        f"No apareció el campo "
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
# BOTÓN ASISTENCIA
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


        if (

            boton.count()
            and
            boton.is_visible()

        ):

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
# ESPERAR RESULTADO
#
# CONTINÚA APENAS HAY RESPUESTA.
# ==========================================================

def esperar_resultado_documento(
    page,
    frame
):

    transcurrido = 0


    while transcurrido < TIMEOUT_RESULTADO:

        texto = texto_de_pagina(
            page
        )


        if asistencia_ya_registrada(
            texto
        ):

            return "ya_registrada"


        if documento_no_encontrado(
            texto
        ):

            return "no_encontrado"


        if documento_invalido(
            texto
        ):

            return "invalido"


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
            POLL_MS
        )


        transcurrido += POLL_MS


    return "timeout"


# ==========================================================
# ENVIAR ASISTENCIA
#
# NO TIENE PAUSA FIJA.
# ==========================================================

def enviar_asistencia(
    page,
    boton
):

    print(
        "📤 Enviando asistencia..."
    )


    try:

        boton.click()


    except Exception:

        return "error"


    transcurrido = 0


    while transcurrido < TIMEOUT_RESULTADO:

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
        # SI APARECE EL CÓDIGO,
        # LA ASISTENCIA ANTERIOR YA FUE ENVIADA.
        # ==================================================

        if buscar_frame_codigo(
            page
        ) is not None:

            return "enviada"


        page.wait_for_timeout(
            POLL_MS
        )


        transcurrido += POLL_MS


    return "sin_confirmacion"


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
            TIMEOUT_ELEMENTO
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
        # TODAS LAS PERSONAS
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
            # VALIDACIONES
            # ==================================================

            if tipo_documento not in (

                "NIE",

                "DUI"

            ):

                print(
                    "⚠️ TIPO DE DOCUMENTO INVÁLIDO"
                )


                omitidos += 1

                continue


            if not documento:

                print(
                    "⚠️ REGISTRO SIN DOCUMENTO"
                )


                omitidos += 1

                continue


            try:

                # ==================================================
                # ABRIR FORMULARIO
                # ==================================================

                frame = abrir_formulario_para_persona(
                    page
                )


                if frame is None:

                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )


                    print(
                        "No se pudo abrir el formulario."
                    )


                    errores += 1

                    continue


                # ==================================================
                # SELECCIONAR NIE / DUI
                # ==================================================

                seleccionar_tipo_documento(

                    frame,

                    page,

                    tipo_documento

                )


                # ==================================================
                # CAMPO DOCUMENTO
                # ==================================================

                campo = obtener_campo_documento(

                    frame,

                    tipo_documento

                )


                campo.fill(
                    documento
                )


                print(

                    f"{tipo_documento}:",

                    documento

                )


                print(

                    f"🔍 Verificando "
                    f"{tipo_documento}..."

                )


                # ==================================================
                # VERIFICAR
                # ==================================================

                boton_verificar = obtener_boton_verificar(
                    frame
                )


                if boton_verificar is not None:

                    boton_verificar.click()


                else:

                    campo.press(
                        "Tab"
                    )


                # ==================================================
                # RESULTADO
                # ==================================================

                resultado = esperar_resultado_documento(

                    page,

                    frame

                )


                # ==================================================
                # YA TENÍA
                # ==================================================

                if resultado == "ya_registrada":

                    print(
                        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
                    )


                    ya_existentes += 1


                    print(
                        "➡️ Siguiente inmediatamente..."
                    )


                    continue


                # ==================================================
                # NO ENCONTRADO
                # ==================================================

                if resultado in (

                    "no_encontrado",

                    "invalido"

                ):

                    print(

                        f"🔎 {tipo_documento} "
                        f"NO ENCONTRADO"

                    )


                    no_encontrados += 1


                    print(
                        "➡️ Siguiente inmediatamente..."
                    )


                    continue


                # ==================================================
                # TIMEOUT
                # ==================================================

                if resultado == "timeout":

                    print(
                        "❌ ERROR DE TIEMPO DE ESPERA"
                    )


                    errores += 1


                    continue


                # ==================================================
                # VALIDADO
                # ==================================================

                print(

                    f"✅ {tipo_documento} VALIDADO"

                )


                boton_asistencia = obtener_boton_asistencia(
                    frame
                )


                if boton_asistencia is None:

                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )


                    print(
                        "No apareció Valida tu Asistencia."
                    )


                    errores += 1

                    continue


                # ==================================================
                # ESPERAR HABILITADO
                # ==================================================

                transcurrido = 0


                while transcurrido < TIMEOUT_ELEMENTO:

                    try:

                        if boton_asistencia.is_enabled():

                            break


                    except Exception:

                        pass


                    page.wait_for_timeout(
                        POLL_MS
                    )


                    transcurrido += POLL_MS


                else:

                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )


                    print(
                        "El botón no se habilitó."
                    )


                    errores += 1

                    continue


                # ==================================================
                # ENVIAR
                # ==================================================

                resultado_envio = enviar_asistencia(

                    page,

                    boton_asistencia

                )


                if resultado_envio == "enviada":

                    print(
                        "✅ ASISTENCIA ENVIADA"
                    )


                    exitosos += 1


                elif resultado_envio == "ya_registrada":

                    print(
                        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
                    )


                    ya_existentes += 1


                elif resultado_envio == "error":

                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )


                    errores += 1


                else:

                    print(
                        "❌ NO SE PUDO CONFIRMAR EL ENVÍO"
                    )


                    errores += 1


                # ==================================================
                # AQUÍ NO EXISTE SLEEP.
                #
                # APENAS TERMINA ESTE REGISTRO,
                # EL FOR PASA DIRECTAMENTE AL SIGUIENTE.
                # ==================================================

                print(
                    "➡️ Buscando inmediatamente "
                    "el siguiente NIE o DUI..."
                )


            except PlaywrightTimeoutError as error:

                print(
                    "❌ ERROR DE TIEMPO DE ESPERA"
                )


                print(
                    error
                )


                errores += 1


                continue


            except Exception as error:

                print(
                    "❌ ERROR EN EL REGISTRO"
                )


                print(
                    error
                )


                errores += 1


                continue


        # ==========================================================
        # RESUMEN
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