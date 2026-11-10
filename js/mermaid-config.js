// Mermaid under Material for MkDocs (zensical.yml extra_javascript, loaded after the pinned
// mermaid script and before Material mounts the page).
//
// Material renders every `pre.mermaid` itself: each diagram gets an id of its own
// (`__mermaid_<n>`, a counter that only grows, across instant navigation too) and is drawn in its
// own shadow root. That is what readthedocs needed docs/js/mermaid-init.js for: Mermaid's
// automatic ids repeated on long pages (the event system page's 96 diagrams had 92 ids; a
// %%{init}%% directive restarts them), and a diagram sharing an id was drawn over the earlier one.
//
// Material loads its own Mermaid (unpkg's floating mermaid@11) only when `mermaid` is not already
// defined, so the pinned script before this one is the version it uses.
//
// What Material leaves out is the security level: its mermaid.initialize call keeps Mermaid's
// default, "strict", which disables `click` lines, and the event system page's diagrams link
// their nodes to pygame's reference that way. Every initialize call (Material's) gets "loose", as
// the readthedocs script set.
(function () {
    "use strict";

    if (typeof mermaid === "undefined") {
        return;
    }
    var initialize = mermaid.initialize.bind(mermaid);
    mermaid.initialize = function (configuration) {
        return initialize(Object.assign({}, configuration, {securityLevel: "loose"}));
    };
})();
