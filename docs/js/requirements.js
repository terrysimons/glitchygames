// The requirements page's pickers (docs/requirements.md): a target frame rate and the measure a
// verdict is judged by, applied to every measured platform's games from docs/data/requirements.json.
// The page holds the prose and one empty element per table; this file fills them, and fills them
// again whenever a picker changes.
//
// Rules (the page's "What a machine needs" table): at a target of T FPS the frame budget is
// 1000 / T ms; a game is Recommended under 60% of it (10 ms at 60 FPS, leaving the rest for
// drawing to the screen), at the Minimum under the budget, and Below minimum otherwise.
(function () {
    "use strict";

    var SLOWEST_FPS = 15;
    var FASTEST_FPS = 60;
    var RED_HUE = 0;
    var GREEN_HUE = 120;
    var RECOMMENDED_SHARE_OF_BUDGET = 0.6;
    var TARGETS_FPS = [30, 60];
    var MEASURES = [
        {key: "typical-p99", label: "Typical p99", describe: "the median across runs of each run's 99th-percentile frame"},
        {key: "typical-median", label: "Typical median", describe: "the median across runs of each run's median frame"},
        {key: "slowest-run-p99", label: "Slowest run's p99", describe: "the highest 99th-percentile frame of any run"},
    ];
    var VERDICTS = {
        recommended: "Recommended",
        minimum: "Minimum",
        below: "Below minimum",
    };

    function measuredMilliseconds(measurement, measureKey) {
        if (measureKey === "typical-median") {
            return measurement.median_ms.typical;
        }
        if (measureKey === "slowest-run-p99") {
            return measurement.p99_ms.highest;
        }
        return measurement.p99_ms.typical;
    }

    function verdictFor(milliseconds, targetFps) {
        var budgetMilliseconds = 1000 / targetFps;
        if (milliseconds < budgetMilliseconds * RECOMMENDED_SHARE_OF_BUDGET) {
            return "recommended";
        }
        if (milliseconds < budgetMilliseconds) {
            return "minimum";
        }
        return "below";
    }

    // Red at 15 FPS sliding to green at 60 FPS, clamped at both ends
    function fpsColor(framesPerSecond) {
        var clamped = Math.min(Math.max(framesPerSecond, SLOWEST_FPS), FASTEST_FPS);
        var share = (clamped - SLOWEST_FPS) / (FASTEST_FPS - SLOWEST_FPS);
        return "hsl(" + Math.round(RED_HUE + share * (GREEN_HUE - RED_HUE)) + ", 70%, 82%)";
    }

    function scalePosition(framesPerSecond) {
        return (framesPerSecond - SLOWEST_FPS) / (FASTEST_FPS - SLOWEST_FPS) * 100;
    }

    function element(tag, className, text) {
        var made = document.createElement(tag);
        if (className) {
            made.className = className;
        }
        if (text !== undefined) {
            made.textContent = text;
        }
        return made;
    }

    function range(lowest, highest, unit) {
        var low = lowest.toFixed(1);
        var high = highest.toFixed(1);
        return (low === high ? low : low + "–" + high) + (unit || "");
    }

    // No class: Material styles a typeset table only when it has none (`table:not([class])`)
    function table(headings, rows) {
        var made = element("table");
        var head = made.createTHead().insertRow();
        headings.forEach(function (heading) {
            head.appendChild(element("th", null, heading));
        });
        var body = made.createTBody();
        rows.forEach(function (cells) {
            var row = body.insertRow();
            cells.forEach(function (cell) {
                row.appendChild(cell instanceof Node ? cell : element("td", null, cell));
            });
        });
        return made;
    }

    function pickerGroup(label, options, selectedKey, onPick) {
        var group = element("div", "explorer-picker");
        group.setAttribute("role", "group");
        group.setAttribute("aria-label", label);
        group.appendChild(element("span", "explorer-picker-label", label));
        options.forEach(function (option) {
            var button = element("button", "explorer-picker-option", option.label);
            button.type = "button";
            button.setAttribute("aria-pressed", String(option.key === selectedKey));
            button.addEventListener("click", function () {
                onPick(option.key);
            });
            group.appendChild(button);
        });
        return group;
    }

    function legend(targetFps) {
        var made = element("div", "requirements-legend");
        var stops = [15, 30, 45, 60].map(fpsColor).join(", ");
        var bar = element("div", "requirements-legend-bar");
        bar.style.background = "linear-gradient(to right, " + stops + ")";
        var marker = element("div", "requirements-legend-target");
        marker.style.left = scalePosition(targetFps) + "%";
        marker.title = "Target: " + targetFps + " FPS";
        bar.appendChild(marker);
        made.appendChild(bar);
        var ticks = element("div", "requirements-legend-ticks");
        [15, 30, 45, 60].forEach(function (framesPerSecond) {
            var tick = element("span", null, framesPerSecond + " FPS");
            var position = scalePosition(framesPerSecond);
            tick.style.left = position + "%";
            tick.style.transform = "translateX(-" + position + "%)";
            ticks.appendChild(tick);
        });
        made.appendChild(ticks);
        return made;
    }

    function verdictCell(verdict) {
        var cell = element("td", "requirements-verdict requirements-verdict-" + verdict, VERDICTS[verdict]);
        return cell;
    }

    function fpsCell(framesPerSecond) {
        var cell = element("td", "requirements-fps", String(Math.round(framesPerSecond)));
        cell.style.background = fpsColor(framesPerSecond);
        return cell;
    }

    // Material's content tabs are radio inputs with labels; picking a platform from the summary
    // checks its tab and scrolls to it
    function showPlatformTab(platformName) {
        var labels = document.querySelectorAll(".tabbed-labels > label");
        for (var index = 0; index < labels.length; index++) {
            if (labels[index].textContent.trim() === platformName) {
                labels[index].click();
                labels[index].scrollIntoView({behavior: "smooth", block: "start"});
                return;
            }
        }
    }

    function summary(data, state) {
        var measure = MEASURES.find(function (candidate) {
            return candidate.key === state.measureKey;
        });
        var rows = data.platforms.map(function (platform) {
            var groups = {recommended: [], minimum: [], below: []};
            platform.measurements.forEach(function (measurement) {
                var milliseconds = measuredMilliseconds(measurement, state.measureKey);
                groups[verdictFor(milliseconds, state.targetFps)].push(measurement.name);
            });
            var nameCell = element("td");
            var link = element("a", null, platform.name);
            link.href = "#" + platform.slug;
            link.addEventListener("click", function (event) {
                event.preventDefault();
                showPlatformTab(platform.name);
            });
            nameCell.appendChild(link);
            var everything = platform.measurements.length;
            function listed(names) {
                if (names.length === 0) {
                    return "None";
                }
                return names.length === everything ? "Every game" : names.join(", ");
            }
            return [nameCell, platform.os, listed(groups.recommended), listed(groups.minimum), listed(groups.below)];
        });
        var made = element("div");
        made.appendChild(element(
            "p",
            "explorer-caption",
            "At " + state.targetFps + " FPS (" + (1000 / state.targetFps).toFixed(1) + " ms a frame), judged by "
                + measure.label.toLowerCase() + ": " + measure.describe + ".",
        ));
        made.appendChild(table(["Platform", "OS", "Recommended for", "Minimum for", "Below minimum"], rows));
        return made;
    }

    function platformTables(platform, state) {
        var made = element("div");
        made.appendChild(table(["Machine", platform.name], platform.specs.map(function (spec) {
            return [spec[0], spec[1]];
        })));
        var measure = MEASURES.find(function (candidate) {
            return candidate.key === state.measureKey;
        });
        var rows = platform.measurements.map(function (measurement) {
            var milliseconds = measuredMilliseconds(measurement, state.measureKey);
            return [
                measurement.name,
                verdictCell(verdictFor(milliseconds, state.targetFps)),
                fpsCell(1000 / milliseconds),
                milliseconds.toFixed(1),
                range(measurement.p99_ms.lowest, measurement.p99_ms.highest),
                range(measurement.median_ms.lowest, measurement.median_ms.highest),
                range(measurement.worst_frame_ms.lowest, measurement.worst_frame_ms.highest),
                range(
                    measurement.frames_over_60_fps_budget_percent.lowest,
                    measurement.frames_over_60_fps_budget_percent.highest,
                    "%",
                ),
                String(measurement.runs),
            ];
        });
        made.appendChild(table(
            [
                "Recording", "Verdict", "FPS", measure.label + " (ms)", "p99 (ms)", "Median (ms)",
                "Worst frame (ms)", "Frames over 16.7 ms", "Runs",
            ],
            rows,
        ));
        return made;
    }

    function render(root, data, state) {
        var controls = root.querySelector(".explorer-controls");
        controls.replaceChildren(
            pickerGroup(
                "Target",
                TARGETS_FPS.map(function (targetFps) {
                    return {key: targetFps, label: targetFps + " FPS"};
                }),
                state.targetFps,
                function (targetFps) {
                    state.targetFps = targetFps;
                    render(root, data, state);
                },
            ),
            pickerGroup("Judge by", MEASURES, state.measureKey, function (measureKey) {
                state.measureKey = measureKey;
                render(root, data, state);
            }),
            legend(state.targetFps),
        );
        root.querySelector(".requirements-summary").replaceChildren(summary(data, state));
        document.querySelectorAll(".requirements-platform").forEach(function (holder) {
            var platform = data.platforms.find(function (candidate) {
                return candidate.slug === holder.dataset.platform;
            });
            holder.replaceChildren(platform ? platformTables(platform, state) : element(
                "p",
                null,
                "No measurements for " + holder.dataset.platform + ".",
            ));
        });
    }

    function start() {
        var root = document.querySelector(".requirements-explorer");
        if (!root) {
            return;
        }
        var state = {targetFps: 60, measureKey: "typical-p99"};
        fetch(new URL(root.dataset.source, window.location.href))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("HTTP " + response.status);
                }
                return response.json();
            })
            .then(function (data) {
                render(root, data, state);
            })
            .catch(function (error) {
                root.querySelector(".requirements-summary").textContent =
                    "The measurements could not be loaded (" + error.message + ").";
            });
    }

    // Material's instant navigation swaps pages without a reload; document$ fires for each one
    if (typeof document$ !== "undefined") {
        document$.subscribe(start);
    } else {
        document.addEventListener("DOMContentLoaded", start);
    }
})();
