import json

import os

import sys

import time

import unicodedata



from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError





# ==========================================================

# UTF-8

# ==========================================================

if hasattr(sys.stdout, "reconfigure"):

    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

if hasattr(sys.stderr, "reconfigure"):

    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)





# ==========================================================

# CONFIGURACIÓN

# ==========================================================

def _env_bool(nombre, valor_defecto=False):

    valor = os.getenv(nombre)

    if valor is None or not str(valor).strip():

        return valor_defecto

    return str(valor).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}





URL = (

    os.getenv("DAVIS_REGISTRO_URL", "").strip()

    or os.getenv("REGISTRO_URL", "").strip()

)

ARCHIVO_JSON = os.getenv("DAVIS_ARCHIVO_JSON", "").strip()

JOB_ID = os.getenv("DAVIS_REGISTRO_JOB_ID", "registro").strip() or "registro"



# En Railway debe ejecutarse oculto. En Windows local, si no se define HEADLESS,

# se deja visible para facilitar pruebas.

EN_RAILWAY = bool(

    os.getenv("RAILWAY_ENVIRONMENT")

    or os.getenv("RAILWAY_PROJECT_ID")

    or os.getenv("RAILWAY_SERVICE_ID")

)

HEADLESS = _env_bool("HEADLESS", EN_RAILWAY)



CONTROL_DIR = os.getenv("DAVIS_REGISTRO_CONTROL_DIR", "").strip()

if not CONTROL_DIR:

    if ARCHIVO_JSON:

        CONTROL_DIR = os.path.join(

            os.path.dirname(os.path.abspath(ARCHIVO_JSON)),

            f"control_{JOB_ID}",

        )

    else:

        CONTROL_DIR = os.path.join(os.getcwd(), "temp", f"control_{JOB_ID}")



os.makedirs(CONTROL_DIR, exist_ok=True)



ARCHIVO_REVISION = os.path.join(CONTROL_DIR, "revision_pendiente.json")

ARCHIVO_CORRECCION = os.path.join(CONTROL_DIR, "correccion.json")

ARCHIVO_PROGRESO = os.path.join(CONTROL_DIR, "progreso.json")





# ==========================================================

# UTILIDADES

# ==========================================================

def normalizar_texto(texto):

    texto = str(texto or "").lower()

    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(

        caracter

        for caracter in texto

        if unicodedata.category(caracter) != "Mn"

    )

    return texto.strip()





def valor(persona, campo):

    dato = persona.get(campo, "")

    if dato is None:

        return ""

    return str(dato).strip()





def guardar_json(ruta, datos):

    temporal = ruta + ".tmp"

    with open(temporal, "w", encoding="utf-8") as archivo:

        json.dump(datos, archivo, ensure_ascii=False, indent=4)

    os.replace(temporal, ruta)





def eliminar_archivo(ruta):

    try:

        if ruta and os.path.exists(ruta):

            os.remove(ruta)

    except Exception:

        pass





def texto_de_pagina(page):

    """Obtiene el texto del body con poco overhead."""

    try:

        texto = page.evaluate(

            "() => document.body ? document.body.innerText : ''"

        )

        return normalizar_texto(texto)

    except Exception:

        return ""





# ==========================================================

# PROGRESO COMPARTIDO CON SERVICES

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

    PROGRESO.update(cambios)

    PROGRESO["actualizado_en"] = time.time()

    try:

        guardar_json(ARCHIVO_PROGRESO, PROGRESO)

    except Exception:

        # El registro no debe detenerse si falla únicamente el archivo de progreso.

        pass





# ==========================================================

# MENSAJES DEL FORMULARIO

# ==========================================================

def beneficiario_ya_registrado(texto):

    texto = normalizar_texto(texto)

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

    return any(mensaje in texto for mensaje in mensajes)





def beneficiario_creado(texto):

    texto = normalizar_texto(texto)

    mensajes = (

        "beneficiario creado correctamente",

        "beneficiado creado correctamente",

        "beneficiario guardado correctamente",

        "beneficiario registrado correctamente",

        "beneficiario creado con exito",

        "beneficiario registrado con exito",

    )

    return any(mensaje in texto for mensaje in mensajes)





# ==========================================================

# VALIDACIÓN DE DATOS

# ==========================================================

class SaltarPersona(Exception):

    """Señal interna para omitir manualmente solo el registro actual."""

    pass





class CampoRegistroError(Exception):

    def __init__(self, campo, detalle=""):

        self.campo = campo

        self.detalle = str(detalle)

        super().__init__(f"{campo}: {detalle}")





def campos_requeridos_faltantes(persona):

    requeridos = {

        "tipo_documento": "Tipo de documento",

        "documento": "Documento",

        "nombre": "Nombre completo",

        "genero": "Género",

        "fecha_nacimiento": "Fecha de nacimiento",

        "departamento": "Departamento",

        "municipio": "Municipio",

        "distrito": "Distrito",

        "residencia": "Residencia",

        "direccion": "Dirección",

    }

    return [

        nombre

        for campo, nombre in requeridos.items()

        if not valor(persona, campo)

    ]





# ==========================================================

