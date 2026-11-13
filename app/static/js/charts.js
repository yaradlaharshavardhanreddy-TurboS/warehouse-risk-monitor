"use strict";

const dashboardCharts = {};

/* =========================================
   DESTROY EXISTING CHART
========================================= */

function destroyChart(chartName) {
    if (dashboardCharts[chartName]) {
        dashboardCharts[chartName].destroy();
        delete dashboardCharts[chartName];
    }
}

/* =========================================
   EXTRACT CHART DATA
   Supports arrays and objects
========================================= */

function getChartEntries(data) {
    if (!data) {
        return [];
    }

    // API returns an array of objects
    if (Array.isArray(data)) {
        return data.map(item => {
            if (!item || typeof item !== "object") {
                return null;
            }

            const labelKey = [
                "category",
                "status",
                "alarm_type",
                "inspection_type",
                "type",
                "name",
                "label"
            ].find(key => item[key] !== undefined);

            const valueKey = [
                "count",
                "total",
                "alarm_count",
                "value"
            ].find(key =>
                item[key] !== undefined &&
                Number.isFinite(Number(item[key]))
            );

            if (!labelKey || !valueKey) {
                return null;
            }

            return {
                label: String(item[labelKey]).replaceAll("_", " "),
                value: Number(item[valueKey])
            };
        }).filter(Boolean);
    }

    // API returns a normal object
    if (typeof data === "object") {
        return Object.entries(data)
            .filter(([, value]) =>
                Number.isFinite(Number(value))
            )
            .map(([label, value]) => ({
                label: label.replaceAll("_", " "),
                value: Number(value)
            }));
    }

    return [];
}

/* =========================================
   EMPTY CHART MESSAGE PLUGIN
========================================= */

const emptyChartPlugin = {
    id: "emptyChartMessage",

    afterDraw(chart) {
        const dataset = chart.data.datasets[0];
        const values = dataset ? dataset.data : [];

        const hasData = values.some(
            value => Number(value) > 0
        );

        if (hasData) {
            return;
        }

        const ctx = chart.ctx;
        const width = chart.width;
        const height = chart.height;

        ctx.save();

        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#64748b";
        ctx.font = "14px Arial";

        ctx.fillText(
            "No data available",
            width / 2,
            height / 2
        );

        ctx.restore();
    }
};

/* =========================================
   DOUGHNUT CHART
========================================= */

function renderDoughnutChart(canvasId, data, label) {
    const canvas = document.getElementById(canvasId);

    if (!canvas || typeof Chart === "undefined") {
        console.error("Chart canvas or Chart.js missing:", canvasId);
        return;
    }

    destroyChart(canvasId);

    const entries = getChartEntries(data);

    dashboardCharts[canvasId] = new Chart(canvas, {
        type: "doughnut",

        data: {
            labels: entries.map(item => item.label),

            datasets: [{
                label: label,
                data: entries.map(item => item.value),
                borderWidth: 2,
                hoverOffset: 8
            }]
        },

        plugins: [emptyChartPlugin],

        options: {
            responsive: true,
            maintainAspectRatio: false,

            plugins: {
                legend: {
                    display: entries.length > 0,
                    position: "bottom"
                },

                tooltip: {
                    enabled: entries.length > 0
                }
            }
        }
    });
}

/* =========================================
   LINE CHART
========================================= */

function renderLineChart(canvasId, data, label) {
    const canvas = document.getElementById(canvasId);

    if (!canvas || typeof Chart === "undefined") {
        console.error("Chart canvas or Chart.js missing:", canvasId);
        return;
    }

    destroyChart(canvasId);

    if (!Array.isArray(data) || data.length === 0) {
        dashboardCharts[canvasId] = new Chart(canvas, {
            type: "line",
            data: {
                labels: [],
                datasets: [{
                    label: label,
                    data: []
                }]
            },
            plugins: [emptyChartPlugin]
        });

        return;
    }

    const first = data[0];

    if (!first || typeof first !== "object") {
        return;
    }

    const labelKey = Object.keys(first).find(
        key => /date|day|timestamp/i.test(key)
    );

    const valueKey = Object.keys(first).find(
        key =>
            key !== labelKey &&
            Number.isFinite(Number(first[key]))
    );

    if (!labelKey || !valueKey) {
        console.error("Invalid trend data:", canvasId);
        return;
    }

    const rows = data.filter(
        row =>
            row &&
            Number.isFinite(Number(row[valueKey]))
    );

    dashboardCharts[canvasId] = new Chart(canvas, {
        type: "line",

        data: {
            labels: rows.map(row => String(row[labelKey])),

            datasets: [{
                label: label,
                data: rows.map(row => Number(row[valueKey])),
                tension: 0.3,
                fill: false,
                borderWidth: 2,
                pointRadius: 4
            }]
        },

        plugins: [emptyChartPlugin],

        options: {
            responsive: true,
            maintainAspectRatio: false,

            plugins: {
                legend: {
                    display: true
                }
            },

            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}
