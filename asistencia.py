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
    print("❌ DAVIS no recibió el enlace de asistencia.")
    sys.exit(1)

if not CODIGO_VERIFICACION:
    print("❌ DAVIS no recibió el código de integración.")
    sys.exit(1)

if not ARCHIVO_JSON:
    print("❌ DAVIS no recibió el archivo JSON.")
    sys.exit(1)

if not os.path.exists(ARCHIVO_JSON):
    print("❌ No existe el archivo temporal:")
    print(ARCHIVO_JSON)
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

        personas = json.load(archivo)

except Exception as error:

    print()
    print("❌ ERROR LEYENDO EL JSON")
    print(error)

    sys.exit(1)


if not isinstance(personas, list):

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
print("======================================")
print("           SISTEMA DAVIS")
print("======================================")
print("MÓDULO: ASISTENCIA")
print()
print("Registros recibidos:", len(personas))
print("Enlace recibido correctamente.")
print("Código recibido: ********")
print("Navegador oculto:", HEADLESS)
print("======================================")


# ==========================================================
# NORMALIZAR TEXTO
# ==========================================================

def normalizar_texto(texto):

    texto = str(texto).lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    return texto


# ==========================================================
# OBTENER TEXTO DE PÁGINA
# ==========================================================

def texto_de_pagina(page):

    try:

        return normalizar_texto(
            page.locator("body").inner_text()
        )

    except Exception:

        return ""


