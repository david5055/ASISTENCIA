import os
import sys
import json
import re

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
# CONFIGURACIÓN RECIBIDA DESDE DAVIS
# ==========================================================

URL = os.getenv("DAVIS_ASISTENCIA_URL", "").strip()
CODIGO_VERIFICACION = os.getenv("DAVIS_CODIGO_INTEGRACION", "").strip()
ARCHIVO_JSON = os.getenv("DAVIS_ARCHIVO_JSON", "").strip()

HEADLESS = os.getenv(
    "HEADLESS",
    "false",
).strip().lower() == "true"


# ==========================================================
# TIEMPOS MÁXIMOS DE SEGURIDAD
#
# NO SON PAUSAS ENTRE PERSONAS.
# EN CUANTO APARECE EL RESULTADO, DAVIS CONTINÚA.
# ==========================================================

TIMEOUT_FORMULARIO = 7000
TIMEOUT_ELEMENTO = 5000
TIMEOUT_VALIDACION = 6000
TIMEOUT_ENVIO = 3500
POLLING = 20


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
    print("❌ DAVIS no recibió el archivo temporal de datos.")
    sys.exit(1)

if not os.path.exists(ARCHIVO_JSON):
    print("❌ No existe el archivo temporal:")
    print(ARCHIVO_JSON)
    sys.exit(1)


# ==========================================================
# LEER DATOS
#
# El usuario puede:
# - pegar JSON
# - subir JSON
# - subir CSV
#
# app.py / data_loader / asistencia_service convierten todo
# a una lista y el service crea este JSON temporal.
# ==========================================================

try:
    with open(
        ARCHIVO_JSON,
        "r",
        encoding="utf-8",
    ) as archivo:
        personas = json.load(archivo)

except Exception as error:
    print("❌ ERROR LEYENDO LOS DATOS DE ASISTENCIA")
    print(error)
    sys.exit(1)


if not isinstance(personas, list):
    print("❌ Los datos de asistencia deben ser una lista.")
    sys.exit(1)

if not personas:
    print("❌ No hay personas para procesar.")
    sys.exit(1)


# ==========================================================
# INFORMACIÓN INICIAL
# ==========================================================

print()
print("======================================")
print("SISTEMA DAVIS - ASISTENCIA")
print("======================================")
print("Registros recibidos:", len(personas))
print("Enlace recibido correctamente.")
print("Código recibido: ********")
print("Navegador oculto:", HEADLESS)
print("======================================")


# ==========================================================
# TEXTO DE PÁGINA
# ==========================================================

def texto_pagina(page):
    try:
        return (
            page.locator("body")
            .inner_text(timeout=1000)
            .lower()
        )
    except Exception:
        return ""


# ==========================================================
# ESTADO DEL FORMULARIO
#
# formulario:
#   Tipo de documento + Verificar
#
# bloqueado:
#   pantalla de código de verificación
# ==========================================================

