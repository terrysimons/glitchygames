// The Code Complexity explorer (docs/quality/complexity.md): one chart with pickers for the
// metric, modules or packages, a path filter and how many lines to draw.
//
// The data is complexity-explorer.json, which scripts/generate_complexity_graphs.py writes from
// the wily cache of the whole history (complexity_history): `commits` oldest first, `modules` in
// rank order (total cyclomatic complexity at HEAD, highest first), `packages` by path, and
// `series[path][metric]`, a point `[commit index, value]` at each commit that changed the value.
// Each line is drawn as a step that holds until the next change, extended to the newest commit
// (that last point has no marker: nothing changed there). plotly.js is loaded only on this page,
// from the pinned URL the data names.
(function () {
    "use strict";

    var KINDS = [
        {key: "modules", label: "Modules"},
        {key: "packages", label: "Packages"},
    ];
    var COUNTS = [
        {key: "default", label: null},
        {key: "30", label: "30"},
        {key: "all", label: "All"},
    ];
    var MARKER_SIZE = 6;
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

    // A group of buttons, one pressed; refresh() presses the state's choice again
    function pickerGroup(label, options, currentKey, onPick) {
        var group = element("div", "explorer-picker");
        group.setAttribute("role", "group");
        group.setAttribute("aria-label", label);
        group.appendChild(element("span", "explorer-picker-label", label));
        var buttons = options.map(function (option) {
            var button = element("button", "explorer-picker-option", option.label);
            button.type = "button";
            button.addEventListener("click", function () {
                onPick(option.key);
            });
            group.appendChild(button);
            return {key: option.key, button: button};
        });
        group.refresh = function () {
            var selected = currentKey();
            buttons.forEach(function (entry) {
                entry.button.setAttribute("aria-pressed", String(entry.key === selected));
            });
        };
        group.refresh();
        return group;
    }

    function pickedPaths(data, state) {
        var filter = state.filter.trim().toLowerCase();
        var paths = data[state.kind].filter(function (path) {
            return filter === "" || path.toLowerCase().indexOf(filter) >= 0;
        });
        if (state.count === "all") {
            return paths;
        }
        var count = state.count === "default" ? data.default_count : Number(state.count);
        return paths.slice(0, count);
    }

    function traceFor(data, path, metric) {
        var points = data.series[path][metric];
        var x = [];
        var y = [];
        var hover = [];
        var sizes = [];
        points.forEach(function (point) {
            var commit = data.commits[point[0]];
            x.push(commit.commit);
            y.push(point[1]);
            hover.push(commit.date + " " + commit.message);
            sizes.push(MARKER_SIZE);
        });
        var newest = data.commits.length - 1;
        if (points.length > 0 && points[points.length - 1][0] < newest) {
            x.push(data.commits[newest].commit);
            y.push(points[points.length - 1][1]);
            hover.push("unchanged since");
            sizes.push(0);
        }
        return {
            type: "scatter",
            mode: "lines+markers",
            name: path,
            x: x,
            y: y,
            customdata: hover,
            line: {shape: "hv", width: 2},
            marker: {size: sizes},
            hovertemplate: "%{x}: %{y}<br>%{customdata}<extra>%{fullData.name}</extra>",
        };
    }

    function theme() {
        var style = getComputedStyle(document.body);
        return {
            ink: style.getPropertyValue("--md-default-fg-color").trim(),
            muted: style.getPropertyValue("--md-default-fg-color--light").trim(),
            grid: style.getPropertyValue("--md-default-fg-color--lightest").trim(),
        };
    }

    function draw(holder, data, state) {
        var metric = data.metrics.find(function (candidate) {
            return candidate.key === state.metric;
        });
        var paths = pickedPaths(data, state);
        var traces = paths.map(function (path) {
            return traceFor(data, path, state.metric);
        }).filter(function (trace) {
            return trace.x.length > 0;
        });
        var total = data[state.kind].length;
        holder.caption.textContent = metric.label + " by commit, " + paths.length + " of "
            + total + " " + state.kind + (state.kind === "modules"
                ? " (highest total cyclomatic complexity at the newest commit first)"
                : " (by path)")
            + ". Click a line in the legend to hide it; double-click to show it alone.";
        if (traces.length === 0) {
            window.Plotly.purge(holder.plot);
            holder.plot.replaceChildren(element("p", null, "Nothing matches the filter."));
            return;
        }
        holder.plot.replaceChildren();
        var colors = theme();
        window.Plotly.react(holder.plot, traces, {
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: {color: colors.ink},
            margin: {l: 72, r: 16, t: 16, b: 64},
            hovermode: "closest",
            legend: {font: {color: colors.muted}},
            xaxis: {
                type: "category",
                categoryorder: "array",
                categoryarray: data.commits.map(function (commit) {
                    return commit.commit;
                }),
                title: {text: "commits (evenly spaced, oldest first)"},
                showticklabels: false,
                gridcolor: colors.grid,
                linecolor: colors.grid,
            },
            yaxis: {
                title: {text: metric.label},
                rangemode: "tozero",
                gridcolor: colors.grid,
                linecolor: colors.grid,
                zerolinecolor: colors.grid,
            },
        }, {responsive: true, displaylogo: false});
    }

    function build(root, data) {
        var state = {
            metric: data.metrics[0].key,
            kind: "modules",
            filter: "",
            count: "default",
        };
        var holder = {
            caption: element("p", "explorer-caption"),
            plot: element("div", "explorer-chart"),
        };
        var groups = [];
        function changed() {
            groups.forEach(function (group) {
                group.refresh();
            });
            draw(holder, data, state);
        }
        groups.push(pickerGroup("Metric", data.metrics, function () {
            return state.metric;
        }, function (key) {
            state.metric = key;
            changed();
        }));
        groups.push(pickerGroup("Show", KINDS, function () {
            return state.kind;
        }, function (key) {
            state.kind = key;
            changed();
        }));
        groups.push(pickerGroup("Lines", COUNTS.map(function (option) {
            return {key: option.key, label: option.label || ("Top " + data.default_count)};
        }), function () {
            return state.count;
        }, function (key) {
            state.count = key;
            changed();
        }));
        var filterLabel = element("label", "explorer-picker");
        filterLabel.appendChild(element("span", "explorer-picker-label", "Path contains"));
        var filterInput = element("input");
        filterInput.type = "search";
        filterInput.placeholder = "scenes/, replay, audio/engine.py";
        filterInput.addEventListener("input", function () {
            state.filter = filterInput.value;
            draw(holder, data, state);
        });
        filterLabel.appendChild(filterInput);
        var controls = element("div", "explorer-controls");
        groups.forEach(function (group) {
            controls.appendChild(group);
        });
        controls.appendChild(filterLabel);
        root.replaceChildren(controls, holder.caption, holder.plot);
        draw(holder, data, state);
    }

    function start() {
        var root = document.querySelector(".complexity-explorer");
        if (!root) {
            return;
        }
        root.textContent = "Loading the measurements…";
        fetch(new URL(root.dataset.source, window.location.href))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("HTTP " + response.status);
                }
                return response.json();
            })
            .then(function (data) {
                return loadPlotly(data.plotly).then(function () {
                    build(root, data);
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
