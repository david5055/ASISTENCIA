// ==========================================================
// DAVIS - JAVASCRIPT GENERAL
// ==========================================================


// ==========================================================
// MOSTRAR / OCULTAR CAMPOS SECRETOS
// ==========================================================

document.querySelectorAll(
    "[data-toggle-secret]"
).forEach((button) => {

    button.addEventListener("click", () => {

        const id =
            button.dataset.toggleSecret;

        const input =
            document.getElementById(id);

        if (!input) return;

        const showing =
            input.type === "text";

        input.type =
            showing
                ? "password"
                : "text";

        button.textContent =
            showing
                ? "Mostrar"
                : "Ocultar";
    });
});


// ==========================================================
// IDENTIFICADOR DEL DISPOSITIVO
//
// El mismo navegador/perfil conserva el mismo ID.
// Todas las pestañas comparten este identificador.
// ==========================================================

(() => {

    const STORAGE_KEY =
        "davis_device_id";

    const COOKIE_NAME =
        "davis_device_id";


    function generarId() {

        if (
            window.crypto
            &&
            typeof crypto.randomUUID
            ===
            "function"
        ) {

            return crypto.randomUUID();
        }


        const bytes =
            new Uint8Array(32);


        if (
            window.crypto
            &&
            typeof crypto.getRandomValues
            ===
            "function"
        ) {

            crypto.getRandomValues(
                bytes
            );

            return Array.from(
                bytes
            )
                .map(
                    (valor) =>
                        valor
                            .toString(16)
                            .padStart(
                                2,
                                "0"
                            )
                )
                .join("");
        }


        return (
            Date.now().toString(36)
            +
            "-"
            +
            Math.random()
                .toString(36)
                .slice(2)
        );
    }


    function leerCookie(
        nombre
    ) {

        const prefijo =
            nombre
            +
            "=";

        const partes =
            document.cookie.split(
                ";"
            );


        for (
            const parteOriginal
            of partes
        ) {

            const parte =
                parteOriginal.trim();

            if (
                parte.startsWith(
                    prefijo
                )
            ) {

                return decodeURIComponent(
                    parte.slice(
                        prefijo.length
                    )
                );
            }
        }

        return "";
    }


    let dispositivoId = "";


    try {

        dispositivoId =
            localStorage.getItem(
                STORAGE_KEY
            )
            ||
            "";

    } catch (error) {

        dispositivoId = "";
    }


    if (!dispositivoId) {

        dispositivoId =
            leerCookie(
                COOKIE_NAME
            );
    }


    if (!dispositivoId) {

        dispositivoId =
            generarId();
    }


    try {

        localStorage.setItem(
            STORAGE_KEY,
            dispositivoId
        );

    } catch (error) {

        // Si localStorage está bloqueado,
        // se mantiene la cookie.
    }


    document.cookie =
        COOKIE_NAME
        +
        "="
        +
        encodeURIComponent(
            dispositivoId
        )
        +
        "; Path=/"
        +
        "; Max-Age=31536000"
        +
        "; SameSite=Lax";

})();


// ==========================================================
// CONTROL DE INACTIVIDAD
// ==========================================================