# REVISIÓN / CORRECCIÓN DESDE LA WEB

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



    eliminar_archivo(ARCHIVO_CORRECCION)



    if numero not in REVISIONES_CONTADAS:

        REVISIONES_CONTADAS.add(numero)

        actualizar_progreso(revisiones=len(REVISIONES_CONTADAS))



    datos_revision = {

        "estado": "requiere_revision",

        "job_id": JOB_ID,

        "numero": numero,

        "total": total,

        "documento": valor(persona, "documento"),

        "tipo_documento": valor(persona, "tipo_documento"),

        "motivo": motivo,

        "campos_faltantes": campos_faltantes,

        "persona": persona,

    }

    guardar_json(ARCHIVO_REVISION, datos_revision)



    actualizar_progreso(

        estado="requiere_revision",

        actual=numero,

        total=total,

        documento=valor(persona, "documento"),

        requiere_revision=True,

        mensaje=motivo,

    )



    print()

    print("⏸️ REQUIERE REVISIÓN")

    print("DOCUMENTO:", valor(persona, "documento"))

    print("MOTIVO:", motivo)

    if campos_faltantes:

        print("CAMPOS FALTANTES:", ", ".join(campos_faltantes))

    print("DAVIS está esperando una corrección desde la página web.")



    # Se revisa 5 veces por segundo. Antes era más lento y hacía que la

    # corrección tardara en ser tomada por el proceso.

    while True:

        if os.path.exists(ARCHIVO_CORRECCION):

            try:

                with open(ARCHIVO_CORRECCION, "r", encoding="utf-8") as archivo:

                    correccion = json.load(archivo)



                if isinstance(correccion, dict):

                    accion = str(

                        correccion.get("accion", "")

                        or ""

                    ).strip().lower()



                    # ==========================================

                    # SALTAR PERSONA

                    # ==========================================

                    if accion == "saltar":

                        eliminar_archivo(ARCHIVO_CORRECCION)

                        eliminar_archivo(ARCHIVO_REVISION)



                        actualizar_progreso(

                            estado="ejecutando",

                            requiere_revision=False,

                            mensaje="Persona omitida manualmente. Continuando con la siguiente.",

                        )



                        print()

                        print("⏭️ PERSONA OMITIDA MANUALMENTE")

                        print("DOCUMENTO:", valor(persona, "documento"))

                        print("➡️ Pasando al siguiente registro...")



                        raise SaltarPersona()



                    cambios = correccion.get("persona", correccion)

                    if isinstance(cambios, dict):

                        persona_actualizada = dict(persona)

                        persona_actualizada.update(cambios)



                        eliminar_archivo(ARCHIVO_CORRECCION)

                        eliminar_archivo(ARCHIVO_REVISION)



                        actualizar_progreso(

                            estado="ejecutando",

                            requiere_revision=False,

                            mensaje="Corrección recibida. Reintentando registro.",

                        )



                        print()

                        print("▶️ CORRECCIÓN RECIBIDA")

                        print("DAVIS volverá a intentar este registro.")

                        return persona_actualizada



            except SaltarPersona:

                raise



            except Exception as error:

                print("⚠️ No se pudo leer la corrección:", error)



        time.sleep(0.20)





# ==========================================================

# MENSAJES DE VALIDACIÓN DEL FORMULARIO

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

            elementos = page.locator(selector)

            cantidad = min(elementos.count(), 20)

            for i in range(cantidad):

                elemento = elementos.nth(i)

                try:

                    if not elemento.is_visible():

                        continue

                    texto = elemento.inner_text().strip()

                    if not texto or len(texto) > 300:

                        continue



                    normalizado = normalizar_texto(texto)

                    if beneficiario_creado(normalizado) or beneficiario_ya_registrado(normalizado):

                        continue



                    ignorar = (

                        "toggle theme",

                        "cambiar tema",

                        "navigation",

                        "menu",

                    )

                    if any(palabra in normalizado for palabra in ignorar):

                        continue



                    if texto not in mensajes:

                        mensajes.append(texto)

                except Exception:

                    pass

        except Exception:

            pass



    try:

        invalidos = page.locator("input:invalid, textarea:invalid, select:invalid")

        cantidad = min(invalidos.count(), 20)

        for i in range(cantidad):

            campo = invalidos.nth(i)

            try:

                if not campo.is_visible():

                    continue

                nombre = (

                    campo.get_attribute("aria-label")

                    or campo.get_attribute("placeholder")

                    or campo.get_attribute("name")

                    or "Campo requerido"

                )

                mensaje = f"Revisar: {nombre}"

                if mensaje not in mensajes:

                    mensajes.append(mensaje)

            except Exception:

                pass

    except Exception:

        pass



    return mensajes





def identificar_campos_error(mensajes):

    campos = []

    mapa = (

        (("nombre completo", "nombre"), "Nombre completo"),

        (("genero", "género"), "Género"),

        (("fecha de nacimiento", "fecha nacimiento"), "Fecha de nacimiento"),

        (("whatsapp",), "WhatsApp"),

        (("telefono", "teléfono"), "Teléfono"),

        (("correo", "email"), "Correo"),

        (("departamento",), "Departamento"),

        (("municipio",), "Municipio"),

        (("distrito",), "Distrito"),

        (("canton", "cantón", "caserio", "caserío", "barrio", "residencia"), "Residencia"),

        (("direccion", "dirección"), "Dirección"),

        (("institucion", "institución"), "Institución"),

        (("cargo",), "Cargo"),

    )



    for mensaje in mensajes:

        texto = normalizar_texto(mensaje)

        for palabras, nombre_campo in mapa:

            if any(normalizar_texto(palabra) in texto for palabra in palabras):

                if nombre_campo not in campos:

                    campos.append(nombre_campo)

    return campos





# ==========================================================

# ESPERA RÁPIDA DE VALIDACIÓN DUI / NIE

# ==========================================================

def esperar_resultado_documento(page, timeout_ms=5000):

    """

    Espera el primer resultado real del formulario sin pausas fijas de 1-2 s.



    Devuelve:

      - ya_registrado

      - formulario

      - timeout

    """

    inicio = time.monotonic()

    timeout_s = timeout_ms / 1000

    nombre = page.get_by_role("textbox", name="* Nombre Completo")



    formulario_visible_desde = None

    ultima_revision_texto = 0.0



    while (time.monotonic() - inicio) < timeout_s:

        ahora = time.monotonic()



        # No copiamos todo el BODY cada 50 ms; se revisa aproximadamente

        # cada 150 ms, suficiente para detectar el aviso inmediatamente.

        if ahora - ultima_revision_texto >= 0.15:

            if beneficiario_ya_registrado(texto_de_pagina(page)):

                return "ya_registrado"

            ultima_revision_texto = ahora



        try:

            formulario_disponible = nombre.is_visible() and nombre.is_enabled()

        except Exception:

            formulario_disponible = False



        if formulario_disponible:

            if formulario_visible_desde is None:

                formulario_visible_desde = ahora



            # Pequeño margen para evitar que el formulario gane la carrera

            # a un mensaje de "ya registrado" que llegue casi simultáneamente.

            if ahora - formulario_visible_desde >= 0.18:

                if beneficiario_ya_registrado(texto_de_pagina(page)):

                    return "ya_registrado"

                return "formulario"

        else:

            formulario_visible_desde = None



        page.wait_for_timeout(40)



    if beneficiario_ya_registrado(texto_de_pagina(page)):

        return "ya_registrado"



    try:

        if nombre.is_visible() and nombre.is_enabled():

            return "formulario"

    except Exception:

        pass



    return "timeout"





