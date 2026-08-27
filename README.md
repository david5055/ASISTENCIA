# Sistema DAVIS

Base web para los módulos de Registro y Asistencia.

## Recomendación de datos

Usa JSON como formato principal porque conserva los nombres de los campos y
es más seguro para automatizaciones que dependen de claves como `documento`,
`nombre`, `genero`, `departamento`, etc.

CSV también está habilitado para listas simples.

## Instalación en Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
python app.py
```

Abrir:

http://127.0.0.1:5000

## Qué incluye esta primera fase

- Inicio DAVIS.
- Pantalla Registro.
- Código de integración.
- Subida de JSON o CSV.
- Opción de pegar JSON.
- Pantalla Asistencia.
- Enlace de actividad.
- Código de integración.
- JSON/CSV de personas.
- Validación básica de datos.
- Los códigos se muestran ocultos en el resumen.

## Siguiente fase

Conectar el código Playwright real dentro de:

- `services/registro_service.py`
- `services/asistencia_service.py`

No subas archivos con información personal ni códigos de integración a un
repositorio público.