def esperar_estado_formulario(
    page,
    timeout=TIMEOUT_FORMULARIO,
):
    """
    Detecta el portal de forma amplia.

    IMPORTANTE:
    - No espera un tiempo fijo.
    - En cuanto encuentra formulario o código, continúa.
    - Evita el error donde Chromium abría correctamente
      pero DAVIS no reconocía la pantalla y cerraba el proceso.
    """

    try:
        resultado = page.wait_for_function(
            """
            () => {
                const visible = (el) => {
                    if (!el) {
                        return false;
                    }

                    const estilo =
                        window.getComputedStyle(el);

                    return (
                        estilo.display !== "none"
                        &&
                        estilo.visibility !== "hidden"
                        &&
                        (
                            el.offsetWidth
                            ||
                            el.offsetHeight
                            ||
                            el.getClientRects().length
                        )
                    );
                };


                const texto =
                    (document.body?.innerText || "")
                    .toLowerCase();


                // ==========================================
                // 1. PANTALLA DEL CÓDIGO
                // ==========================================

                const textoCodigo =
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
                        "validar código"
                    )
                    ||
                    texto.includes(
                        "validar codigo"
                    );


                const camposCodigo =
                    Array.from(
                        document.querySelectorAll(
                            'input[maxlength="1"]'
                        )
                    ).filter(visible);


                if (
                    textoCodigo
                    ||
                    camposCodigo.length >= 4
                ) {
                    return "bloqueado";
                }


                // ==========================================
                // 2. FORMULARIO
                // ==========================================

                const botones =
                    Array.from(
                        document.querySelectorAll(
                            "button"
                        )
                    ).filter(visible);


                const botonVerificar =
                    botones.some(
                        b =>
                            (b.innerText || "")
                            .trim()
                            .toLowerCase()
                            === "verificar"
                    );


                const combos =
                    Array.from(
                        document.querySelectorAll(
                            '[role="combobox"], select'
                        )
                    ).filter(visible);


                const inputs =
                    Array.from(
                        document.querySelectorAll(
                            "input"
                        )
                    ).filter(visible);


                const campoDocumento =
                    inputs.some(
                        input => {
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
                                placeholder.includes("nie")
                                ||
                                placeholder.includes(
                                    "12345678-9"
                                )
                                ||
                                aria === "nie"
                                ||
                                aria === "dui"
                            );
                        }
                    );


                const labels =
                    Array.from(
                        document.querySelectorAll(
                            "label"
                        )
                    ).filter(visible);


                const labelDocumento =
                    labels.some(
                        label => {
                            const t =
                                (
                                    label.innerText
                                    ||
                                    label.textContent
                                    ||
                                    ""
                                )
                                .replace("*", "")
                                .trim()
                                .toLowerCase();

                            return (
                                t === "nie"
                                ||
                                t === "dui"
                                ||
                                t === "tipo de documento"
                            );
                        }
                    );


                const textoFormulario =
                    texto.includes(
                        "tipo de documento"
                    )
                    ||
                    texto.includes(
                        "verifica tu asistencia"
                    )
                    ||
                    texto.includes(
                        "valida tu asistencia"
                    );


                if (
                    botonVerificar
                    ||
                    combos.length > 0
                    ||
                    campoDocumento
                    ||
                    labelDocumento
                    ||
                    textoFormulario
                ) {
                    return "formulario";
                }


                return false;
            }
            """,
            timeout=timeout,
            polling=POLLING,
        )

        return resultado.json_value()

    except PlaywrightTimeoutError:
        return "timeout"

# ==========================================================
# INGRESAR CÓDIGO DE VERIFICACIÓN
# ==========================================================