# ==========================================================

# ABRIR FORMULARIO Y ESPERAR QUE ESTÉ REALMENTE LISTO

# ==========================================================

def abrir_formulario_listo(page, tipo, intentos=3):

    """

    Abre el formulario y espera el campo DUI/NIE antes de continuar.



    Esto evita perder el primer registro cuando Chromium todavía está

    arrancando o cuando el JavaScript del formulario tarda más en cargar.

    """

    nombre_campo = "DUI" if tipo == "DUI" else "NIE"

    ultimo_error = None



    for intento in range(1, intentos + 1):

        try:

            print(f"Abriendo formulario... intento {intento} de {intentos}")



            page.goto(

                URL,

                wait_until="domcontentloaded",

                timeout=20000,

            )



            campo_documento = page.get_by_role(

                "textbox",

                name=nombre_campo,

            )



            campo_documento.wait_for(

                state="visible",

                timeout=10000,

            )



            boton_validar = page.get_by_role(

                "button",

                name="Validar",

            )



            boton_validar.wait_for(

                state="visible",

                timeout=5000,

            )



            return campo_documento



        except Exception as error:

            ultimo_error = error

            print("⚠️ El formulario todavía no está listo.")



            if intento < intentos:

                page.wait_for_timeout(500)



    if ultimo_error is not None:

        raise ultimo_error



    raise RuntimeError("No se pudo abrir el formulario de registro.")





# ==========================================================

# INGRESAR DOCUMENTO Y ESPERAR BOTÓN VALIDAR

# ==========================================================

def ingresar_documento_y_validar(page, tipo, documento, intentos=3):
    """
    Intenta colocar el DUI/NIE completo de una sola vez.

    Si React/Ant Design no reconoce fill(), DAVIS usa escritura gradual
    únicamente como respaldo. Nunca avanza automáticamente a otra persona
    si el botón Validar no logra habilitarse.
    """
    ultimo_error = None

    for intento in range(1, intentos + 1):
        try:
            campo_documento = abrir_formulario_listo(
                page,
                tipo,
                intentos=1,
            )

            print(f"{tipo}: {documento}")

            boton_validar = page.get_by_role(
                "button",
                name="Validar",
            )
            boton_validar.wait_for(
                state="visible",
                timeout=5000,
            )

            # ==================================================
            # INTENTO RÁPIDO
            # ==================================================
            campo_documento.click()
            campo_documento.fill(documento)
            campo_documento.press("Tab")

            inicio = time.monotonic()

            while (time.monotonic() - inicio) < 1.2:
                try:
                    if boton_validar.is_enabled():
                        boton_validar.click(timeout=2500)
                        print("Validando...")
                        return
                except PlaywrightTimeoutError:
                    pass

                page.wait_for_timeout(60)

            # ==================================================
            # RESPALDO GRADUAL
            # ==================================================
            print(
                "⚠️ El formulario no reconoció el llenado instantáneo. "
                "Aplicando método de respaldo..."
            )

            campo_documento.click()
            campo_documento.press("Control+A")
            campo_documento.press("Backspace")
            campo_documento.type(
                documento,
                delay=40 if intento == 1 else 60,
            )
            campo_documento.press("Tab")

            inicio = time.monotonic()

            while (time.monotonic() - inicio) < 3.5:
                try:
                    if boton_validar.is_enabled():
                        boton_validar.click(timeout=2500)
                        print("Validando...")
                        return
                except PlaywrightTimeoutError:
                    pass

                page.wait_for_timeout(80)

            raise RuntimeError(
                "El botón Validar permaneció deshabilitado "
                "después de ingresar el documento."
            )

        except Exception as error:
            ultimo_error = error

            print(
                f"⚠️ El botón Validar todavía no está disponible. "
                f"Reintento {intento} de {intentos}."
            )

            if intento < intentos:
                page.wait_for_timeout(250)

    if ultimo_error is not None:
        raise ultimo_error

    raise RuntimeError("No se pudo validar el documento.")


# ==========================================================
# CAMPOS DEL FORMULARIO
# ==========================================================

def _dropdown_visible(page):
    """
    Devuelve el último dropdown visible de Ant Design, si existe.
    """
    try:
        dropdowns = page.locator(".ant-select-dropdown:visible")
        if dropdowns.count() > 0:
            return dropdowns.last
    except Exception:
        pass

    return None


