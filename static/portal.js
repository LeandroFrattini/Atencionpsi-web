document.addEventListener('DOMContentLoaded', function () {
    /* ── Línea de "ahora" en la grilla del día de hoy (una sola vez, no cambia al navegar de día) ── */
    var nowLine = document.querySelector('.portal-now-line');
    if (nowLine) {
        var gridDeHoy = nowLine.closest('.portal-grid');
        var horaInicioHoy = parseFloat(gridDeHoy.dataset.horaInicio);
        var horaFinHoy = parseFloat(gridDeHoy.dataset.horaFin);
        var ahora = new Date();
        var minutosAhora = ahora.getHours() * 60 + ahora.getMinutes();
        var totalMinHoy = (horaFinHoy - horaInicioHoy) * 60;
        var pctHoy = ((minutosAhora - horaInicioHoy * 60) / totalMinHoy) * 100;
        if (pctHoy >= 0 && pctHoy <= 100) {
            nowLine.style.top = pctHoy + '%';
        } else {
            nowLine.style.display = 'none';
        }
    }

    /* ── Al abrir un día, centrar el scroll en "ahora" (si es hoy) o en las 8am ── */
    function ajustarScrollGrilla(panel) {
        var wrap = panel.querySelector('.portal-grid-wrap');
        var gridEl = panel.querySelector('.portal-grid');
        if (!wrap || !gridEl) return;
        var scrollAlto = gridEl.scrollHeight;
        var linea = panel.querySelector('.portal-now-line');
        var objetivo;
        if (linea && linea.style.display !== 'none') {
            objetivo = (parseFloat(linea.style.top) / 100) * scrollAlto - wrap.clientHeight / 2;
        } else {
            var horaInicio = parseFloat(gridEl.dataset.horaInicio);
            var horaFin = parseFloat(gridEl.dataset.horaFin);
            var pct = Math.max(0, (8 - horaInicio) / (horaFin - horaInicio));
            objetivo = pct * scrollAlto - 20;
        }
        wrap.scrollTop = Math.max(0, objetivo);
    }

    /* ── Acordeón semanal: un cuadrado de día por vez ── */
    var semanaGrid = document.getElementById('portal-week-grid');
    if (semanaGrid) {
        var defaultDia = semanaGrid.dataset.default || '0';

        function activarDia(idx) {
            document.querySelectorAll('.portal-day-box').forEach(function (b) {
                b.classList.toggle('portal-day-box-active', b.dataset.dia === idx);
            });
            document.querySelectorAll('.portal-day-panel').forEach(function (p) {
                var activo = p.dataset.diaPanel === idx;
                p.classList.toggle('portal-day-panel-active', activo);
                if (activo) ajustarScrollGrilla(p);
            });
        }

        semanaGrid.querySelectorAll('.portal-day-box').forEach(function (box) {
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

    /* ── Confirmación antes de reagendar (crea un turno nuevo +1 semana) ── */
    document.querySelectorAll('.portal-inline-form').forEach(function (form) {
        if (form.querySelector('.portal-reagendar-btn')) {
            form.addEventListener('submit', function (e) {
                if (!window.confirm('¿Crear un turno nuevo para este paciente la semana que viene, a la misma hora?')) {
                    e.preventDefault();
                }
            });
        }
    });

    /* ── Grilla tipo Google Calendar: tocar un evento abre su detalle abajo ── */
    var eventoOverlay = document.getElementById('portal-evento-overlay');
    if (eventoOverlay) {
        document.querySelectorAll('[data-turno-abrir]').forEach(function (chip) {
            chip.addEventListener('click', function () {
                if (chip.dataset.suprimirClick === '1') {
                    // el click llegó justo después de arrastrar el turno: lo ignoramos
                    chip.dataset.suprimirClick = '';
                    return;
                }
                var id = chip.dataset.turnoAbrir;
                document.querySelectorAll('.portal-evento-detalle').forEach(function (d) {
                    d.classList.toggle('portal-evento-detalle-active', d.dataset.turnoDetalle === id);
                });
                eventoOverlay.classList.add('portal-evento-overlay-visible');
            });
        });

        eventoOverlay.addEventListener('click', function (e) {
            if (e.target === eventoOverlay) {
                eventoOverlay.classList.remove('portal-evento-overlay-visible');
            }
        });

        var cerrarEvento = document.getElementById('portal-evento-cerrar');
        if (cerrarEvento) {
            cerrarEvento.addEventListener('click', function () {
                eventoOverlay.classList.remove('portal-evento-overlay-visible');
            });
        }
    }

    /* ── Arrastrar un turno a otro horario dentro del mismo día ── */
    var etiquetaArrastre = document.getElementById('portal-arrastre-etiqueta');
    var moverForm = document.getElementById('portal-mover-turno-form');

    document.querySelectorAll('.portal-evento').forEach(function (chip) {
        var arrastrando = false;
        var movio = false;
        var startY = 0;
        var startTopPx = 0;
        var gridRect = null;
        var chipAltoPx = 0;
        var gridAltoPx = 0;
        var horaInicio = 0;
        var totalMin = 0;

        chip.addEventListener('pointerdown', function (e) {
            if (e.button !== undefined && e.button !== 0) return;
            var gridEl = chip.closest('.portal-grid');
            gridRect = gridEl.getBoundingClientRect();
            gridAltoPx = gridRect.height;
            horaInicio = parseFloat(gridEl.dataset.horaInicio);
            var horaFin = parseFloat(gridEl.dataset.horaFin);
            totalMin = (horaFin - horaInicio) * 60;

            arrastrando = true;
            movio = false;
            startY = e.clientY;
            var chipRect = chip.getBoundingClientRect();
            startTopPx = chipRect.top - gridRect.top;
            chipAltoPx = chipRect.height;
            chip.setPointerCapture(e.pointerId);
        });

        chip.addEventListener('pointermove', function (e) {
            if (!arrastrando) return;
            var deltaY = e.clientY - startY;
            if (!movio && Math.abs(deltaY) < 6) return;
            movio = true;
            chip.classList.add('portal-evento-arrastrando');

            var nuevaTopPx = Math.max(0, Math.min(gridAltoPx - chipAltoPx, startTopPx + deltaY));
            var minutosPorPx = totalMin / gridAltoPx;
            var minutosSnap = Math.round((nuevaTopPx * minutosPorPx) / 15) * 15;
            var topSnapPct = (minutosSnap / minutosPorPx) / gridAltoPx * 100;
            chip.style.top = topSnapPct + '%';

            var horaMostrar = horaInicio + Math.floor(minutosSnap / 60);
            var minMostrar = minutosSnap % 60;
            if (etiquetaArrastre) {
                etiquetaArrastre.textContent = String(horaMostrar % 24).padStart(2, '0') + ':' + String(minMostrar).padStart(2, '0');
                etiquetaArrastre.style.top = (gridRect.top + (topSnapPct / 100) * gridAltoPx) + 'px';
                etiquetaArrastre.classList.add('portal-arrastre-etiqueta-visible');
            }
        });

        chip.addEventListener('pointerup', function (e) {
            arrastrando = false;
            chip.classList.remove('portal-evento-arrastrando');
            if (etiquetaArrastre) etiquetaArrastre.classList.remove('portal-arrastre-etiqueta-visible');
            if (!movio) return;

            chip.dataset.suprimirClick = '1';

            var minutosPorPx = totalMin / gridAltoPx;
            var topPx = (parseFloat(chip.style.top) / 100) * gridAltoPx;
            var minutosFinal = Math.round((topPx * minutosPorPx) / 15) * 15;
            var horaFinal = (horaInicio + Math.floor(minutosFinal / 60)) % 24;
            var minFinal = minutosFinal % 60;
            var horaTexto = String(horaFinal).padStart(2, '0') + ':' + String(minFinal).padStart(2, '0');
            var nombre = chip.querySelector('.portal-evento-nombre').textContent.trim();

            if (window.confirm('¿Estás seguro que querés reprogramar el turno de ' + nombre + ' para las ' + horaTexto + '?')) {
                moverForm.action = chip.dataset.moverUrl;
                moverForm.querySelector('input[name="hora"]').value = horaFinal;
                moverForm.querySelector('input[name="minuto"]').value = minFinal;
                moverForm.querySelector('input[name="next"]').value = window.location.pathname + window.location.search;
                moverForm.submit();
            } else {
                chip.style.top = (startTopPx / gridAltoPx * 100) + '%';
            }
        });
    });
});
