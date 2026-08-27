def preparar_registro(codigo_integracion, personas):
    """
    FASE 1:
    Recibe y valida los datos desde la interfaz web.

    FASE 2:
    Aquí conectaremos tu automatización de Playwright
    para registrar cada beneficiario.
    """

    # Nunca devolvemos ni imprimimos el código de integración completo.
    codigo_oculto = ("*" * max(0, len(codigo_integracion) - 2)) + codigo_integracion[-2:]

    return {
        "modulo": "REGISTRO",
        "registros": len(personas),
        "codigo": codigo_oculto,
        "estado": "Datos recibidos correctamente.",
        "siguiente_paso": (
            "Conectar aquí el flujo Playwright de validación y registro."
        ),
    }