def _buscar_opcion_visible(page, opcion):
    """
    Busca una opción exacta que esté realmente visible.

    Se intenta primero por role=option y luego por los selectores
    habituales de Ant Design. Como último respaldo se usa texto exacto.
    """
    opcion = str(opcion or "").strip()

    if not opcion:
        return None

    dropdown = _dropdown_visible(page)

    # ======================================================
    # 1. DENTRO DEL DROPDOWN VISIBLE
    # ======================================================
    if dropdown is not None:
        try:
            candidato = dropdown.get_by_role(
                "option",
                name=opcion,
                exact=True,
            ).last

            if candidato.count() > 0 and candidato.is_visible():
                return candidato
        except Exception:
            pass

        try:
            candidatos = dropdown.locator(
                ".ant-select-item-option-content"
            )

            cantidad = candidatos.count()

            for indice in range(cantidad):
                candidato = candidatos.nth(indice)

                try:
                    if (
                        candidato.is_visible()
                        and candidato.inner_text().strip() == opcion
                    ):
                        return candidato
                except Exception:
                    pass
        except Exception:
            pass

        try:
            candidato = dropdown.get_by_text(
                opcion,
                exact=True,
            ).last

            if candidato.count() > 0 and candidato.is_visible():
                return candidato
        except Exception:
            pass

    # ======================================================
    # 2. ROLE=OPTION GLOBAL
    # ======================================================
    try:
        candidatos = page.get_by_role(
            "option",
            name=opcion,
            exact=True,
        )

        cantidad = candidatos.count()

        for indice in range(cantidad - 1, -1, -1):
            candidato = candidatos.nth(indice)

            try:
                if candidato.is_visible():
                    return candidato
            except Exception:
                pass
    except Exception:
        pass

    # ======================================================
    # 3. TEXTO EXACTO VISIBLE COMO ÚLTIMO RESPALDO
    # ======================================================
    try:
        candidatos = page.get_by_text(
            opcion,
            exact=True,
        )

        cantidad = candidatos.count()

        for indice in range(cantidad - 1, -1, -1):
            candidato = candidatos.nth(indice)

            try:
                if candidato.is_visible():
                    return candidato
            except Exception:
                pass
    except Exception:
        pass

    return None


def _esperar_y_click_opcion(page, opcion, timeout=1800):
    """
    Espera activamente hasta que una opción aparezca y luego hace clic.
    No usa una pausa fija larga.
    """
    inicio = time.monotonic()
    timeout_s = max(0.2, timeout / 1000)

    while (time.monotonic() - inicio) < timeout_s:
        candidato = _buscar_opcion_visible(
            page,
            opcion,
        )

        if candidato is not None:
            try:
                candidato.click(
                    timeout=min(timeout, 1200)
                )
                return True
            except Exception:
                try:
                    candidato.click(
                        timeout=800,
                        force=True,
                    )
                    return True
                except Exception:
                    pass

        page.wait_for_timeout(45)

    return False


def _esperar_dropdown_cerrado(page, timeout=1000):
    """
    Después de seleccionar una opción, da un pequeño margen para
    que React/Ant Design confirme el cambio y cierre el menú.
    """
    inicio = time.monotonic()
    timeout_s = timeout / 1000

    while (time.monotonic() - inicio) < timeout_s:
        if _dropdown_visible(page) is None:
            return

        page.wait_for_timeout(40)


def normalizar_genero_formulario(genero):
    """
    Convierte variantes comunes a los dos valores aceptados
    por el formulario.
    """
    dato = normalizar_texto(genero)

    masculinos = {
        "masculino",
        "hombre",
        "m",
        "h",
    }

    femeninos = {
        "femenino",
        "mujer",
        "f",
    }

    if dato in masculinos:
        return "Masculino"

    if dato in femeninos:
        return "Femenino"

    return str(genero or "").strip()


def seleccionar_genero_rapido(page, opcion, timeout=3500):
    """
    Selección específica y robusta de Género.

    Género tiene únicamente unas pocas opciones, por lo que NO se escribe
    dentro del combobox. Se abre el menú, se espera a que la opción exacta
    aparezca y se hace clic.

    Esto evita el error que podía ocurrir al intentar usar fill() sobre
    un selector que no funciona como un campo de búsqueda normal.
    """
    opcion = normalizar_genero_formulario(
        opcion
    )

    if opcion not in {
        "Masculino",
        "Femenino",
    }:
        raise ValueError(
            f"Género no reconocido: {opcion}"
        )

    combo = page.get_by_role(
        "combobox",
        name="* Género",
    )

    combo.wait_for(
        state="visible",
        timeout=timeout,
    )

    # Esperar si el control aún está terminando de habilitarse.
    inicio = time.monotonic()

    while (time.monotonic() - inicio) < (timeout / 1000):
        try:
            if combo.is_enabled():
                break
        except Exception:
            pass

        page.wait_for_timeout(50)
    else:
        raise RuntimeError(
            "El selector de Género permanece deshabilitado."
        )

    # ======================================================
    # PRIMER INTENTO
    # ======================================================
    combo.click(
        timeout=min(timeout, 1500)
    )

    if _esperar_y_click_opcion(
        page,
        opcion,
        timeout=1600,
    ):
        _esperar_dropdown_cerrado(
            page,
            timeout=700,
        )
        return

    # ======================================================
    # SEGUNDO INTENTO
    #
    # React puede ignorar un clic mientras termina de pintar
    # el formulario. Reabrimos el selector una sola vez.
    # ======================================================
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass

    page.wait_for_timeout(80)

    combo.click(
        timeout=min(timeout, 1500)
    )

    if _esperar_y_click_opcion(
        page,
        opcion,
        timeout=1600,
    ):
        _esperar_dropdown_cerrado(
            page,
            timeout=700,
        )
        return

    raise RuntimeError(
        f"No se pudo seleccionar el género '{opcion}'."
    )


def _texto_seleccionado_combobox(combo):
    """
    Intenta obtener el texto que el Select muestra como opción elegida.
    Compatible con Ant Design y con selectores similares.
    """
    # Ant Design: buscar el elemento que pinta la selección.
    try:
        raiz = combo.locator(
            "xpath=ancestor::*[contains(@class,'ant-select')][1]"
        )

        if raiz.count() > 0:
            seleccion = raiz.locator(
                ".ant-select-selection-item"
            )

            if seleccion.count() > 0:
                texto = seleccion.last.inner_text().strip()

                if texto:
                    return texto
    except Exception:
        pass

    # Respaldo por valor real del input.
    try:
        dato = combo.input_value().strip()

        if dato:
            return dato
    except Exception:
        pass

    # Respaldo por texto del contenedor inmediato.
    try:
        padre = combo.locator("xpath=..")
        texto = padre.inner_text().strip()

        if texto:
            return texto
    except Exception:
        pass

    return ""


