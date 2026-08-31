import os
import sys
import json
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
# DATOS RECIBIDOS DESDE DAVIS WEB
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


if not ARCHIVO_JSON:

    print(
        "❌ DAVIS no recibió el archivo JSON."
    )

    sys.exit(1)


if not os.path.exists(
    ARCHIVO_JSON
):

    print(
        "❌ No existe el archivo temporal:"
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


if not personas:

    print(
        "❌ El JSON no contiene registros."
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

print()

print(
    "Registros recibidos:",
    len(personas)
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


    return texto


# ==========================================================
# OBTENER TEXTO DE PÁGINA
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

        "asistencia ya registrada"

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# DOCUMENTO NO ENCONTRADO
# ==========================================================

def documento_no_encontrado(
    texto,
    tipo_documento=""
):

    texto = normalizar_texto(
        texto
    )


    tipo_documento = str(
        tipo_documento
    ).strip().upper()


    mensajes = (

        "beneficiario no encontrado",

        "documento no encontrado",

        "no existe el beneficiario",

        "no se encontro el beneficiario",

        "persona no encontrada",

        "nie no encontrado",

        "no se encontro el nie",

        "dui no encontrado",

        "no se encontro el dui"

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# DOCUMENTO INVÁLIDO
# ==========================================================

def documento_invalido(
    texto,
    tipo_documento=""
):

    texto = normalizar_texto(
        texto
    )


    tipo_documento = str(
        tipo_documento
    ).strip().upper()


    mensajes = (

        "documento invalido",

        "documento incorrecto",

        "nie invalido",

        "nie incorrecto",

        "dui invalido",

        "dui incorrecto"

    )


    return any(

        mensaje in texto

        for mensaje in mensajes

    )


# ==========================================================
# ESPERAR FORMULARIO O PANTALLA DE CÓDIGO
#
# DETECTA:
#
# NIE
# DUI
# SELECTOR DE TIPO DE DOCUMENTO
# PANTALLA DE CÓDIGO
# ==========================================================

def esperar_estado_formulario(
    page,
    timeout=5000
):

    try:

        resultado = page.wait_for_function(

            """
            () => {

                const texto =
                    document.body.innerText
                    .toLowerCase();


                // ==========================================
                // PANTALLA DE CÓDIGO
                // ==========================================

                const bloqueado =
                    texto.includes(
                        "ya existe una asistencia registrada en este dispositivo"
                    )
                    ||
                    texto.includes(
                        "ingresa el código de verificación"
                    )
                    ||
                    texto.includes(
                        "ingresa el codigo de verificacion"
                    )
                    ||
                    texto.includes(
                        "código de verificación"
                    )
                    ||
                    texto.includes(
                        "codigo de verificacion"
                    );


                if (bloqueado) {

                    return "bloqueado";

                }


                // ==========================================
                // BUSCAR NIE O DUI
                // ==========================================

                const inputs =
                    Array.from(
                        document.querySelectorAll(
                            "input"
                        )
                    );


                const campoDocumento =
                    inputs.find(
                        input => {

                            const visible =
                                !!(
                                    input.offsetWidth
                                    ||
                                    input.offsetHeight
                                    ||
                                    input.getClientRects().length
                                );


                            const placeholder =
                                (
                                    input.getAttribute(
                                        "placeholder"
                                    )
                                    ||
                                    ""
                                ).toLowerCase();


                            const aria =
                                (
                                    input.getAttribute(
                                        "aria-label"
                                    )
                                    ||
                                    ""
                                ).toLowerCase();


                            return (

                                visible

                                &&

                                (
                                    placeholder.includes(
                                        "nie"
                                    )
                                    ||
                                    placeholder.includes(
                                        "dui"
                                    )
                                    ||
                                    aria.includes(
                                        "nie"
                                    )
                                    ||
                                    aria.includes(
                                        "dui"
                                    )
                                )

                            );

                        }
                    );


                if (campoDocumento) {

                    return "formulario";

                }


                // ==========================================
                // SELECTOR TIPO DOCUMENTO
                // ==========================================

                const elementos =
                    Array.from(
                        document.querySelectorAll(
                            'select, [role="combobox"]'
                        )
                    );


                const selector =
                    elementos.find(
                        elemento => {

                            const visible =
                                !!(
                                    elemento.offsetWidth
                                    ||
                                    elemento.offsetHeight
                                    ||
                                    elemento.getClientRects().length
                                );


                            const aria =
                                (
                                    elemento.getAttribute(
                                        "aria-label"
                                    )
                                    ||
                                    ""
                                ).toLowerCase();


                            const textoElemento =
                                (
                                    elemento.innerText
                                    ||
                                    ""
                                ).toLowerCase();


                            return (

                                visible

                                &&

                                (
                                    aria.includes(
                                        "tipo de documento"
                                    )
                                    ||
                                    textoElemento.includes(
                                        "nie"
                                    )
                                    ||
                                    textoElemento.includes(
                                        "dui"
                                    )
                                )

                            );

                        }
                    );


                if (selector) {

                    return "formulario";

                }


                return false;

            }
            """,

            timeout=timeout,

            polling=30

        )


        return resultado.json_value()


    except PlaywrightTimeoutError:

        # ==================================================
        # FALLBACK PLAYWRIGHT
        # ==================================================

        try:

            selector = page.get_by_role(
                "combobox",
                name="Tipo de documento"
            )


            if selector.is_visible():

                return "formulario"


        except Exception:

            pass


        for tipo in (
            "NIE",
            "DUI"
        ):

            try:

                campo = page.get_by_role(
                    "textbox",
                    name=tipo,
                    exact=True
                )


                if campo.is_visible():

                    return "formulario"


            except Exception:

                pass


        return "timeout"


# ==========================================================
# DESBLOQUEAR FORMULARIO
# ==========================================================

def desbloquear_formulario(
    page
):

    estado = esperar_estado_formulario(

        page,

        timeout=5000

    )


    # ======================================================
    # YA ESTÁ DISPONIBLE
    # ======================================================

    if estado == "formulario":

        return True


    # ======================================================
    # NO APARECIÓ NADA
    # ======================================================

    if estado == "timeout":

        print(

            "❌ No apareció el formulario "
            "ni la pantalla del código."

        )


        return False


    # ======================================================
    # SOLICITA CÓDIGO
    # ======================================================

    print()

    print(
        "======================================"
    )

    print(
        "🔐 DESBLOQUEANDO FORMULARIO"
    )

    print(
        "======================================"
    )

    print(
        "Código recibido desde DAVIS: ********"
    )


    try:

        # ==================================================
        # CAMPOS INDIVIDUALES
        # ==================================================

        campos = page.locator(
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


        # ==================================================
        # MÉTODO PRINCIPAL
        # ==================================================

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


        # ==================================================
        # MÉTODO ALTERNATIVO
        # ==================================================

        else:

            inputs = page.locator(
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


        # ==================================================
        # BOTÓN VALIDAR CÓDIGO
        # ==================================================

        boton_codigo = page.get_by_role(
            "button",
            name="Validar código"
        )


        boton_codigo.wait_for(

            state="visible",

            timeout=3000

        )


        # ==================================================
        # ESPERAR A QUE SE HABILITE
        # ==================================================

        page.wait_for_function(

            """
            () => {

                const botones =
                    Array.from(
                        document.querySelectorAll(
                            "button"
                        )
                    );


                const boton =
                    botones.find(
                        b => {

                            const texto =
                                b.innerText
                                .toLowerCase();


                            return (
                                texto.includes(
                                    "validar código"
                                )
                                ||
                                texto.includes(
                                    "validar codigo"
                                )
                            );

                        }
                    );


                if (!boton) {

                    return false;

                }


                return (

                    !boton.disabled

                    &&

                    boton.getAttribute(
                        "aria-disabled"
                    ) !== "true"

                );

            }
            """,

            timeout=3000,

            polling=20

        )


        # ==================================================
        # VALIDAR
        # ==================================================

        boton_codigo.click()


        print(
            "🔓 Validando código..."
        )


        # ==================================================
        # ESPERAR FORMULARIO NIE / DUI
        # ==================================================

        estado_despues_codigo = esperar_estado_formulario(

            page,

            timeout=5000

        )


        if estado_despues_codigo == "formulario":

            print(
                "✅ Formulario desbloqueado."
            )


            return True


        texto = texto_de_pagina(
            page
        )


        if (

            "codigo incorrecto" in texto

            or

            "codigo invalido" in texto

            or

            "codigo no valido" in texto

        ):

            print(
                "❌ Código de integración incorrecto."
            )


        else:

            print(

                "❌ No apareció el formulario "
                "después de validar el código."

            )


        return False


    except PlaywrightTimeoutError:

        texto = texto_de_pagina(
            page
        )


        if (

            "codigo incorrecto" in texto

            or

            "codigo invalido" in texto

            or

            "codigo no valido" in texto

        ):

            print(
                "❌ Código de integración incorrecto."
            )


        else:

            print(

                "❌ No apareció el formulario "
                "después de validar el código."

            )


        return False


    except Exception as error:

        print(
            "❌ Error desbloqueando formulario:"
        )

        print(
            error
        )


        return False


# ==========================================================
# SELECCIONAR TIPO DE DOCUMENTO
#
# NIE → NIE
# DUI → DUI
# ==========================================================

def seleccionar_tipo_documento(
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


    # ======================================================
    # SELECTOR
    # ======================================================

    selector = page.get_by_role(
        "combobox",
        name="Tipo de documento"
    )


    selector.wait_for(

        state="visible",

        timeout=3000

    )


    # ======================================================
    # SELECT HTML NATIVO
    # ======================================================

    try:

        tag = selector.evaluate(

            "(el) => el.tagName.toLowerCase()"

        )


        if tag == "select":

            opciones = selector.locator(
                "option"
            )


            for indice in range(
                opciones.count()
            ):

                opcion = opciones.nth(
                    indice
                )


                texto = normalizar_texto(
                    opcion.inner_text()
                ).strip()


                if texto == normalizar_texto(
                    tipo_documento
                ).strip():

                    valor = opcion.get_attribute(
                        "value"
                    )


                    selector.select_option(
                        valor
                    )


                    return


    except Exception:

        pass


    # ======================================================
    # SELECT PERSONALIZADO
    # ======================================================

    try:

        valor_actual = normalizar_texto(

            selector.input_value()

        ).strip()


        if valor_actual == normalizar_texto(
            tipo_documento
        ).strip():

            return


    except Exception:

        pass


    selector.click()


    seleccionado = False


    # ======================================================
    # PRIMER INTENTO ROLE OPTION
    # ======================================================

    try:

        opcion = page.get_by_role(

            "option",

            name=tipo_documento,

            exact=True

        ).last


        opcion.wait_for(

            state="visible",

            timeout=1500

        )


        opcion.click()


        seleccionado = True


    except Exception:

        pass


    # ======================================================
    # FALLBACK POR TEXTO
    # ======================================================

    if not seleccionado:

        opcion = page.get_by_text(

            tipo_documento,

            exact=True

        ).last


        opcion.wait_for(

            state="visible",

            timeout=2000

        )


        opcion.click()


    print(

        "✅ Tipo de documento seleccionado:",

        tipo_documento

    )


# ==========================================================
# OBTENER CAMPO NIE O DUI
# ==========================================================

def obtener_campo_documento(
    page,
    tipo_documento
):

    tipo_documento = str(
        tipo_documento
    ).strip().upper()


    campo = page.get_by_role(

        "textbox",

        name=tipo_documento,

        exact=True

    )


    campo.wait_for(

        state="visible",

        timeout=3000

    )


    return campo


# ==========================================================
# ESPERAR RESULTADO DEL DOCUMENTO
#
# NIE Y DUI
#
# REVISA CADA 30 MS
# ==========================================================

def esperar_resultado_documento(
    page,
    timeout=6000
):

    try:

        resultado = page.wait_for_function(

            """
            () => {

                const texto =
                    document.body.innerText
                    .toLowerCase();


                // ==========================================
                // YA TIENE ASISTENCIA
                // ==========================================

                if (
                    texto.includes(
                        "el beneficiario ya tiene una asistencia registrada para esta jornada"
                    )
                    ||
                    texto.includes(
                        "ya tiene una asistencia registrada para esta jornada"
                    )
                    ||
                    texto.includes(
                        "asistencia registrada para esta jornada"
                    )
                    ||
                    texto.includes(
                        "ya existe una asistencia registrada en esta actividad"
                    )
                    ||
                    texto.includes(
                        "ya tiene una asistencia registrada en esta actividad"
                    )
                ) {

                    return "ya_registrada";

                }


                // ==========================================
                // NO ENCONTRADO
                // ==========================================

                if (
                    texto.includes(
                        "nie no encontrado"
                    )
                    ||
                    texto.includes(
                        "dui no encontrado"
                    )
                    ||
                    texto.includes(
                        "beneficiario no encontrado"
                    )
                    ||
                    texto.includes(
                        "documento no encontrado"
                    )
                    ||
                    texto.includes(
                        "no existe el beneficiario"
                    )
                    ||
                    texto.includes(
                        "no se encontró el nie"
                    )
                    ||
                    texto.includes(
                        "no se encontro el nie"
                    )
                    ||
                    texto.includes(
                        "no se encontró el dui"
                    )
                    ||
                    texto.includes(
                        "no se encontro el dui"
                    )
                ) {

                    return "no_encontrado";

                }


                // ==========================================
                // INVÁLIDO
                // ==========================================

                if (
                    texto.includes(
                        "documento inválido"
                    )
                    ||
                    texto.includes(
                        "documento invalido"
                    )
                    ||
                    texto.includes(
                        "nie inválido"
                    )
                    ||
                    texto.includes(
                        "nie invalido"
                    )
                    ||
                    texto.includes(
                        "dui inválido"
                    )
                    ||
                    texto.includes(
                        "dui invalido"
                    )
                ) {

                    return "invalido";

                }


                // ==========================================
                // BOTÓN DE ASISTENCIA
                // ==========================================

                const botones =
                    Array.from(
                        document.querySelectorAll(
                            "button"
                        )
                    );


                const boton =
                    botones.find(
                        b => {

                            const textoBoton =
                                b.innerText
                                .toLowerCase();


                            return textoBoton.includes(
                                "valida tu asistencia"
                            );

                        }
                    );


                if (!boton) {

                    return false;

                }


                const habilitado =

                    !boton.disabled

                    &&

                    boton.getAttribute(
                        "aria-disabled"
                    ) !== "true";


                if (habilitado) {

                    return "valido";

                }


                return false;

            }
            """,

            timeout=timeout,

            polling=30

        )


        return resultado.json_value()


    except PlaywrightTimeoutError:

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


    try:

        boton_asistencia.click()


    except Exception:

        return "error"


    try:

        resultado = page.wait_for_function(

            """
            () => {

                const texto =
                    document.body.innerText
                    .toLowerCase();


                // ==========================================
                // YA TENÍA ASISTENCIA
                // ==========================================

                if (
                    texto.includes(
                        "el beneficiario ya tiene una asistencia registrada para esta jornada"
                    )
                    ||
                    texto.includes(
                        "ya tiene una asistencia registrada para esta jornada"
                    )
                    ||
                    texto.includes(
                        "asistencia registrada para esta jornada"
                    )
                ) {

                    return "ya_registrada";

                }


                // ==========================================
                // ASISTENCIA EXITOSA
                // ==========================================

                if (
                    texto.includes(
                        "asistencia registrada correctamente"
                    )
                    ||
                    texto.includes(
                        "asistencia registrada con éxito"
                    )
                    ||
                    texto.includes(
                        "asistencia registrada con exito"
                    )
                    ||
                    texto.includes(
                        "asistencia validada correctamente"
                    )
                    ||
                    texto.includes(
                        "asistencia creada correctamente"
                    )
                    ||
                    texto.includes(
                        "asistencia enviada correctamente"
                    )
                    ||
                    texto.includes(
                        "asistencia guardada correctamente"
                    )
                ) {

                    return "enviada";

                }


                // ==========================================
                // ERROR
                // ==========================================

                if (
                    texto.includes(
                        "error al registrar la asistencia"
                    )
                    ||
                    texto.includes(
                        "no se pudo registrar la asistencia"
                    )
                ) {

                    return "error";

                }


                // ==========================================
                // PANTALLA DE CÓDIGO DESPUÉS DE ENVIAR
                // ==========================================

                if (
                    texto.includes(
                        "ya existe una asistencia registrada en este dispositivo"
                    )
                    ||
                    texto.includes(
                        "ingresa el código de verificación"
                    )
                    ||
                    texto.includes(
                        "ingresa el codigo de verificacion"
                    )
                ) {

                    return "enviada";

                }


                return false;

            }
            """,

            timeout=3500,

            polling=20

        )


        return resultado.json_value()


    except PlaywrightTimeoutError:

        texto = texto_de_pagina(
            page
        )


        if asistencia_ya_registrada(
            texto
        ):

            return "ya_registrada"


        if (

            "error al registrar la asistencia"
            in texto

            or

            "no se pudo registrar la asistencia"
            in texto

        ):

            return "error"


        return "sin_confirmacion"


# ==========================================================
# PREPARAR SIGUIENTE DOCUMENTO
# ==========================================================

def preparar_siguiente(
    page
):

    try:

        page.reload(
            wait_until="domcontentloaded"
        )


        return desbloquear_formulario(
            page
        )


    except Exception as error:

        print(

            "❌ Error preparando "
            "el siguiente documento:"

        )


        print(
            error
        )


        try:

            page.goto(

                URL,

                wait_until="domcontentloaded"

            )


            return desbloquear_formulario(
                page
            )


        except Exception:

            return False


# ==========================================================
# PLAYWRIGHT
# ==========================================================

with sync_playwright() as p:

    browser = None

    context = None


    try:

        # ==================================================
        # NAVEGADOR
        # ==================================================

        browser = p.chromium.launch(
            headless=HEADLESS
        )


        context = browser.new_context()


        page = context.new_page()


        page.set_default_timeout(
            6000
        )


        # ==================================================
        # ABRIR FORMULARIO
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


        page.goto(

            URL,

            wait_until="domcontentloaded"

        )


        # ==================================================
        # DESBLOQUEAR
        # ==================================================

        if not desbloquear_formulario(
            page
        ):

            print()

            print(
                "❌ No fue posible abrir el formulario."
            )

            sys.exit(1)


        # ==================================================
        # CONTADORES
        # ==================================================

        exitosos = 0

        ya_registradas = 0

        no_encontrados = 0

        omitidos = 0

        errores = 0


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

                f"ASISTENCIA {numero} "
                f"DE {len(personas)}"

            )


            print(
                "======================================"
            )


            # ==================================================
            # SOLO TOMAMOS ESTOS DOS DATOS
            #
            # TODO LO DEMÁS DEL JSON SE IGNORA.
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

                print()

                print(
                    "⚠️ TIPO DE DOCUMENTO INVÁLIDO"
                )


                print(

                    "Valor recibido:",

                    tipo_documento
                    if tipo_documento
                    else
                    "VACÍO"

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

                print()

                print(
                    "⚠️ REGISTRO SIN DOCUMENTO"
                )


                omitidos += 1


                continue


            # ==================================================
            # LOG COMPATIBLE
            # ==================================================

            print(

                f"{tipo_documento}:",

                documento

            )


            try:

                # ==================================================
                # FORMULARIO
                # ==================================================

                if not desbloquear_formulario(
                    page
                ):

                    print()

                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )


                    print(
                        "No se pudo acceder al formulario."
                    )


                    errores += 1


                    continue


                # ==================================================
                # SELECCIONAR NIE / DUI
                # ==================================================

                seleccionar_tipo_documento(

                    page,

                    tipo_documento

                )


                # ==================================================
                # CAMPO DEL DOCUMENTO
                # ==================================================

                campo_documento = obtener_campo_documento(

                    page,

                    tipo_documento

                )


                # ==================================================
                # ESCRIBIR
                # ==================================================

                campo_documento.fill(
                    documento
                )


                # ==================================================
                # VERIFICAR
                # ==================================================

                boton_verificar = page.get_by_role(
                    "button",
                    name="Verificar"
                )


                boton_verificar.wait_for(

                    state="visible",

                    timeout=2000

                )


                boton_verificar.click()


                print(

                    f"🔍 Verificando "
                    f"{tipo_documento}..."

                )


                # ==================================================
                # ESPERA RÁPIDA
                # ==================================================

                resultado = esperar_resultado_documento(

                    page,

                    timeout=6000

                )


                # ==================================================
                # YA TENÍA ASISTENCIA
                # ==================================================

                if resultado == "ya_registrada":

                    print()

                    print(
                        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
                    )


                    print(

                        f"{tipo_documento}:",

                        documento

                    )


                    ya_registradas += 1


                    print(
                        "➡️ Siguiente documento..."
                    )


                    if not preparar_siguiente(
                        page
                    ):

                        print(
                            "❌ ERROR EN EL REGISTRO"
                        )


                        errores += 1


                        break


                    continue


                # ==================================================
                # NO ENCONTRADO
                # ==================================================

                if resultado == "no_encontrado":

                    print()


                    if tipo_documento == "NIE":

                        print(
                            "🔎 NIE NO ENCONTRADO"
                        )


                    else:

                        print(
                            "🔎 DUI NO ENCONTRADO"
                        )


                    print(

                        f"{tipo_documento}:",

                        documento

                    )


                    no_encontrados += 1


                    print(
                        "➡️ Siguiente documento..."
                    )


                    if not preparar_siguiente(
                        page
                    ):

                        print(
                            "❌ ERROR EN EL REGISTRO"
                        )


                        errores += 1


                        break


                    continue


                # ==================================================
                # INVÁLIDO
                # ==================================================

                if resultado == "invalido":

                    print()


                    if tipo_documento == "NIE":

                        print(
                            "🔎 NIE NO ENCONTRADO"
                        )


                    else:

                        print(
                            "🔎 DUI NO ENCONTRADO"
                        )


                    print(
                        "Motivo: documento inválido."
                    )


                    no_encontrados += 1


                    if not preparar_siguiente(
                        page
                    ):

                        break


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

                        print()

                        print(
                            "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
                        )


                        ya_registradas += 1


                    elif (

                        documento_no_encontrado(
                            texto,
                            tipo_documento
                        )

                        or

                        documento_invalido(
                            texto,
                            tipo_documento
                        )

                    ):

                        print()


                        if tipo_documento == "NIE":

                            print(
                                "🔎 NIE NO ENCONTRADO"
                            )


                        else:

                            print(
                                "🔎 DUI NO ENCONTRADO"
                            )


                        no_encontrados += 1


                    else:

                        print()

                        print(
                            "❌ ERROR DE TIEMPO DE ESPERA"
                        )


                        print(

                            f"{tipo_documento}:",

                            documento

                        )


                        errores += 1


                    if not preparar_siguiente(
                        page
                    ):

                        break


                    continue


                # ==================================================
                # DOCUMENTO VÁLIDO
                # ==================================================

                if resultado != "valido":

                    print()

                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )


                    print(

                        "Respuesta desconocida al validar",

                        tipo_documento

                    )


                    errores += 1


                    preparar_siguiente(
                        page
                    )


                    continue


                print(

                    f"✅ {tipo_documento} VALIDADO"

                )


                # ==================================================
                # BOTÓN ASISTENCIA
                # ==================================================

                boton_asistencia = page.get_by_role(
                    "button",
                    name="Valida tu Asistencia"
                )


                boton_asistencia.wait_for(

                    state="visible",

                    timeout=2000

                )


                # ==================================================
                # ESPERAR A QUE SE HABILITE
                # ==================================================

                try:

                    page.wait_for_function(

                        """
                        () => {

                            const botones =
                                Array.from(
                                    document.querySelectorAll(
                                        "button"
                                    )
                                );


                            const boton =
                                botones.find(
                                    b =>
                                        b.innerText
                                        .toLowerCase()
                                        .includes(
                                            "valida tu asistencia"
                                        )
                                );


                            if (!boton) {

                                return false;

                            }


                            return (

                                !boton.disabled

                                &&

                                boton.getAttribute(
                                    "aria-disabled"
                                ) !== "true"

                            );

                        }
                        """,

                        timeout=3000,

                        polling=20

                    )


                except PlaywrightTimeoutError:

                    texto = texto_de_pagina(
                        page
                    )


                    if asistencia_ya_registrada(
                        texto
                    ):

                        print()

                        print(
                            "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
                        )


                        ya_registradas += 1


                    elif (

                        documento_no_encontrado(
                            texto,
                            tipo_documento
                        )

                        or

                        documento_invalido(
                            texto,
                            tipo_documento
                        )

                    ):

                        print()


                        if tipo_documento == "NIE":

                            print(
                                "🔎 NIE NO ENCONTRADO"
                            )


                        else:

                            print(
                                "🔎 DUI NO ENCONTRADO"
                            )


                        no_encontrados += 1


                    else:

                        print()

                        print(
                            "❌ ERROR EN EL REGISTRO"
                        )


                        print(

                            "El botón Valida tu Asistencia "
                            "no se habilitó."

                        )


                        errores += 1


                    if not preparar_siguiente(
                        page
                    ):

                        break


                    continue


                # ==================================================
                # ENVIAR
                # ==================================================

                resultado_envio = enviar_asistencia(

                    page,

                    boton_asistencia

                )


                # ==================================================
                # YA TENÍA
                # ==================================================

                if resultado_envio == "ya_registrada":

                    print()

                    print(
                        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
                    )


                    print(

                        f"{tipo_documento}:",

                        documento

                    )


                    ya_registradas += 1


                # ==================================================
                # ENVIADA
                # ==================================================

                elif resultado_envio == "enviada":

                    print()

                    print(
                        "✅ ASISTENCIA ENVIADA"
                    )


                    print(

                        f"{tipo_documento}:",

                        documento

                    )


                    exitosos += 1


                # ==================================================
                # ERROR
                # ==================================================

                elif resultado_envio == "error":

                    print()

                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )


                    print(

                        f"{tipo_documento}:",

                        documento

                    )


                    print(
                        "No se pudo registrar la asistencia."
                    )


                    errores += 1


                # ==================================================
                # SIN CONFIRMACIÓN
                # ==================================================

                else:

                    print()

                    print(
                        "❌ NO SE PUDO CONFIRMAR EL ENVÍO"
                    )


                    print(

                        f"{tipo_documento}:",

                        documento

                    )


                    errores += 1


                # ==================================================
                # SIGUIENTE
                # ==================================================

                print(
                    "🔄 Preparando siguiente..."
                )


                if not preparar_siguiente(
                    page
                ):

                    print()

                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )


                    print(

                        "No fue posible volver "
                        "al formulario."

                    )


                    errores += 1


                    break


                print(
                    "➡️ Listo para el siguiente documento."
                )


            # ======================================================
            # TIMEOUT PLAYWRIGHT
            # ======================================================

            except PlaywrightTimeoutError as error:

                print()

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


                try:

                    preparar_siguiente(
                        page
                    )


                except Exception:

                    pass


                continue


            # ======================================================
            # ERROR GENERAL
            # ======================================================

            except Exception as error:

                print()

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


                try:

                    preparar_siguiente(
                        page
                    )


                except Exception:

                    pass


                continue


        # ==========================================================
        # RESULTADO FINAL
        # ==========================================================

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

            "✅ Asistencias enviadas:",

            exitosos

        )


        print(

            "⚠️ Ya tenían asistencia:",

            ya_registradas

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
    # CERRAR AUTOMÁTICAMENTE
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