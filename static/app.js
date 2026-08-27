document.querySelectorAll("[data-toggle-secret]").forEach((button) => {
    button.addEventListener("click", () => {
        const id = button.dataset.toggleSecret;
        const input = document.getElementById(id);
        if (!input) return;

        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.textContent = showing ? "Mostrar" : "Ocultar";
    });
});
