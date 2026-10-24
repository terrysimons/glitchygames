// Initialize Mermaid diagrams for mkdocs with readthedocs theme.
// The pymdownx.superfences custom fence emits <pre class="mermaid"><code>...</code></pre>.
// Mermaid expects <pre class="mermaid">...</pre> (no <code> wrapper), so we unwrap first.
document.addEventListener("DOMContentLoaded", async function () {
    // Unwrap <code> elements inside <pre class="mermaid"> so Mermaid can find them.
    document.querySelectorAll("pre.mermaid code").forEach(function (codeEl) {
        var preEl = codeEl.parentElement;
        preEl.textContent = codeEl.textContent;
        preEl.classList.add("mermaid");
    });

    mermaid.initialize({
        startOnLoad: false,
        theme: "default",
        securityLevel: "loose",
    });

    // Each diagram is rendered here with an id of its own: Mermaid's automatic ids repeated on
    // long pages (the event system page's 96 diagrams had 92 ids; a %%{init}%% directive
    // restarts them), and a diagram sharing an id is drawn over the earlier one. One at a time,
    // in page order, as startOnLoad would.
    var diagrams = document.querySelectorAll("pre.mermaid");
    for (var index = 0; index < diagrams.length; index++) {
        var diagram = diagrams[index];
        try {
            var rendered = await mermaid.render("glitchygames-diagram-" + index, diagram.textContent);
            diagram.innerHTML = rendered.svg;
            if (rendered.bindFunctions) {
                rendered.bindFunctions(diagram);
            }
        } catch (error) {
            // Keep a broken diagram visible as its error, as startOnLoad does
            diagram.textContent = "Diagram error: " + error;
        }
    }
});
