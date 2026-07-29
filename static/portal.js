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

    /* ── Modal: al marcar un turno como realizado, preguntar si pagó + comentario opcional ── */
    var modal = document.getElementById('portal-realizado-modal');
    var textarea = document.getElementById('portal-comentario-texto');
    var btnGuardar = document.getElementById('portal-comentario-guardar');
    var choiceBtns = modal ? modal.querySelectorAll('.portal-choice-btn') : [];
    var formPendiente = null;
    var pagoElegido = null;

    function abrirModal(form) {
        formPendiente = form;
        pagoElegido = null;
        if (textarea) textarea.value = '';
        choiceBtns.forEach(function (b) { b.classList.remove('portal-choice-btn-selected'); });
        if (btnGuardar) btnGuardar.disabled = true;
        if (modal) modal.classList.add('portal-modal-overlay-visible');
    }

    function cerrarModal(restaurarCheckbox) {
        if (restaurarCheckbox && formPendiente) {
            var checkbox = formPendiente.querySelector('.portal-check-input');
            if (checkbox) { checkbox.checked = false; checkbox.disabled = false; }
        }
        if (modal) modal.classList.remove('portal-modal-overlay-visible');
        formPendiente = null;
        pagoElegido = null;
    }

    document.querySelectorAll('.portal-check-form .portal-check-input').forEach(function (checkbox) {
        checkbox.addEventListener('change', function () {
            if (!checkbox.checked) return;
            checkbox.disabled = true;
            abrirModal(checkbox.closest('form'));
        });
    });

    choiceBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            pagoElegido = btn.dataset.valor;
            choiceBtns.forEach(function (b) { b.classList.remove('portal-choice-btn-selected'); });
            btn.classList.add('portal-choice-btn-selected');
            if (btnGuardar) btnGuardar.disabled = false;
        });
    });

    if (btnGuardar) {
        btnGuardar.addEventListener('click', function () {
            if (!formPendiente || pagoElegido === null) return;
            formPendiente.querySelector('input[name="pagado"]').value = pagoElegido;
            formPendiente.querySelector('input[name="notas_sesion"]').value = textarea.value.trim();
            var form = formPendiente;
            formPendiente = null;
            form.submit();
        });
    }

    var btnCancelar = document.getElementById('portal-comentario-cancelar');
    if (btnCancelar) {
        btnCancelar.addEventListener('click', function () { cerrarModal(true); });
    }

    /* ── Confirmación antes de reagendar +1 semana ── */
    document.querySelectorAll('.portal-inline-form').forEach(function (form) {
        if (form.querySelector('.portal-reagendar-btn')) {
            form.addEventListener('submit', function (e) {
                if (!window.confirm('¿Reagendar este turno una semana después, a la misma hora?')) {
                    e.preventDefault();
                }
            });
        }
    });
});