(() => {

    const body =
        document.body;

    if (!body) return;


    const autenticado =
        body.dataset.davisAuthenticated
        ===
        "1";


    if (!autenticado) {

        return;
    }


    // ======================================================
    // 30 MINUTOS
    // ======================================================

    const LIMITE_MS =
        30
        *
        60
        *
        1000;


    const STORAGE_ACTIVIDAD =
        "davis_ultima_actividad";


    // Máximo un heartbeat cada 45 segundos.
    const INTERVALO_HEARTBEAT_MS =
        45
        *
        1000;


    // Evita escribir muchas veces al mover el mouse.
    const INTERVALO_MARCA_LOCAL_MS =
        1000;


    let ultimoHeartbeat = 0;

    let ultimaMarcaLocal = 0;

    let cerrandoSesion = false;


    function ahora() {

        return Date.now();
    }


    // ======================================================
    // LEER ÚLTIMA ACTIVIDAD
    // ======================================================

    function leerActividad() {

        try {

            const valor =
                Number(
                    localStorage.getItem(
                        STORAGE_ACTIVIDAD
                    )
                );


            if (
                Number.isFinite(
                    valor
                )
                &&
                valor > 0
            ) {

                return valor;
            }

        } catch (error) {

            // Ignorar
        }

        return 0;
    }


    // ======================================================
    // GUARDAR ACTIVIDAD
    // ======================================================

    function guardarActividad(
        timestamp
    ) {

        try {

            localStorage.setItem(
                STORAGE_ACTIVIDAD,
                String(
                    timestamp
                )
            );

        } catch (error) {

            // Ignorar
        }
    }


    // ======================================================
    // CERRAR SESIÓN
    // ======================================================

    function cerrarPorInactividad() {

        if (
            cerrandoSesion
        ) {

            return;
        }

        cerrandoSesion = true;


        window.location.replace(
            "/logout?motivo=inactividad"
        );
    }


    // ======================================================
    // SABER SI YA PASARON 30 MINUTOS
    // ======================================================

    function sesionYaInactiva() {

        const ultima =
            leerActividad();


        if (!ultima) {

            return false;
        }


        return (
            ahora()
            -
            ultima
        )
        >=
        LIMITE_MS;
    }


    // ======================================================
    // HEARTBEAT AL SERVIDOR
    // ======================================================

    async function enviarHeartbeat(
        forzar = false
    ) {

        if (
            cerrandoSesion
        ) {

            return;
        }


        const tiempoActual =
            ahora();


        if (
            !forzar
            &&
            (
                tiempoActual
                -
                ultimoHeartbeat
            )
            <
            INTERVALO_HEARTBEAT_MS
        ) {

            return;
        }


        ultimoHeartbeat =
            tiempoActual;


        try {

            const respuesta =
                await fetch(

                    "/api/auth/actividad",

                    {
                        method:
                            "POST",

                        credentials:
                            "same-origin",

                        cache:
                            "no-store",

                        headers: {

                            "X-DAVIS-ACTIVITY":
                                "1"

                        }

                    }

                );


            if (
                respuesta.status
                ===
                401
            ) {

                cerrandoSesion = true;


                window.location.replace(
                    "/login?motivo=sesion"
                );

            }

        } catch (error) {

            // Si se cae Internet unos segundos,
            // no se cierra inmediatamente.
        }
    }


    // ======================================================
    // REGISTRAR ACTIVIDAD
    // ======================================================

    function registrarActividad(
        forzarHeartbeat = false
    ) {

        if (
            cerrandoSesion
        ) {

            return;
        }


        // ==================================================
        // IMPORTANTE
        //
        // Si ya pasaron 30 minutos,
        // un movimiento nuevo NO revive la sesión.
        // ==================================================

        if (
            sesionYaInactiva()
        ) {

            cerrarPorInactividad();

            return;
        }


        const tiempoActual =
            ahora();


        if (
            (
                tiempoActual
                -
                ultimaMarcaLocal
            )
            >=
            INTERVALO_MARCA_LOCAL_MS
        ) {

            ultimaMarcaLocal =
                tiempoActual;


            guardarActividad(
                tiempoActual
            );

        }


        enviarHeartbeat(
            forzarHeartbeat
        );
    }


    // ======================================================
    // COMPROBAR INACTIVIDAD
    // ======================================================

    function verificarInactividad() {

        if (
            cerrandoSesion
        ) {

            return;
        }


        if (
            sesionYaInactiva()
        ) {

            cerrarPorInactividad();
        }
    }


    // ======================================================
    // NUEVO LOGIN
    // ======================================================

    const inicioSesion =
        Number(

            body.dataset.davisSessionStart
            ||
            "0"

        );


    const actividadGuardada =
        leerActividad();


    if (
        inicioSesion > 0
        &&
        (
            !actividadGuardada
            ||
            actividadGuardada
            <
            inicioSesion
        )
    ) {

        guardarActividad(
            inicioSesion
        );
    }


    // ======================================================
    // ABRIR / NAVEGAR PÁGINA CUENTA COMO ACTIVIDAD
    // ======================================================

    registrarActividad(
        true
    );


    // ======================================================
    // MOVIMIENTOS QUE CUENTAN COMO ACTIVIDAD
    // ======================================================

    const eventos = [

        "mousemove",

        "mousedown",

        "keydown",

        "click",

        "scroll",

        "touchstart",

        "pointerdown"

    ];


    eventos.forEach(
        (evento) => {

            window.addEventListener(

                evento,

                () => {

                    registrarActividad(
                        false
                    );

                },

                {
                    passive:
                        true
                }

            );

        }
    );


    // ======================================================
    // VOLVER A LA PESTAÑA
    // ======================================================

    window.addEventListener(

        "focus",

        () => {

            registrarActividad(
                true
            );

        }

    );


    // ======================================================
    // VOLVER A HACER VISIBLE LA PESTAÑA
    // ======================================================

    document.addEventListener(

        "visibilitychange",

        () => {

            if (
                document.visibilityState
                ===
                "visible"
            ) {

                registrarActividad(
                    true
                );

            }

        }

    );


    // ======================================================
    // REVISAR CADA 15 SEGUNDOS
    // ======================================================

    setInterval(

        verificarInactividad,

        15
        *
        1000

    );

})();