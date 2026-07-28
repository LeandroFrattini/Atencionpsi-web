document.addEventListener('DOMContentLoaded', function () {
    /* ── Acordeón semanal: un cuadrado de día por vez ── */
    var grid = document.getElementById('portal-week-grid');
    if (grid) {
        var defaultDia = grid.dataset.default || '0';

        function activarDia(idx) {
            document.querySelectorAll('.portal-day-box').forEach(function (b) {
                b.classList.toggle('portal-day-box-active', b.dataset.dia === idx);
            });
            document.querySelectorAll('.portal-day-panel').forEach(function (p) {
                p.classList.toggle('portal-day-panel-active', p.dataset.diaPanel === idx);
            });
        }

        grid.querySelectorAll('.portal-day-box').forEach(function (box) {
            box.addEventListener('click', function () { activarDia(box.dataset.dia); });
        });

        activarDia(defaultDia);
    }

    /* ── Confirmación + comentario opcional al marcar un turno como realizado ── */
    var modal = document.getElementById('portal-comentario-modal');
    var textarea = document.getElementById('portal-comentario-texto');
    var formPendiente = null;

    function cerrarModal() {
        if (modal) modal.classList.remove('portal-modal-overlay-visible');
        formPendiente = null;
        if (textarea) textarea.value = '';
    }

    document.querySelectorAll('.portal-check-form .portal-check-input').forEach(function (checkbox) {
        checkbox.addEventListener('change', function () {
            if (!checkbox.checked) return;
            var form = checkbox.closest('form');
            var quiereComentario = window.confirm('Turno marcado como realizado.\n\n¿Querés ingresar algún comentario de la sesión?');
            if (!quiereComentario) {
                form.submit();
                return;
            }
            formPendiente = form;
            checkbox.disabled = true;
            if (modal) modal.classList.add('portal-modal-overlay-visible');
            if (textarea) textarea.focus();
        });
    });

    var btnGuardar = document.getElementById('portal-comentario-guardar');
    if (btnGuardar) {
        btnGuardar.addEventListener('click', function () {
            if (!formPendiente) return;
            formPendiente.querySelector('input[name="notas_sesion"]').value = textarea.value.trim();
            formPendiente.submit();
        });
    }

    var btnCancelar = document.getElementById('portal-comentario-cancelar');
    if (btnCancelar) {
        btnCancelar.addEventListener('click', function () {
            if (formPendiente) {
                var checkbox = formPendiente.querySelector('.portal-check-input');
                if (checkbox) { checkbox.checked = false; checkbox.disabled = false; }
            }
            cerrarModal();
        });
    }

    /* ── Confirmación antes de reagendar +1 semana ── */
    document.querySelectorAll('.portal-inline-form').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!window.confirm('¿Reagendar este turno una semana después, a la misma hora?')) {
                e.preventDefault();
            }
        });
    });
});