def _selector_cerrado(combo):
    """
    Comprueba si el desplegable dejó de estar abierto.
    """
    try:
        expandido = combo.get_attribute(
            "aria-expanded"
        )

        if expandido is not None:
            return str(expandido).lower() != "true"
    except Exception:
        pass

    # Si el componente no usa aria-expanded, se toma como cerrado
    # cuando ya no existe un listbox/dropdown visible asociado.
    try:
        controles = (
            combo.get_attribute("aria-controls")
            or combo.get_attribute("aria-owns")
            or ""
        ).strip()

        if controles:
            popup = combo.page.locator(
                f"#{controles}"
            )

            if popup.count() > 0:
                return not popup.is_visible()
    except Exception:
        pass

    try:
        visibles = combo.page.locator(
            '[role="listbox"]:visible, .ant-select-dropdown:visible'
        )

        return visibles.count() == 0
    except Exception:
        return True


def _seleccion_confirmada(combo, opcion):
    """
    Confirma que:
    1) el menú está cerrado;
    2) el texto seleccionado coincide con la opción esperada.
    """
    if not _selector_cerrado(
        combo
    ):
        return False

    esperado = normalizar_texto(
        opcion
    )

    visible = normalizar_texto(
        _texto_seleccionado_combobox(
            combo
        )
    )

    # En algunos Select el input queda vacío después de elegir.
    # En ese caso, que el menú haya cerrado es señal suficiente.
    if not visible:
        return True

    return (
        visible == esperado
        or esperado in visible
    )


def _esperar_seleccion_confirmada(
    combo,
    opcion,
    timeout=1800,
):
    """
    Espera dinámicamente a que React termine de confirmar la selección.
    """
    inicio = time.monotonic()
    timeout_s = timeout / 1000

    while (
        time.monotonic() - inicio
    ) < timeout_s:

        if _seleccion_confirmada(
            combo,
            opcion,
        ):
            return True

        combo.page.wait_for_timeout(
            50
        )

    return False


def _opcion_exacta_visible(page, combo, opcion):
    """
    Busca la opción exacta dentro del popup asociado al combobox.
    Evita confundir el texto ya seleccionado con la opción del menú.
    """
    opcion = str(
        opcion or ""
    ).strip()

    popup = None

    # Primero usar el popup específico indicado por aria-controls/aria-owns.
    try:
        popup_id = (
            combo.get_attribute("aria-controls")
            or combo.get_attribute("aria-owns")
            or ""
        ).strip()

        if popup_id:
            candidato_popup = page.locator(
                f"#{popup_id}"
            )

            if (
                candidato_popup.count() > 0
                and candidato_popup.is_visible()
            ):
                popup = candidato_popup
    except Exception:
        popup = None

    # Respaldo: último listbox/dropdown realmente visible.
    if popup is None:
        try:
            popups = page.locator(
                '[role="listbox"]:visible, .ant-select-dropdown:visible'
            )

            if popups.count() > 0:
                popup = popups.last
        except Exception:
            popup = None

    if popup is None:
        return None

    # Opción semántica.
    try:
        candidato = popup.get_by_role(
            "option",
            name=opcion,
            exact=True,
        ).last

        if (
            candidato.count() > 0
            and candidato.is_visible()
        ):
            return candidato
    except Exception:
        pass

    # Ant Design.
    try:
        items = popup.locator(
            ".ant-select-item-option"
        )

        cantidad = items.count()

        for indice in range(
            cantidad
        ):
            item = items.nth(
                indice
            )

            try:
                if not item.is_visible():
                    continue

                contenido = item.locator(
                    ".ant-select-item-option-content"
                )

                texto_item = (
                    contenido.inner_text().strip()
                    if contenido.count() > 0
                    else item.inner_text().strip()
                )

                if normalizar_texto(
                    texto_item
                ) == normalizar_texto(
                    opcion
                ):
                    return item
            except Exception:
                pass
    except Exception:
        pass

    # Texto exacto únicamente dentro del popup.
    try:
        candidatos = popup.get_by_text(
            opcion,
            exact=True,
        )

        cantidad = candidatos.count()

        for indice in range(
            cantidad
        ):
            candidato = candidatos.nth(
                indice
            )

            try:
                if candidato.is_visible():
                    return candidato
            except Exception:
                pass
    except Exception:
        pass

    return None


