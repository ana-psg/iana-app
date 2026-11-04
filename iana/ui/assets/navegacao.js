(function() {
    const p = window;
    const doc = p.document;

    if (p._ianaConvNavAttached) return;
    p._ianaConvNavAttached = true;

    doc.addEventListener('click', function(e) {
        const a = e.target && e.target.closest ? e.target.closest('a.conv-item') : null;
        if (!a) return;
        const href = a.getAttribute('href');
        if (!href || !href.startsWith('?load_conv=')) return;

        e.preventDefault();
        e.stopPropagation();

        try {
            p.history.pushState({}, '', href);
        } catch (err) {
            p.location.href = href;
            return;
        }

        const ganchos = [
            '.st-key-nav_trigger_hidden button',
            '[class*="st-key-nav_trigger_hidden"] button',
        ];
        for (const s of ganchos) {
            const b = doc.querySelector(s);
            if (b) { b.click(); return; }
        }
        p.location.href = href;
    }, true);
})();