# ==========================================================
# ESPERAR FORMULARIO O PANTALLA DE CÓDIGO
#
# NO USA ESPERAS FIJAS.
# REVISA CADA 30 MILISEGUNDOS.
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


                // PANTALLA DE CÓDIGO

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


                // BUSCAR CAMPO NIE

                const inputs =
                    Array.from(
                        document.querySelectorAll("input")
                    );


                const campoNIE =
                    inputs.find(input => {

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
                                input.getAttribute("placeholder")
                                || ""
                            ).toLowerCase();


                        const aria =
                            (
                                input.getAttribute("aria-label")
                                || ""
                            ).toLowerCase();


                        return (
                            visible
                            &&
                            (
                                placeholder.includes("nie")
                                ||
                                aria.includes("nie")
                            )
                        );

                    });


                if (campoNIE) {
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

        # Intento adicional usando Playwright
        try:

            campo_nie = page.get_by_role(
                "textbox",
                name="NIE"
            )

            if campo_nie.is_visible():
                return "formulario"

        except Exception:
            pass


        return "timeout"


# ==========================================================
# DESBLOQUEAR FORMULARIO
# ==========================================================

def desbloquear_formulario(page):

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
    print("======================================")
    print("🔐 DESBLOQUEANDO FORMULARIO")
    print("======================================")
    print("Código recibido desde DAVIS: ********")


    try:

        # ==================================================
        # CAMPOS INDIVIDUALES
        # ==================================================

        campos = page.locator(
            'input[maxlength="1"]:visible'
        )


        campos.first.wait_for(
            state="visible",
            timeout=3000
        )


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

            for i, caracter in enumerate(
                CODIGO_VERIFICACION
            ):

                campos.nth(i).fill(
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


            for i in range(
                inputs.count()
            ):

                campo = inputs.nth(i)


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


            if len(candidatos) < len(
                CODIGO_VERIFICACION
            ):

                print(
                    "❌ No se encontraron suficientes "
                    "campos para el código."
                )

                return False


            for i, caracter in enumerate(
                CODIGO_VERIFICACION
            ):

                candidatos[i].fill(
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
        # ESPERAR SOLO HASTA QUE SE HABILITE
        # ==================================================

        page.wait_for_function(
            """
            () => {

                const botones =
                    Array.from(
                        document.querySelectorAll("button")
                    );


                const boton =
                    botones.find(b => {

                        const texto =
                            b.innerText
                            .toLowerCase();

                        return (
                            texto.includes("validar código")
                            ||
                            texto.includes("validar codigo")
                        );

                    });


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
        # ESPERAR CAMPO NIE DIRECTAMENTE
        # ==================================================

        campo_nie = page.get_by_role(
            "textbox",
            name="NIE"
        )


        campo_nie.wait_for(
            state="visible",
            timeout=5000
        )


        print(
            "✅ Formulario desbloqueado."
        )


        return True


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

        print(error)

        return False


# ==========================================================
# SELECCIONAR NIE
# ==========================================================

def seleccionar_nie(page):

    try:

        selector = page.get_by_role(
            "combobox",
            name="Tipo de documento"
        )


        if not selector.is_visible():

            return


        # ==================================================
        # SI ES SELECT HTML NATIVO
        # ==================================================

        try:

            tag = selector.evaluate(
                "(el) => el.tagName.toLowerCase()"
            )


            if tag == "select":

                opciones = selector.locator(
                    "option"
                )


                for i in range(
                    opciones.count()
                ):

                    opcion = opciones.nth(i)

                    texto = normalizar_texto(
                        opcion.inner_text()
                    )


                    if texto == "nie":

                        valor = opcion.get_attribute(
                            "value"
                        )

                        selector.select_option(
                            valor
                        )

                        return

        except Exception:

            pass


        # ==================================================
        # SELECT PERSONALIZADO
        # ==================================================

        try:

            valor = normalizar_texto(
                selector.input_value()
            )


            if valor == "nie":

                return

        except Exception:

            pass


        selector.click()


        opcion_nie = page.get_by_text(
            "NIE",
            exact=True
        ).last


        opcion_nie.wait_for(
            state="visible",
            timeout=1500
        )


        opcion_nie.click()


    except Exception:

        # Si no existe selector, se supone que
        # el formulario ya trabaja con NIE.
        pass


# ==========================================================
# ESPERAR RESULTADO DEL NIE
#
# ESTA ES LA PARTE RÁPIDA.
#
# NO ESPERA 1.2 SEGUNDOS.
# APENAS APARECE EL RESULTADO CONTINÚA.
# ==========================================================

def esperar_resultado_nie(
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
                // NIE NO ENCONTRADO
                // ==========================================

                if (
                    texto.includes(
                        "nie no encontrado"
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
                ) {

                    return "no_encontrado";

                }


                // ==========================================
                // NIE INVÁLIDO
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
                ) {

                    return "invalido";

                }


                // ==========================================
                // BOTÓN DE ASISTENCIA
                // ==========================================

                const botones =
                    Array.from(
                        document.querySelectorAll("button")
                    );


                const boton =
                    botones.find(b => {

                        const textoBoton =
                            b.innerText
                            .toLowerCase();

                        return textoBoton.includes(
                            "valida tu asistencia"
                        );

                    });


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

            # REVISA CADA 30 MS
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


    # ======================================================
    # ESPERAR RESULTADO INMEDIATAMENTE
    # ======================================================

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
                // DESPUÉS DE ENVIAR PUEDE VOLVER
                // A LA PANTALLA DE CÓDIGO
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

        # ==================================================
        # REVISIÓN FINAL
        # ==================================================

        texto = texto_de_pagina(
            page
        )


        if (
            "el beneficiario ya tiene una asistencia registrada para esta jornada"
            in texto
            or
            "ya tiene una asistencia registrada para esta jornada"
            in texto
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
# PREPARAR SIGUIENTE NIE
# ==========================================================

def preparar_siguiente(page):

    try:

        # ==================================================
        # RECARGAR DIRECTAMENTE
        # ==================================================

        page.reload(
            wait_until="domcontentloaded"
        )


        # ==================================================
        # SI PIDE CÓDIGO, LO COLOCA DE INMEDIATO
        # ==================================================

        return desbloquear_formulario(
            page
        )


    except Exception as error:

        print(
            "❌ Error preparando el siguiente NIE:"
        )

        print(
            error
        )


        # ==================================================
        # INTENTO DE RECUPERACIÓN
        # ==================================================

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
        # ABRIR NAVEGADOR
        # ==================================================

        browser = p.chromium.launch(
            headless=HEADLESS
        )


        context = browser.new_context()


        page = context.new_page()


        # ==================================================
        # TIMEOUT GENERAL
        # ==================================================

        page.set_default_timeout(
            6000
        )


        # ==================================================
        # ABRIR FORMULARIO
        # ==================================================

        print()
        print("======================================")
        print("ABRIENDO FORMULARIO")
        print("======================================")


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
        errores = 0


        # ==================================================
        # RECORRER PERSONAS
        # ==================================================

        for numero, persona in enumerate(
            personas,
            start=1
        ):


            print()
            print("======================================")

            print(
                f"ASISTENCIA {numero} DE {len(personas)}"
            )

            print("======================================")


            # ==================================================
            # DOCUMENTO
            # ==================================================

            documento = str(
                persona.get(
                    "documento",
                    ""
                )
            ).strip()


            print(
                "NIE:",
                documento if documento else "VACÍO"
            )


            # ==================================================
            # SIN NIE = ERROR
            # ==================================================

            if not documento:

                print()
                print(
                    "❌ ERROR EN EL REGISTRO"
                )

                print(
                    "Registro sin NIE."
                )


                errores += 1

                continue


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
                # ASEGURAR NIE
                # ==================================================

                seleccionar_nie(
                    page
                )


                # ==================================================
                # CAMPO NIE
                # ==================================================

                campo_nie = page.get_by_role(
                    "textbox",
                    name="NIE"
                )


                campo_nie.wait_for(
                    state="visible",
                    timeout=3000
                )


                # ==================================================
                # ESCRIBIR NIE INMEDIATAMENTE
                # ==================================================

                campo_nie.fill(
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
                    "🔍 Verificando NIE..."
                )


                # ==================================================
                # ESPERA RÁPIDA DEL RESULTADO
                # ==================================================

                resultado = esperar_resultado_nie(
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


                    ya_registradas += 1


                    print(
                        "➡️ Siguiente NIE..."
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
                    print(
                        "🔎 NIE NO ENCONTRADO"
                    )


                    no_encontrados += 1


                    print(
                        "➡️ Siguiente NIE..."
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
                # NIE INVÁLIDO
                # ==================================================

                if resultado == "invalido":

                    print()
                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )

                    print(
                        "NIE inválido."
                    )


                    errores += 1


                    if not preparar_siguiente(
                        page
                    ):

                        break


                    continue


                # ==================================================
                # TIMEOUT
                # ==================================================

                if resultado == "timeout":

                    print()
                    print(
                        "❌ ERROR DE TIEMPO DE ESPERA"
                    )

                    print(
                        "El sistema tardó demasiado "
                        "en validar este NIE."
                    )


                    errores += 1


                    if not preparar_siguiente(
                        page
                    ):

                        break


                    continue


                # ==================================================
                # NIE VÁLIDO
                # ==================================================

                if resultado != "valido":

                    print()
                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )

                    print(
                        "Respuesta desconocida al validar NIE."
                    )


                    errores += 1


                    preparar_siguiente(
                        page
                    )


                    continue


                print(
                    "✅ NIE VALIDADO"
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
                # ENVIAR
                # ==================================================

                resultado_envio = enviar_asistencia(
                    page,
                    boton_asistencia
                )


                # ==================================================
                # YA TENÍA ASISTENCIA
                # ==================================================

                if resultado_envio == "ya_registrada":

                    print()
                    print(
                        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
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
                        "No fue posible volver al formulario."
                    )


                    errores += 1

                    break


                print(
                    "➡️ Siguiente NIE..."
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
                    "NIE:",
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
                    "NIE:",
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
        print("======================================")
        print("          PROCESO FINALIZADO")
        print("======================================")

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
            "🔎 NIE no encontrados:",
            no_encontrados
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