def seleccionar_combobox(
    page,
    nombre,
    opcion,
    timeout=5000,
):
    """
    Selecciona Departamento, Municipio o Distrito de forma confirmada.

    Flujo:
    1. abre el selector;
    2. escribe/filtra el valor;
    3. intenta confirmar con ENTER;
    4. si ENTER no confirma, hace clic SOLO en la opción del popup;
    5. NO continúa hasta comprobar que el menú se cerró.

    Esto corrige casos como Distrito=SANTA ANA, donde el texto podía
    verse en pantalla pero el dropdown seguía abierto.
    """
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

    # Esperar a que React habilite el campo.
    inicio = time.monotonic()
    timeout_s = timeout / 1000

    while (
        time.monotonic() - inicio
    ) < timeout_s:

        try:
            if combo.is_enabled():
                break
        except Exception:
            pass

        page.wait_for_timeout(
            60
        )
    else:
        raise RuntimeError(
            f"El selector '{nombre}' continúa deshabilitado."
        )

    ultimo_error = None

    # Dos intentos completos, nunca más para evitar esperas largas.
    for intento in range(
        1,
        3,
    ):
        try:
            # Limpiar cualquier menú anterior.
            try:
                page.keyboard.press(
                    "Escape"
                )
            except Exception:
                pass

            page.wait_for_timeout(
                50
            )

            combo.click(
                timeout=min(
                    timeout,
                    1600,
                )
            )

            # ==================================================
            # FILTRAR
            # ==================================================
            try:
                combo.fill(
                    opcion
                )
            except Exception:
                try:
                    combo.press(
                        "Control+A"
                    )
                    page.keyboard.insert_text(
                        opcion
                    )
                except Exception:
                    pass

            # Dejar que el popup filtre, pero sin una pausa larga fija.
            inicio_filtro = time.monotonic()

            while (
                time.monotonic()
                - inicio_filtro
            ) < 1.2:

                opcion_popup = _opcion_exacta_visible(
                    page,
                    combo,
                    opcion,
                )

                if opcion_popup is not None:
                    break

                page.wait_for_timeout(
                    40
                )
            else:
                opcion_popup = None

            # ==================================================
            # MÉTODO 1: ENTER
            #
            # Para listas filtradas a una sola opción (como Distrito
            # SANTA ANA) es el método más confiable.
            # ==================================================
            try:
                combo.press(
                    "Enter"
                )
            except Exception:
                pass

            if _esperar_seleccion_confirmada(
                combo,
                opcion,
                timeout=900,
            ):
                return

            # ==================================================
            # MÉTODO 2: CLIC EN LA OPCIÓN REAL DEL POPUP
            # ==================================================
            if opcion_popup is None:
                opcion_popup = _opcion_exacta_visible(
                    page,
                    combo,
                    opcion,
                )

            if opcion_popup is not None:
                try:
                    opcion_popup.click(
                        timeout=1200
                    )
                except Exception:
                    opcion_popup.click(
                        timeout=900,
                        force=True,
                    )

                if _esperar_seleccion_confirmada(
                    combo,
                    opcion,
                    timeout=1200,
                ):
                    return

            raise RuntimeError(
                f"La opción '{opcion}' apareció, "
                "pero el selector no confirmó la selección."
            )

        except Exception as error:
            ultimo_error = error

            if intento < 2:
                try:
                    page.keyboard.press(
                        "Escape"
                    )
                except Exception:
                    pass

                page.wait_for_timeout(
                    100
                )

    raise RuntimeError(
        f"No se pudo confirmar '{opcion}' en '{nombre}'. "
        f"Detalle: {ultimo_error}"
    )


def esperar_combobox_habilitado(page, nombre, timeout=8000):
    """
    Espera únicamente hasta que el selector dependiente quede habilitado.
    """
    combo = page.get_by_role(
        "combobox",
        name=nombre,
    )

    combo.wait_for(
        state="visible",
        timeout=timeout,
    )

    inicio = time.monotonic()

    while (time.monotonic() - inicio) < (timeout / 1000):
        try:
            if combo.is_enabled():
                # Dar un margen mínimo a React para cargar las opciones.
                page.wait_for_timeout(70)
                return combo
        except Exception:
            pass

        page.wait_for_timeout(70)

    raise RuntimeError(
        f"El selector '{nombre}' no se habilitó "
        "después de la selección anterior."
    )


def llenar_opcional(page, nombre, dato, nombre_error):

    dato = str(dato or "").strip()

    if not dato:

        return



    try:

        campo = page.get_by_role("textbox", name=nombre)

        campo.wait_for(state="visible", timeout=3500)

        campo.fill(dato)

    except Exception as error:

        raise CampoRegistroError(nombre_error, error) from error





def llenar_formulario(page, persona):

    try:

        page.get_by_role("textbox", name="* Nombre Completo").fill(valor(persona, "nombre"))

    except Exception as error:

        raise CampoRegistroError("Nombre completo", error) from error



    try:

        seleccionar_genero_rapido(
            page,
            valor(persona, "genero"),
            timeout=3000,
        )

    except Exception as error:

        raise CampoRegistroError("Género", error) from error



    try:

        campo_fecha = page.get_by_role("textbox", name="* Fecha de nacimiento")

        campo_fecha.wait_for(state="visible", timeout=4000)

        fecha = valor(persona, "fecha_nacimiento")



        if not fecha:

            raise ValueError("La fecha de nacimiento está vacía.")



        # IMPORTANTE:

        # Este formulario usa una máscara/JavaScript para la fecha.

        # fill() puede mostrar el dato para Playwright pero no dejarlo

        # registrado en el componente. Por eso volvemos al método que

        # ya funcionaba: escribir carácter por carácter.

        campo_fecha.click()

        campo_fecha.press("Control+A")

        campo_fecha.press("Backspace")

        campo_fecha.type(fecha, delay=60)

        campo_fecha.press("Enter")

        campo_fecha.press("Tab")

        page.wait_for_timeout(150)



        valor_fecha = campo_fecha.input_value().strip()



        # Si el componente no conservó la fecha, hacemos un segundo intento

        # más lento antes de pedir revisión al usuario.

        if not valor_fecha:

            campo_fecha.click()

            campo_fecha.press("Control+A")

            campo_fecha.press("Backspace")

            campo_fecha.type(fecha, delay=90)

            campo_fecha.press("Tab")

            page.wait_for_timeout(200)

            valor_fecha = campo_fecha.input_value().strip()



        if not valor_fecha:

            raise ValueError(

                f"El formulario no aceptó la fecha de nacimiento: {fecha}"

            )



    except Exception as error:

        raise CampoRegistroError("Fecha de nacimiento", error) from error



    llenar_opcional(page, "Teléfono de Llamadas", valor(persona, "telefono"), "Teléfono")

    llenar_opcional(page, "Teléfono de WhatsApp", valor(persona, "whatsapp"), "WhatsApp")

    llenar_opcional(page, "Correo Personal", valor(persona, "correo"), "Correo")



    try:

        seleccionar_combobox(

            page,

            "* Departamento dónde reside",

            valor(persona, "departamento"),

            timeout=6000,

        )

        esperar_combobox_habilitado(
            page,
            "* Municipio dónde reside",
            timeout=9000,
        )

    except Exception as error:

        raise CampoRegistroError("Departamento", error) from error



    try:

        seleccionar_combobox(

            page,

            "* Municipio dónde reside",

            valor(persona, "municipio"),

            timeout=7000,

        )

        esperar_combobox_habilitado(
            page,
            "* Distrito dónde reside",
            timeout=9000,
        )

    except Exception as error:

        raise CampoRegistroError("Municipio", error) from error



    try:

        seleccionar_combobox(

            page,

            "* Distrito dónde reside",

            valor(persona, "distrito"),

            timeout=7000,

        )

    except Exception as error:

        raise CampoRegistroError("Distrito", error) from error



    try:

        page.get_by_role("textbox", name="* Cantón/Caserío/Barrio/").fill(

            valor(persona, "residencia")

        )

    except Exception as error:

        raise CampoRegistroError("Residencia", error) from error



    try:

        page.get_by_role("textbox", name="* Dirección de residencia").fill(

            valor(persona, "direccion")

        )

    except Exception as error:

        raise CampoRegistroError("Dirección", error) from error



    llenar_opcional(

        page,

        "Institución / Organización",

        valor(persona, "institucion"),

        "Institución",

    )

    llenar_opcional(page, "Cargo", valor(persona, "cargo"), "Cargo")