def ingresar_codigo(page):
    print()
    print("======================================")
    print("🔐 DESBLOQUEANDO FORMULARIO")
    print("======================================")

    try:
        campos = page.locator(
            'input[maxlength="1"]:visible'
        )

        campos.first.wait_for(
            state="visible",
            timeout=TIMEOUT_ELEMENTO,
        )

        cantidad = campos.count()

        # ==================================================
        # MÉTODO PRINCIPAL:
        # campos maxlength=1
        # ==================================================

        if cantidad >= len(CODIGO_VERIFICACION):
            for indice, caracter in enumerate(
                CODIGO_VERIFICACION
            ):
                campos.nth(indice).fill(
                    caracter
                )

        # ==================================================
        # FALLBACK:
        # inputs pequeños visibles
        # ==================================================

        else:
            inputs = page.locator(
                "input:visible"
            )

            candidatos = []

            for indice in range(
                inputs.count()
            ):
                campo = inputs.nth(indice)

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
                    "❌ No se encontraron "
                    "los campos del código."
                )
                return False

            for indice, caracter in enumerate(
                CODIGO_VERIFICACION
            ):
                candidatos[indice].fill(
                    caracter
                )

        print("✅ Código ingresado.")

        # ==================================================
        # BOTÓN VALIDAR CÓDIGO
        # ==================================================

        try:
            boton_codigo = page.get_by_role(
                "button",
                name=re.compile(
                    r"validar\s*c[oó]digo",
                    re.IGNORECASE,
                ),
            ).first

            boton_codigo.wait_for(
                state="visible",
                timeout=TIMEOUT_ELEMENTO,
            )

        except Exception:
            boton_codigo = page.locator(
                "button:visible"
            ).filter(
                has_text=re.compile(
                    r"validar\s*c[oó]digo",
                    re.IGNORECASE,
                )
            ).first

            boton_codigo.wait_for(
                state="visible",
                timeout=TIMEOUT_ELEMENTO,
            )

        # ==================================================
        # ESPERAR QUE SE HABILITE
        # ==================================================

        page.wait_for_function(
            """
            () => {
                const botones =
                    Array.from(
                        document.querySelectorAll("button")
                    );

                const boton =
                    botones.find(
                        b => {
                            const t =
                                (b.innerText || "")
                                .toLowerCase();

                            return (
                                t.includes(
                                    "validar código"
                                )
                                ||
                                t.includes(
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
            timeout=TIMEOUT_ELEMENTO,
            polling=POLLING,
        )

        boton_codigo.click()

        print("🔓 Validando código...")

        # ==================================================
        # EN CUANTO VUELVE EL FORMULARIO, CONTINÚA
        # ==================================================

        estado = esperar_estado_formulario(
            page,
            timeout=TIMEOUT_FORMULARIO,
        )

        if estado == "formulario":
            print(
                "✅ Formulario desbloqueado."
            )
            return True

        texto = texto_pagina(page)

        if (
            "código incorrecto" in texto
            or
            "codigo incorrecto" in texto
            or
            "código inválido" in texto
            or
            "codigo invalido" in texto
        ):
            print("❌ Código incorrecto.")
        else:
            print(
                "❌ No apareció el formulario "
                "después de validar el código."
            )

        return False

    except PlaywrightTimeoutError:
        print(
            "❌ El portal tardó demasiado "
            "al desbloquear el formulario."
        )
        return False

    except Exception as error:
        print(
            "❌ Error desbloqueando formulario:"
        )
        print(error)
        return False


# ==========================================================
# DESBLOQUEAR SI ES NECESARIO
# ==========================================================

def desbloquear_formulario(page):
    estado = esperar_estado_formulario(
        page
    )

    if estado == "formulario":
        return True

    if estado == "bloqueado":
        return ingresar_codigo(
            page
        )

    print(
        "❌ No apareció el formulario "
        "ni la pantalla del código."
    )
    return False


# ==========================================================
# CAMPO NIE
#
# IMPORTANTE:
# SI EL REGISTRO ES NIE, NO SE TOCA EL DESPLEGABLE.
# ==========================================================

def obtener_campo_nie(page):
    # Método que funcionaba en la versión original.
    try:
        campo = page.get_by_role(
            "textbox",
            name="NIE",
        )

        campo.wait_for(
            state="visible",
            timeout=TIMEOUT_ELEMENTO,
        )

        return campo

    except Exception:
        pass

    # Fallback por label.
    try:
        campo = page.get_by_label(
            re.compile(
                r"^\s*\*?\s*NIE\s*$",
                re.IGNORECASE,
            )
        ).first

        campo.wait_for(
            state="visible",
            timeout=TIMEOUT_ELEMENTO,
        )

        return campo

    except Exception:
        pass

    # Fallback por label visible -> input siguiente.
    labels = page.locator(
        "label:visible"
    )

    for indice in range(
        labels.count()
    ):
        label = labels.nth(indice)

        try:
            texto = (
                label.inner_text(
                    timeout=300
                )
                or
                ""
            )

            limpio = (
                texto
                .replace("*", "")
                .strip()
                .upper()
            )

            if limpio != "NIE":
                continue

            for_id = label.get_attribute(
                "for"
            )

            if for_id:
                campo = page.locator(
                    f'#{for_id}:visible'
                )

                if campo.count():
                    return campo.first

            padre = label.locator(
                "xpath=.."
            )

            campo = padre.locator(
                "input:visible"
            )

            if campo.count():
                return campo.first

            campo = label.locator(
                "xpath=following::input[1]"
            )

            if (
                campo.count()
                and
                campo.first.is_visible()
            ):
                return campo.first

        except Exception:
            continue

    raise Exception(
        "No apareció el campo NIE."
    )


# ==========================================================
# CAMPO DUI
#
# EN EL FORMULARIO EL PLACEHOLDER ES:
# "Ej: 12345678-9"
# ==========================================================

def obtener_campo_dui(page):
    """
    Selector obtenido directamente con Playwright Codegen
    del formulario real.

    Codegen registró:
        page.get_by_role(
            "textbox",
            name="Ej: 12345678-"
        )

    Usamos regex para tolerar que el nombre accesible
    continúe con más caracteres.
    """

    # ======================================================
    # MÉTODO EXACTO OBTENIDO DEL CODEGEN
    # ======================================================

    try:
        campo = page.get_by_role(
            "textbox",
            name=re.compile(
                r"^Ej:\s*12345678-",
                re.IGNORECASE,
            ),
        ).first

        campo.wait_for(
            state="visible",
            timeout=TIMEOUT_ELEMENTO,
        )

        return campo

    except Exception:
        pass

    # ======================================================
    # FALLBACK POR PLACEHOLDER
    # ======================================================

    try:
        campo = page.locator(
            'input[placeholder^="Ej: 12345678-"]:visible'
        ).first

        campo.wait_for(
            state="visible",
            timeout=TIMEOUT_ELEMENTO,
        )

        return campo

    except Exception:
        pass

    # ======================================================
    # FALLBACK POR LABEL DUI
    # ======================================================

    try:
        campo = page.get_by_label(
            re.compile(
                r"^\s*\*?\s*DUI\s*$",
                re.IGNORECASE,
            )
        ).first

        campo.wait_for(
            state="visible",
            timeout=TIMEOUT_ELEMENTO,
        )

        return campo

    except Exception:
        pass

    raise Exception(
        "DUI fue seleccionado, "
        "pero no apareció el campo "
        "'Ej: 12345678-'."
    )

# ==========================================================
# SELECCIONAR DUI
#
# SOLO SE LLAMA PARA tipo_documento == "DUI".
#
# NIE:
#   NO TOCA EL DESPLEGABLE.
#
# DUI:
#   abre la lista y hace click EXACTO en DUI.
#
# NO SE USAN FLECHAS.
# NO SE SELECCIONA "Código Integración".
# ==========================================================

def seleccionar_dui(page):
    """
    Usa EXACTAMENTE la interacción grabada por
    Playwright Codegen en el formulario real:

        page.locator('[id="_r_0_"]').click()
        page.get_by_title("DUI").locator("div").click()

    No usa ArrowDown.
    No hace clic en Código Integración.
    Apenas aparece el campo DUI, continúa.
    """

    print(
        "📄 Seleccionando tipo de documento: DUI"
    )

    # ======================================================
    # 1. ABRIR DESPLEGABLE
    #
    # SELECTOR EXACTO DEL CODEGEN
    # ======================================================

    desplegable_abierto = False

    try:
        desplegable = page.locator(
            '[id="_r_0_"]'
        )

        desplegable.wait_for(
            state="visible",
            timeout=TIMEOUT_ELEMENTO,
        )

        desplegable.click()

        desplegable_abierto = True

    except Exception:
        desplegable_abierto = False

    # ======================================================
    # FALLBACK SI EL ID AUTOGENERADO CAMBIA
    # ======================================================

    if not desplegable_abierto:
        try:
            desplegable = page.get_by_role(
                "combobox",
                name=re.compile(
                    r"tipo\s+de\s+documento",
                    re.IGNORECASE,
                ),
            ).first

            desplegable.wait_for(
                state="visible",
                timeout=TIMEOUT_ELEMENTO,
            )

            desplegable.click()

            desplegable_abierto = True

        except Exception:
            pass

    if not desplegable_abierto:
        try:
            desplegable = page.locator(
                '[role="combobox"]:visible'
            ).first

            desplegable.wait_for(
                state="visible",
                timeout=TIMEOUT_ELEMENTO,
            )

            desplegable.click()

            desplegable_abierto = True

        except Exception:
            pass

    if not desplegable_abierto:
        raise Exception(
            "No se pudo abrir "
            "Tipo de documento."
        )

    # ======================================================
    # 2. CLICK EXACTO EN DUI
    #
    # SELECTOR EXACTO DEL CODEGEN:
    #
    # page.get_by_title("DUI").locator("div").click()
    # ======================================================

    try:
        opcion_dui = page.get_by_title(
            "DUI"
        ).locator(
            "div"
        ).first

        opcion_dui.wait_for(
            state="visible",
            timeout=TIMEOUT_ELEMENTO,
        )

        opcion_dui.click()

    except Exception:
        # ==================================================
        # FALLBACK CONSERVANDO EL MISMO title="DUI"
        # ==================================================

        try:
            opcion_dui = page.get_by_title(
                "DUI"
            ).first

            opcion_dui.wait_for(
                state="visible",
                timeout=TIMEOUT_ELEMENTO,
            )

            opcion_dui.click(
                force=True
            )

        except Exception as error:
            raise Exception(
                "Se abrió Tipo de documento, "
                "pero no se pudo hacer clic "
                "en la opción DUI. "
                f"{error}"
            )

    # ======================================================
    # 3. ESPERAR ÚNICAMENTE A QUE APAREZCA EL CAMPO DUI
    #
    # NO HAY PAUSA FIJA.
    # ======================================================

    obtener_campo_dui(
        page
    )

    print(
        "✅ DUI seleccionado."
    )

    return True

# ==========================================================
# BOTÓN VERIFICAR
# ==========================================================

def obtener_boton_verificar(page):
    boton = page.get_by_role(
        "button",
        name="Verificar",
        exact=True,
    ).first

    boton.wait_for(
        state="visible",
        timeout=TIMEOUT_ELEMENTO,
    )

    return boton


# ==========================================================
# ESPERAR RESULTADO DE VERIFICACIÓN
# ==========================================================

def esperar_resultado_documento(
    page,
    tipo_documento,
):
    tipo = tipo_documento.lower()

    try:
        resultado = page.wait_for_function(
            """
            ([tipo]) => {
                const texto =
                    (document.body?.innerText || "")
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
                ) {
                    return "ya_registrada";
                }

                // ==========================================
                // PERSONA / DOCUMENTO NO EXISTE
                // ==========================================

                if (
                    texto.includes(
                        "la persona no existe"
                    )
                    ||
                    texto.includes(
                        "persona no existe"
                    )
                    ||
                    texto.includes(
                        "persona no encontrada"
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
                        tipo + " no encontrado"
                    )
                    ||
                    texto.includes(
                        "no se encontró"
                    )
                    ||
                    texto.includes(
                        "no se encontro"
                    )
                ) {
                    return "no_encontrado";
                }

                // ==========================================
                // DOCUMENTO INVÁLIDO
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
                        tipo + " inválido"
                    )
                    ||
                    texto.includes(
                        tipo + " invalido"
                    )
                ) {
                    return "invalido";
                }

                // ==========================================
                // DOCUMENTO VÁLIDO:
                // "Valida tu Asistencia" habilitado
                // ==========================================

                const botones =
                    Array.from(
                        document.querySelectorAll("button")
                    );

                const boton =
                    botones.find(
                        b =>
                            (b.innerText || "")
                            .toLowerCase()
                            .includes(
                                "valida tu asistencia"
                            )
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
            arg=[tipo],
            timeout=TIMEOUT_VALIDACION,
            polling=POLLING,
        )

        return resultado.json_value()

    except PlaywrightTimeoutError:
        return "timeout"


