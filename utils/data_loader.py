import csv
import io
import json


class DataError(Exception):
    pass


def _normalizar_lista(datos):
    if isinstance(datos, dict):
        # Permite {"personas": [...]} o un solo objeto.
        if "personas" in datos and isinstance(datos["personas"], list):
            datos = datos["personas"]
        else:
            datos = [datos]

    if not isinstance(datos, list):
        raise DataError("Los datos deben ser una lista de personas.")

    if not datos:
        raise DataError("El archivo o JSON no contiene registros.")

    for indice, persona in enumerate(datos, start=1):
        if not isinstance(persona, dict):
            raise DataError(
                f"El registro {indice} no es un objeto JSON válido."
            )

    return datos


def _leer_json_bytes(contenido):
    try:
        texto = contenido.decode("utf-8-sig")
        datos = json.loads(texto)
        return _normalizar_lista(datos)
    except UnicodeDecodeError:
        raise DataError("El JSON debe estar guardado en UTF-8.")
    except json.JSONDecodeError as error:
        raise DataError(
            f"JSON inválido. Línea {error.lineno}, columna {error.colno}: {error.msg}"
        )


def _leer_csv_bytes(contenido):
    try:
        texto = contenido.decode("utf-8-sig")
        lector = csv.DictReader(io.StringIO(texto))
        filas = [dict(fila) for fila in lector]
        return _normalizar_lista(filas)
    except UnicodeDecodeError:
        raise DataError("El CSV debe estar guardado en UTF-8.")
    except Exception as error:
        raise DataError(f"No se pudo leer el CSV: {error}")


def cargar_personas(archivo=None, texto_json=""):
    """
    Prioridad:
    1. Archivo subido (.json o .csv)
    2. JSON pegado en el textarea
    """
    if archivo and archivo.filename:
        nombre = archivo.filename.lower()
        contenido = archivo.read()

        if not contenido:
            raise DataError("El archivo está vacío.")

        if nombre.endswith(".json"):
            return _leer_json_bytes(contenido)

        if nombre.endswith(".csv"):
            return _leer_csv_bytes(contenido)

        raise DataError("Formato no permitido. Usa .json o .csv.")

    if texto_json.strip():
        try:
            datos = json.loads(texto_json)
            return _normalizar_lista(datos)
        except json.JSONDecodeError as error:
            raise DataError(
                f"JSON pegado inválido. Línea {error.lineno}, columna {error.colno}: {error.msg}"
            )

    raise DataError(
        "Debes subir un archivo JSON/CSV o pegar el JSON en el cuadro."
    )