# ==========================================================

# ESPERA RÁPIDA AL GUARDAR

# ==========================================================

def esperar_resultado_guardado(page, timeout_ms=4500):

    inicio = time.monotonic()

    timeout_s = timeout_ms / 1000

    siguiente_revision_errores = inicio + 0.30



    while (time.monotonic() - inicio) < timeout_s:

        texto = texto_de_pagina(page)

        if beneficiario_creado(texto):

            return "creado", []



        ahora = time.monotonic()

        if ahora >= siguiente_revision_errores:

            mensajes = extraer_mensajes_validacion(page)

            if mensajes:

                return "revision", mensajes

            siguiente_revision_errores = ahora + 0.25



        page.wait_for_timeout(80)



    # Última revisión antes de pedir intervención del usuario.

    texto = texto_de_pagina(page)

    if beneficiario_creado(texto):

        return "creado", []



    return "revision", extraer_mensajes_validacion(page)





# ==========================================================

# PROCESAR UNA PERSONA

# ==========================================================

def procesar_persona(page, persona_original, numero, total):

    persona = dict(persona_original)

    requirio_revision = False



    while True:

        tipo = valor(persona, "tipo_documento").upper()

        documento = valor(persona, "documento")



        actualizar_progreso(

            estado="ejecutando",

            actual=numero,

            total=total,

            documento=documento,

            requiere_revision=False,

            mensaje="Validando documento.",

        )



        problemas_identidad = []

        if tipo not in ("DUI", "NIE"):

            problemas_identidad.append("Tipo de documento")

        if not documento:

            problemas_identidad.append("Documento")



        if problemas_identidad:

            requirio_revision = True

            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo="Faltan datos necesarios para validar al beneficiario.",

                campos_faltantes=problemas_identidad,

            )

            continue



        # ==================================================

        # ABRIR + ESCRIBIR DOCUMENTO + VALIDAR

        #

        # El botón Validar de este formulario puede quedar

        # temporalmente deshabilitado aunque el DUI/NIE ya se

        # vea escrito. DAVIS espera a que se habilite y, si no

        # ocurre, vuelve a intentar ESTA MISMA PERSONA.

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

                    "DAVIS ingresó el documento, pero el botón Validar "

                    "no logró habilitarse después de 3 intentos. "

                    "DAVIS NO pasará automáticamente a la siguiente "

                    "persona. Puedes usar Guardar corrección y continuar "

                    "para reintentar esta misma persona, o Saltar persona "

                    "para omitirla manualmente. "

                    f"Detalle: {error}"

                ),

                campos_faltantes=["Documento"],

            )

            continue



        resultado_documento = esperar_resultado_documento(page, timeout_ms=5000)



        if resultado_documento == "ya_registrado":

            print()

            print("⚠️ YA REGISTRADO")

            print("DOCUMENTO:", documento)

            print("➡️ Pasando al siguiente registro...")

            return "ya_registrado", requirio_revision



        if resultado_documento != "formulario":

            print()

            print("⚠️ NO SE HABILITÓ EL FORMULARIO")

            print("DOCUMENTO:", documento)

            print("DAVIS mantendrá esta misma persona en revisión.")



            requirio_revision = True

            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=(

                    "Después de validar el documento no se habilitó el "

                    "formulario. DAVIS no pasará automáticamente a la "

                    "siguiente persona. Puedes reintentar con Guardar "

                    "corrección y continuar, o usar Saltar persona."

                ),

                campos_faltantes=[],

            )

            continue



        print("✅ Documento validado.")

        actualizar_progreso(mensaje="Documento validado. Completando formulario.")



        faltantes = campos_requeridos_faltantes(persona)

        if faltantes:

            requirio_revision = True

            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo="El registro tiene campos requeridos sin información.",

                campos_faltantes=faltantes,

            )

            continue



        try:

            llenar_formulario(page, persona)

        except CampoRegistroError as error:

            requirio_revision = True

            print()

            print("⚠️ ERROR EN CAMPO:")

            print(error.campo)

            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=f"DAVIS no pudo completar el campo: {error.campo}.",

                campos_faltantes=[error.campo],

            )

            continue

        except Exception:

            requirio_revision = True

            mensajes = extraer_mensajes_validacion(page)

            campos_error = identificar_campos_error(mensajes)

            motivo = "DAVIS no pudo completar correctamente el formulario."

            if mensajes:

                motivo += " " + " | ".join(mensajes[:5])

            persona = solicitar_revision(

                persona=persona,

                numero=numero,

                total=total,

                motivo=motivo,

                campos_faltantes=campos_error,

            )

            continue



        print("Guardando beneficiario...")

        actualizar_progreso(mensaje="Guardando beneficiario.")



        boton_guardar = page.get_by_role("button", name="Guardar Beneficiario")

        boton_guardar.wait_for(state="visible", timeout=4000)

        boton_guardar.click()



        resultado_guardado, mensajes = esperar_resultado_guardado(page, timeout_ms=4500)



        if resultado_guardado == "creado":

            print()

            print("✅ BENEFICIARIO CREADO CORRECTAMENTE")

            print("DOCUMENTO:", documento)

            print("➡️ Pasando al siguiente registro...")

            return "creado", requirio_revision



        campos_error = identificar_campos_error(mensajes)

        if mensajes:

            motivo = "No se pudo guardar el beneficiario. " + " | ".join(mensajes[:8])

        else:

            motivo = (

                "No se detectó el mensaje 'Beneficiario creado correctamente'. "

                "Revisa los datos del formulario."

            )



        requirio_revision = True

        persona = solicitar_revision(

            persona=persona,

            numero=numero,

            total=total,

            motivo=motivo,

            campos_faltantes=campos_error,

        )





