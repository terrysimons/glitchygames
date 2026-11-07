// The performance page's list of games (scripts/generate_performance_graphs.py): one game's graphs
// are shown and loaded at a time, and the choice is kept in the page's address so it can be linked.
document.addEventListener("DOMContentLoaded", function () {
    var select = document.getElementById("performance-game");
    if (!select) {
        return;
    }
    var sections = document.querySelectorAll("[data-performance-game]");

    function showGame(game) {
        sections.forEach(function (section) {
            var isChosen = section.dataset.performanceGame === game;
            section.hidden = !isChosen;
            section.querySelectorAll("iframe").forEach(function (frame) {
                var page = isChosen ? frame.dataset.src : "about:blank";
                if (frame.getAttribute("src") !== page) {
                    frame.setAttribute("src", page);
                }
            });
        });
    }

    function isGame(game) {
        return Array.prototype.some.call(select.options, function (option) {
            return option.value === game;
        });
    }

    var gameInAddress = new URLSearchParams(window.location.search).get("game");
    // The first game, not the list's value: a browser can restore that from before a reload
    select.value = isGame(gameInAddress) ? gameInAddress : select.options[0].value;
    showGame(select.value);

    select.addEventListener("change", function () {
        showGame(select.value);
        var url = new URL(window.location.href);
        url.searchParams.set("game", select.value);
        window.history.replaceState(null, "", url);
    });
});