# ==========================================================
# ENVIAR ASISTENCIA
# ==========================================================

def enviar_asistencia(
    page,
    boton_asistencia,
):
    print(
        "📤 Enviando asistencia..."
    )

    try:
        boton_asistencia.click()
    except Exception as error:
        print(
            "❌ No se pudo hacer clic "
            "en Valida tu Asistencia:"
        )
        print(error)
        return "error"

    try:
        resultado = page.wait_for_function(
            """
            () => {
                const texto =
                    (document.body?.innerText || "")
                    .toLowerCase();

                // Duplicado
                if (
                    texto.includes(
                        "el beneficiario ya tiene una asistencia registrada para esta jornada"
                    )
                    ||
                    texto.includes(
                        "ya tiene una asistencia registrada para esta jornada"
                    )
                ) {
                    return "ya_registrada";
                }

                // Éxito explícito
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
                ) {
                    return "enviada";
                }

                // Después de enviar, el portal puede
                // regresar a la pantalla del código.
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

                // Error explícito
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

                return false;
            }
            """,
            timeout=TIMEOUT_ENVIO,
            polling=POLLING,
        )

        return resultado.json_value()

    except PlaywrightTimeoutError:
        texto = texto_pagina(
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

        # Conserva la lógica del script original:
        # si el clic ocurrió y no apareció un error,
        # se considera enviado.
        return "enviada"


# ==========================================================
# PREPARAR SIGUIENTE PERSONA
#
# MISMA LÓGICA DEL SCRIPT QUE FUNCIONABA:
# RECARGAR -> SI PIDE CÓDIGO -> VALIDAR -> FORMULARIO.
#
# NO HAY PAUSA FIJA ENTRE PERSONAS.
# ==========================================================

def preparar_siguiente(page):
    try:
        page.reload(
            wait_until="domcontentloaded",
            timeout=15000,
        )

        if desbloquear_formulario(
            page
        ):
            return True

        # Fallback único.
        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=15000,
        )

        return desbloquear_formulario(
            page
        )

    except Exception as error:
        print(
            "❌ Error preparando "
            "el siguiente documento:"
        )
        print(error)
        return False