# ==========================================================

# CARGAR JSON

# ==========================================================

def cargar_personas():

    if not URL:

        raise RuntimeError("DAVIS no recibió la URL del formulario de registro.")

    if not ARCHIVO_JSON:

        raise RuntimeError("DAVIS no recibió el archivo JSON.")

    if not os.path.exists(ARCHIVO_JSON):

        raise FileNotFoundError(f"No existe el archivo JSON: {ARCHIVO_JSON}")



    with open(ARCHIVO_JSON, "r", encoding="utf-8-sig") as archivo:

        datos = json.load(archivo)



    if isinstance(datos, dict) and isinstance(datos.get("personas"), list):

        datos = datos["personas"]



    if not isinstance(datos, list):

        raise ValueError("El JSON debe contener una lista de personas.")

    if not datos:

        raise ValueError("No existen personas para registrar.")



    return datos





# ==========================================================

# MAIN

# ==========================================================

def main():

    personas = cargar_personas()

    total = len(personas)



    actualizar_progreso(

        estado="iniciando",

        actual=0,

        total=total,

        mensaje="Preparando navegador.",

    )



    print()

    print("======================================")

    print("           SISTEMA DAVIS")

    print("======================================")

    print("MÓDULO: REGISTRO")

    print()

    print("Registros recibidos:", total)

    print("Navegador oculto:", HEADLESS)

    print("JOB:", JOB_ID)

    print("======================================")



    creados = 0

    ya_registrados = 0

    omitidos = 0

    errores = 0



    browser = None

    context = None



    try:

        with sync_playwright() as p:

            opciones_navegador = {"headless": HEADLESS}

            if os.name != "nt":

                opciones_navegador["args"] = ["--no-sandbox", "--disable-dev-shm-usage"]



            browser = p.chromium.launch(**opciones_navegador)

            context = browser.new_context()

            page = context.new_page()

            page.set_default_timeout(8000)



            actualizar_progreso(estado="ejecutando", mensaje="Navegador listo.")



            for numero, persona in enumerate(personas, start=1):

                print()

                print("======================================")

                print(f"REGISTRO {numero} DE {total}")

                print("======================================")



                documento_inicial = valor(persona, "documento")

                print("DOCUMENTO:", documento_inicial if documento_inicial else "VACÍO")



                actualizar_progreso(

                    estado="ejecutando",

                    actual=numero,

                    total=total,

                    documento=documento_inicial,

                    requiere_revision=False,

                    mensaje="Iniciando registro.",

                )



                try:

                    resultado, _ = procesar_persona(

                        page=page,

                        persona_original=persona,

                        numero=numero,

                        total=total,

                    )



                    if resultado == "creado":

                        creados += 1

                    elif resultado == "ya_registrado":

                        ya_registrados += 1

                    elif resultado == "error":

                        errores += 1



                except SaltarPersona:

                    omitidos += 1



                    actualizar_progreso(

                        omitidos=omitidos,

                        creados=creados,

                        ya_registrados=ya_registrados,

                        revisiones=len(REVISIONES_CONTADAS),

                        errores=errores,

                        requiere_revision=False,

                        mensaje="Persona omitida manualmente. Continuando con la siguiente.",

                    )



                    continue



                except PlaywrightTimeoutError as error:

                    print()

                    print("❌ ERROR DE TIEMPO DE ESPERA")

                    print("DOCUMENTO:", documento_inicial)

                    print("Error:", error)

                    errores += 1



                except Exception as error:

                    print()

                    print("❌ ERROR EN EL REGISTRO")

                    print("DOCUMENTO:", documento_inicial)

                    print("Error:", error)

                    errores += 1



                actualizar_progreso(

                    creados=creados,

                    ya_registrados=ya_registrados,

                    omitidos=omitidos,

                    revisiones=len(REVISIONES_CONTADAS),

                    errores=errores,

                    requiere_revision=False,

                )



            print()

            print()

            print("======================================")

            print("          PROCESO FINALIZADO")

            print("======================================")

            print("Total revisados:", total)

            print()

            print("✅ Beneficiarios creados:", creados)

            print("⚠️ Ya registrados:", ya_registrados)

            print("⏭️ Omitidos manualmente:", omitidos)

            print("⏸️ Requirieron revisión:", len(REVISIONES_CONTADAS))

            print("❌ Errores:", errores)

            print("======================================")



            actualizar_progreso(

                estado="finalizado",

                actual=total,

                total=total,

                creados=creados,

                ya_registrados=ya_registrados,

                omitidos=omitidos,

                revisiones=len(REVISIONES_CONTADAS),

                errores=errores,

                requiere_revision=False,

                mensaje="Proceso finalizado.",

            )



    except Exception as error:

        actualizar_progreso(

            estado="error",

            errores=max(errores, PROGRESO.get("errores", 0)),

            requiere_revision=False,

            mensaje=str(error),

        )

        print()

        print("❌ ERROR GENERAL DEL PROCESO")

        print(error)

        raise



    finally:

        eliminar_archivo(ARCHIVO_REVISION)

        eliminar_archivo(ARCHIVO_CORRECCION)



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





if __name__ == "__main__":

    main()
