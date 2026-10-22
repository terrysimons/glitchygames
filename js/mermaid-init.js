// Initialize Mermaid diagrams for mkdocs with readthedocs theme.
// The pymdownx.superfences custom fence emits <pre class="mermaid"><code>...</code></pre>.
// Mermaid expects <pre class="mermaid">...</pre> (no <code> wrapper), so we unwrap first.
document.addEventListener("DOMContentLoaded", function () {
    // Unwrap <code> elements inside <pre class="mermaid"> so Mermaid can find them.
    document.querySelectorAll("pre.mermaid code").forEach(function (codeEl) {
        var preEl = codeEl.parentElement;
        preEl.textContent = codeEl.textContent;
        preEl.classList.add("mermaid");
    });

    mermaid.initialize({
        startOnLoad: true,
        theme: "default",
        securityLevel: "loose",
    });
});
