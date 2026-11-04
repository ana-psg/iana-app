(function() {
    const p = window;
    const doc = p.document;

    // Roda na própria página (st.html): o botão sobrevive aos reruns,
    // então só é criado uma vez.
    if (doc.getElementById('iana-sidebar-toggle')) return;

    const btn = doc.createElement('button');
    btn.id = 'iana-sidebar-toggle';
    btn.setAttribute('aria-label', 'Alternar barra lateral');
    btn.style.cssText = [
        'position: fixed',
        'top: 12px',
        'left: 12px',
        'width: 28px',
        'height: 28px',
        'border-radius: 8px',
        'border: 1px solid #222226',
        'background: #1C1C20',
        'color: #B4B4BC',
        'cursor: pointer',
        'display: flex',
        'align-items: center',
        'justify-content: center',
        'z-index: 2147483000',
        'padding: 0',
        'font-size: 15px',
        'line-height: 1',
        'font-weight: 700',
        'font-family: -apple-system, BlinkMacSystemFont, sans-serif',
        'pointer-events: auto',
        'user-select: none',
        'transition: left 0.25s ease, background 0.15s ease, color 0.15s ease, border-color 0.15s ease'
    ].join(';');

    function cores() {
        const isDark = (doc.documentElement.getAttribute('data-iana-theme') || 'dark') === 'dark';
        return {
            bg: isDark ? '#1C1C20' : '#F0F0F4',
            border: isDark ? '#222226' : '#E5E5EB',
            text: isDark ? '#B4B4BC' : '#4B4B52'
        };
    }

    let ultimoEstado = '';
    function atualizar(forcar) {
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        const r = sidebar ? sidebar.getBoundingClientRect() : null;
        const aberta = !!r && r.width > 60 && r.right > 40;
        const left = aberta ? (r.right + 18) + 'px' : '12px';
        const tema = doc.documentElement.getAttribute('data-iana-theme') || 'dark';

        // Só mexe no DOM quando algo mudou. Antes reescrevia a cada 200 ms,
        // o que também apagava a cor de hover logo após o mouse entrar.
        const estado = aberta + '|' + left + '|' + tema;
        if (estado === ultimoEstado && forcar !== true) return;
        ultimoEstado = estado;

        btn.textContent = aberta ? '‹' : '›';
        btn.style.left = left;

        const c = cores();
        btn.style.background = c.bg;
        btn.style.borderColor = c.border;
        btn.style.color = c.text;
    }

    function disparar() {
        const candidatos = [
            '[data-testid="stSidebarCollapseButton"] button',
            '[data-testid="stSidebarCollapsedControl"] button',
            '[data-testid="stExpandSidebarButton"] button',
            '[data-testid="stSidebarNavCollapseButton"] button',
            '[data-testid="stCollapsedControl"] button',
            '[data-testid="collapsedControl"] button',
            '[data-testid="stSidebarCollapseButton"]',
            '[data-testid="stSidebarCollapsedControl"]',
            '[data-testid="stExpandSidebarButton"]',
            '[data-testid="stSidebarNavCollapseButton"]',
            '[data-testid="stCollapsedControl"]',
            '[data-testid="collapsedControl"]',
            'button[kind="header"]',
            'button[kind="headerNoPadding"]',
            'button[aria-label="Close sidebar"]',
            'button[aria-label="Open sidebar"]',
            'button[aria-label="close sidebar"]',
            'button[aria-label="open sidebar"]',
            'button[title="Close sidebar"]',
            'button[title="Open sidebar"]',
        ];
        for (const s of candidatos) {
            const el = doc.querySelector(s);
            if (el) { el.click(); return true; }
        }
        return false;
    }

    btn.addEventListener('click', function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        disparar();
        setTimeout(atualizar, 60);
        setTimeout(atualizar, 320);  // depois da animação da sidebar
    });

    btn.addEventListener('mouseenter', function() {
        btn.style.color = '#EC4899';
        btn.style.borderColor = '#EC4899';
    });
    btn.addEventListener('mouseleave', function() { atualizar(true); });

    doc.body.appendChild(btn);

    atualizar(true);
    setInterval(atualizar, 300);
})();
