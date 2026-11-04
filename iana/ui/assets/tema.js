// Define o tema dos tokens CSS (data-iana-theme). O detector antigo lia a cor
// de fundo do app, mas essa cor vem do nosso próprio CSS (que depende do tema):
// era circular e sempre resultava em "dark". Agora o tema vem do Streamlit
// (st.context.theme, que ignora CSS customizado) e, quando ele ainda não sabe,
// da preferência do sistema, que é o que o Streamlit segue por padrão.
(function() {
    let tema = '__TEMA__';
    if (tema !== 'light' && tema !== 'dark') {
        tema = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-iana-theme', tema);
})();
