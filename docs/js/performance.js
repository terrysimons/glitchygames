// The Replay Performance explorer (docs/quality/performance.md): one chart with pickers for the
// recording, the chart, the statistics and the machines, instead of a frame per recording.
//
// The data is performance-explorer.json, which scripts/generate_performance_graphs.py writes
// beside the graph pages: per recording, the engine's own chart traces (recording_charts in
// src/glitchygames/replay/tools/performance_pages.py), so this draws what each recording's own
// page draws, with the same palette and layout. Each trace's `meta` is its series' slot (an index
// into the recording's `series`, which names the machine and kind of run); a processing or frame
// time trace's name ends in ": p50", ": p99" or ": max" (performance_pages._trace). plotly.js is
// loaded only on this page, from the pinned URL the data names.
(function () {
    "use strict";

    var CHARTS = [
        {
            key: "processing",
            label: "Processing time",
            statistics: true,
            axis: "ms",
            describe: "Processing time per frame (ms), by commit: p50 solid, p99 dashed, max dotted.",
            empty: "No measurements with a known commit yet.",
        },
        {
            key: "fps",
            label: "FPS",
            axis: "fps",
            logarithmic: true,
            target: true,
            describe: "FPS by commit: achieved by live runs (solid), headroom of replays (dashed); "
                + "each bar runs from the 5% low to the 5% high. Log scale.",
            empty: "No measurements with FPS figures yet: rows from before the 5% slices have none.",
        },
        {
            key: "over_budget",
            label: "Frames over budget",
            axis: "frames",
            describe: "Frames whose processing alone took longer than the frame budget, by commit.",
            empty: "No measurements with a frame budget yet.",
        },
        {
            key: "frame_time",
            label: "Live frame time",
            statistics: true,
            axis: "ms",
            describe: "Live runs' frame time (ms), start to start: how steady pacing was.",
            empty: "No live runs with a known commit yet.",
        },
        {
            key: "machines",
            label: "Machines",
            axis: "headroom fps",
            target: true,
            describe: "Headroom FPS of each machine's latest replay; (CI) marks continuous "
                + "integration's noisy virtual runners.",
            empty: "No replays with FPS figures yet.",
        },
    ];
    var STATISTICS = ["p50", "p99", "max"];
    var plotlyLoading = null;

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

    function loadPlotly(url) {
        if (window.Plotly) {
            return Promise.resolve(window.Plotly);
        }
        if (!plotlyLoading) {
            plotlyLoading = new Promise(function (resolve, reject) {
                var script = document.createElement("script");
                script.src = url;
                script.onload = function () {
                    resolve(window.Plotly);
                };
                script.onerror = function () {
                    plotlyLoading = null;
                    reject(new Error("plotly.js did not load"));
                };
                document.head.appendChild(script);
            });
        }
        return plotlyLoading;
    }

    function chartFor(key) {
        return CHARTS.find(function (candidate) {
            return candidate.key === key;
        });
    }

    function statisticOf(trace) {
        return trace.name.split(": ").pop();
    }

    function pickerGroup(label, options, isPressed, onPick) {
        var group = element("div", "explorer-picker");
        group.setAttribute("role", "group");
        group.setAttribute("aria-label", label);
        group.appendChild(element("span", "explorer-picker-label", label));
        options.forEach(function (option) {
            var button = element("button", "explorer-picker-option", option.label);
            button.type = "button";
            button.setAttribute("aria-pressed", String(isPressed(option.key)));
            if (option.color) {
                button.style.borderLeft = "0.5rem solid " + option.color;
            }
            button.addEventListener("click", function () {
                onPick(option.key);
            });
            group.appendChild(button);
        });
        return group;
    }

    function recordingPicker(data, state, onPick) {
        var group = element("label", "explorer-picker");
        group.appendChild(element("span", "explorer-picker-label", "Recording"));
        var select = element("select");
        data.recordings.forEach(function (entry, index) {
            var option = element("option", null, entry.recording);
            option.value = String(index);
            option.selected = index === state.recordingIndex;
            select.appendChild(option);
        });
        select.addEventListener("change", function () {
            onPick(Number(select.value));
        });
        group.appendChild(select);
        return group;
    }

    function toggled(set, key) {
        if (set.has(key)) {
            set.delete(key);
        } else {
            set.add(key);
        }
    }

    function theme(data) {
        var dark = document.body.getAttribute("data-md-color-scheme") === "slate";
        var style = getComputedStyle(document.body);
        return {
            palette: dark ? data.colors.dark : data.colors.light,
            ink: style.getPropertyValue("--md-default-fg-color").trim(),
            muted: style.getPropertyValue("--md-default-fg-color--light").trim(),
            grid: style.getPropertyValue("--md-default-fg-color--lightest").trim(),
        };
    }

    // The traces left after the pickers, colored by series slot (copies: plotly keeps state on
    // the objects it is given)
    function visibleTraces(entry, chart, state, colors) {
        if (chart.key === "machines") {
            var bars = entry.charts.machines;
            if (bars === null) {
                return [];
            }
            var kept = bars.meta.map(function (slot, index) {
                return state.hiddenSlots.has(slot) ? -1 : index;
            }).filter(function (index) {
                return index >= 0;
            });
            if (kept.length === 0) {
                return [];
            }
            var copy = JSON.parse(JSON.stringify(bars));
            ["x", "y", "customdata", "meta"].forEach(function (field) {
                copy[field] = kept.map(function (index) {
                    return bars[field][index];
                });
            });
            ["array", "arrayminus"].forEach(function (field) {
                copy.error_y[field] = kept.map(function (index) {
                    return bars.error_y[field][index];
                });
            });
            copy.marker.color = copy.meta.map(function (slot) {
                return colors.palette[slot % colors.palette.length];
            });
            copy.error_y.color = colors.muted;
            return [copy];
        }
        return entry.charts[chart.key].filter(function (trace) {
            if (state.hiddenSlots.has(trace.meta)) {
                return false;
            }
            return !chart.statistics || state.statistics.has(statisticOf(trace));
        }).map(function (trace) {
            var copy = JSON.parse(JSON.stringify(trace));
            var color = colors.palette[copy.meta % colors.palette.length];
            copy.line.color = color;
            copy.marker.color = color;
            if (copy.error_y) {
                copy.error_y.color = color;
            }
            return copy;
        });
    }

    function layout(entry, chart, colors) {
        var target = entry.charts.target_fps;
        var shapes = [];
        var annotations = [];
        if (chart.target && target !== null) {
            shapes.push({
                type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: target, y1: target,
                line: {color: colors.muted, width: 1.5, dash: "dot"},
            });
            // A log axis places annotations by the value's logarithm
            annotations.push({
                xref: "paper", x: 1, xanchor: "right", yref: "y",
                y: chart.logarithmic ? Math.log10(target) : target, yanchor: "bottom",
                text: "target " + target + " fps", showarrow: false,
                font: {color: colors.muted, size: 11},
            });
        }
        var axisColors = {gridcolor: colors.grid, linecolor: colors.grid};
        var xaxis = chart.key === "machines"
            ? Object.assign({type: "category"}, axisColors)
            : Object.assign({
                type: "category", categoryorder: "array", categoryarray: entry.charts.commits,
                title: {text: "commit"},
            }, axisColors);
        var yaxis = chart.logarithmic
            ? Object.assign({type: "log", title: {text: chart.axis}}, axisColors)
            : Object.assign({rangemode: "tozero", title: {text: chart.axis}, zerolinecolor: colors.grid}, axisColors);
        return {
            shapes: shapes,
            annotations: annotations,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: {color: colors.ink},
            margin: {l: 64, r: 16, t: 40, b: chart.key === "machines" ? 96 : 48},
            hovermode: "closest",
            showlegend: chart.key !== "machines",
            legend: {orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: {color: colors.muted}},
            xaxis: xaxis,
            yaxis: yaxis,
        };
    }

    function render(root, data, state) {
        var entry = data.recordings[state.recordingIndex];
        var chart = chartFor(state.chartKey);
        var colors = theme(data);
        function again() {
            render(root, data, state);
        }
        var controls = [
            recordingPicker(data, state, function (index) {
                state.recordingIndex = index;
                state.hiddenSlots.clear();
                again();
            }),
            pickerGroup("Chart", CHARTS, function (key) {
                return key === state.chartKey;
            }, function (key) {
                state.chartKey = key;
                again();
            }),
        ];
        if (chart.statistics) {
            controls.push(pickerGroup("Statistics", STATISTICS.map(function (statistic) {
                return {key: statistic, label: statistic};
            }), function (key) {
                return state.statistics.has(key);
            }, function (key) {
                toggled(state.statistics, key);
                again();
            }));
        }
        controls.push(pickerGroup("Machines", entry.series.map(function (label, slot) {
            return {key: slot, label: label, color: colors.palette[slot % colors.palette.length]};
        }), function (slot) {
            return !state.hiddenSlots.has(slot);
        }, function (slot) {
            toggled(state.hiddenSlots, slot);
            again();
        }));
        var controlsHolder = element("div", "explorer-controls");
        controls.forEach(function (control) {
            controlsHolder.appendChild(control);
        });
        var caption = element("p", "explorer-caption", chart.describe + " ");
        var pageLink = element("a", null, "This recording's own page, with its heatmaps");
        pageLink.href = root.dataset.pages + entry.page;
        caption.appendChild(pageLink);
        var traces = visibleTraces(entry, chart, state, colors);
        var plot = element("div", "explorer-chart");
        root.replaceChildren(controlsHolder, caption, traces.length === 0
            ? element("p", null, entry.charts[chart.key] === null || entry.charts[chart.key].length === 0
                ? chart.empty
                : "Nothing picked: choose a statistic or a machine above.")
            : plot);
        if (traces.length > 0) {
            window.Plotly.newPlot(plot, traces, layout(entry, chart, colors), {
                responsive: true,
                displaylogo: false,
            });
        }
    }

    function start() {
        var root = document.querySelector(".performance-explorer");
        if (!root) {
            return;
        }
        var state = {
            recordingIndex: 0,
            chartKey: "processing",
            statistics: new Set(STATISTICS),
            hiddenSlots: new Set(),
        };
        root.textContent = "Loading the measurements…";
        fetch(new URL(root.dataset.source, window.location.href))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("HTTP " + response.status);
                }
                return response.json();
            })
            .then(function (data) {
                if (data.recordings.length === 0) {
                    root.textContent = "No measurements yet.";
                    return null;
                }
                return loadPlotly(data.plotly).then(function () {
                    render(root, data, state);
                });
            })
            .catch(function (error) {
                root.textContent = "The measurements could not be loaded (" + error.message + ").";
            });
    }

    // Material's instant navigation swaps pages without a reload; document$ fires for each one
    if (typeof document$ !== "undefined") {
        document$.subscribe(start);
    } else {
        document.addEventListener("DOMContentLoaded", start);
    }
})();