# ==========================================================
# DIAGNÓSTICO DE PÁGINA
# ==========================================================

def imprimir_diagnostico_pagina(page):
    try:
        print("URL REAL:", page.url)
    except Exception:
        pass

    try:
        print("TÍTULO:", page.title())
    except Exception:
        pass

    try:
        texto = page.locator(
            "body"
        ).inner_text(
            timeout=1500
        )

        print("TEXTO VISIBLE:")
        print(
            texto[:1500]
        )

    except Exception as error:
        print(
            "No se pudo leer la página:",
            error
        )


# ==========================================================
# ABRIR FORMULARIO INICIAL
#
# NO CIERRA CHROMIUM POR UN FALSO TIMEOUT.
# HACE VARIOS INTENTOS Y CONTINÚA APENAS DETECTA
# FORMULARIO O PANTALLA DEL CÓDIGO.
# ==========================================================

def abrir_formulario_inicial(page):
    for intento in range(
        1,
        4,
    ):
        try:
            if intento == 1:
                print(
                    "🌐 Abriendo enlace de asistencia..."
                )
            else:
                print(
                    f"🔄 Reintentando apertura "
                    f"({intento}/3)..."
                )

            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=20000,
            )

            estado = esperar_estado_formulario(
                page,
                timeout=10000,
            )

            if estado == "formulario":
                print(
                    "✅ Formulario detectado."
                )
                return True

            if estado == "bloqueado":
                if ingresar_codigo(
                    page
                ):
                    print(
                        "✅ Formulario listo."
                    )
                    return True

        except Exception as error:
            print(
                f"⚠️ Intento {intento}/3:",
                error
            )

    print()
    print(
        "======================================"
    )
    print(
        "DIAGNÓSTICO DE APERTURA"
    )
    print(
        "======================================"
    )

    imprimir_diagnostico_pagina(
        page
    )

    print(
        "======================================"
    )

    return False


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
        # ABRIR FORMULARIO
        # ==================================================

        print()
        print("======================================")
        print("ABRIENDO FORMULARIO")
        print("======================================")

        if not abrir_formulario_inicial(
            page
        ):
            print(
                "❌ No fue posible abrir "
                "el formulario después de 3 intentos."
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
        # RECORRER TODAS LAS PERSONAS
        # ==================================================

        for numero, persona in enumerate(
            personas,
            start=1,
        ):
            print()
            print("======================================")
            print(
                f"ASISTENCIA {numero} "
                f"DE {len(personas)}"
            )
            print("======================================")

            tipo_documento = str(
                persona.get(
                    "tipo_documento",
                    "NIE",
                )
                or
                "NIE"
            ).strip().upper()

            documento = str(
                persona.get(
                    "documento",
                    "",
                )
                or
                ""
            ).strip()

            print(
                "TIPO_DOCUMENTO:",
                tipo_documento,
            )

            print(
                "DOCUMENTO:",
                documento
                if documento
                else
                "VACÍO",
            )

            # ==================================================
            # VALIDACIONES
            # ==================================================

            if tipo_documento not in (
                "NIE",
                "DUI",
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
                # NIE:
                # NO TOCA EL DESPLEGABLE.
                # ==================================================

                if tipo_documento == "NIE":
                    campo_documento = obtener_campo_nie(
                        page
                    )

                # ==================================================
                # DUI:
                # CLICK EXACTO EN DUI Y BUSCAR INPUT DUI.
                # ==================================================

                else:
                    seleccionar_dui(
                        page
                    )

                    campo_documento = obtener_campo_dui(
                        page
                    )

                # ==================================================
                # ESCRIBIR DOCUMENTO
                # ==================================================

                campo_documento.fill(
                    documento
                )

                print(
                    f"{tipo_documento}:",
                    documento,
                )

                # ==================================================
                # VERIFICAR
                # ==================================================

                boton_verificar = obtener_boton_verificar(
                    page
                )

                boton_verificar.click()

                print(
                    f"🔍 Verificando "
                    f"{tipo_documento}..."
                )

                resultado = esperar_resultado_documento(
                    page,
                    tipo_documento,
                )

                # ==================================================
                # YA TENÍA ASISTENCIA
                # PASAR INMEDIATAMENTE A LA SIGUIENTE.
                # ==================================================

                if resultado == "ya_registrada":
                    print(
                        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
                    )

                    ya_registradas += 1

                    if numero < len(personas):
                        preparar_siguiente(
                            page
                        )

                    continue

                # ==================================================
                # PERSONA NO EXISTE / NO ENCONTRADO
                # PASAR INMEDIATAMENTE A LA SIGUIENTE.
                # ==================================================

                if resultado == "no_encontrado":
                    print(
                        f"🔎 {tipo_documento} "
                        f"NO ENCONTRADO"
                    )

                    no_encontrados += 1

                    if numero < len(personas):
                        preparar_siguiente(
                            page
                        )

                    continue

                # ==================================================
                # INVÁLIDO
                # ==================================================

                if resultado == "invalido":
                    print(
                        f"🔎 {tipo_documento} "
                        f"NO ENCONTRADO"
                    )

                    no_encontrados += 1

                    if numero < len(personas):
                        preparar_siguiente(
                            page
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

                    if numero < len(personas):
                        preparar_siguiente(
                            page
                        )

                    continue

                # ==================================================
                # DOCUMENTO VÁLIDO
                # ==================================================

                print(
                    f"✅ {tipo_documento} VALIDADO"
                )

                boton_asistencia = page.get_by_role(
                    "button",
                    name="Valida tu Asistencia",
                    exact=True,
                ).first

                boton_asistencia.wait_for(
                    state="visible",
                    timeout=TIMEOUT_ELEMENTO,
                )

                resultado_envio = enviar_asistencia(
                    page,
                    boton_asistencia,
                )

                # ==================================================
                # RESULTADO DE ENVÍO
                # ==================================================

                if resultado_envio == "ya_registrada":
                    print(
                        "⚠️ YA TENÍA REGISTRADA ASISTENCIA"
                    )

                    ya_registradas += 1

                elif resultado_envio == "error":
                    print(
                        "❌ ERROR EN EL REGISTRO"
                    )

                    errores += 1

                elif resultado_envio == "enviada":
                    print(
                        "✅ ASISTENCIA ENVIADA"
                    )

                    exitosos += 1

                else:
                    print(
                        "❌ NO SE PUDO CONFIRMAR EL ENVÍO"
                    )

                    errores += 1

                # ==================================================
                # SIGUIENTE PERSONA
                # ==================================================

                if numero < len(personas):
                    print(
                        "➡️ Preparando siguiente persona..."
                    )

                    if not preparar_siguiente(
                        page
                    ):
                        print(
                            "❌ ERROR EN EL REGISTRO"
                        )
                        print(
                            "No se pudo preparar "
                            "el formulario siguiente."
                        )
                        errores += 1

            except PlaywrightTimeoutError as error:
                print(
                    "❌ ERROR DE TIEMPO DE ESPERA"
                )
                print(error)

                errores += 1

                if numero < len(personas):
                    preparar_siguiente(
                        page
                    )

                continue

            except Exception as error:
                print(
                    "❌ ERROR EN EL REGISTRO"
                )
                print(error)

                errores += 1

                if numero < len(personas):
                    preparar_siguiente(
                        page
                    )

                continue

        # ==================================================
        # RESUMEN FINAL
        # ==================================================

        print()
        print("======================================")
        print("PROCESO FINALIZADO")
        print("======================================")
        print(
            "Total revisados:",
            len(personas),
        )
        print(
            "✅ Asistencias enviadas:",
            exitosos,
        )
        print(
            "⚠️ Ya tenían registrada asistencia:",
            ya_registradas,
        )
        print(
            "🔎 Documentos no encontrados:",
            no_encontrados,
        )
        print(
            "⚠️ Omitidos:",
            omitidos,
        )
        print(
            "❌ Errores:",
            errores,
        )
        print("======================================")

    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass

        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
