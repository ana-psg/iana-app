// Um único listener para todos os botões "Copiar resposta". Antes cada
// resposta tinha o próprio iframe com JS.
(function() {
    if (window._ianaCopiarAtivo) return;
    window._ianaCopiarAtivo = true;

    document.addEventListener('click', function(e) {
        const btn = e.target && e.target.closest ? e.target.closest('.iana-copy-btn') : null;
        if (!btn) return;
        const raw = btn.parentElement.querySelector('.iana-raw');
        if (!raw) return;
        navigator.clipboard.writeText(raw.value).then(function() {
            btn.textContent = 'Copiado!';
            btn.classList.add('ok');
            setTimeout(function() {
                btn.textContent = 'Copiar resposta';
                btn.classList.remove('ok');
            }, 1500);
        });
    });
})();
