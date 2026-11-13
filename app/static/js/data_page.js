"use strict";

/* =========================================
   PAGE CONFIGURATION
========================================= */

function getPageApiEndpoint() {
    const config = document.getElementById("page-config");
    const endpoint = config?.dataset?.apiEndpoint;

    if (!endpoint) {
        throw new Error("Page API endpoint configuration is missing.");
    }

    return endpoint;
}

/* =========================================
   FORMATTING HELPERS
========================================= */

function formatLabel(value) {
    return String(value)
        .replaceAll("_", " ")
        .replace(/\b\w/g, character => character.toUpperCase());
}

function formatNumber(value) {
    if (typeof value === "number") {
        return value.toLocaleString("en-IN");
    }

    return String(value);
}

function isPlainObject(value) {
    return value !== null &&
        typeof value === "object" &&
        !Array.isArray(value);
}

function isNumeric(value) {
    return typeof value === "number" &&
        Number.isFinite(value);
}

/* =========================================
   CREATE SUMMARY CARDS
========================================= */

function renderSummary(data) {
    const container = document.getElementById("page-summary");
    container.innerHTML = "";

    if (!isPlainObject(data)) {
        return;
    }

    const preferredKeys = [
        "total_alarms",
        "total_warehouses",
        "total_inventory_lots",
        "unique_affected_lots",
        "total_inspections",
        "total_remediations",
        "completed",
        "scheduled",
        "in_progress",
        "cancelled",
        "completion_percentage",
        "alarm_lot_links"
    ];

    const metrics = preferredKeys
        .filter(key => isNumeric(data[key]))
        .map(key => [key, data[key]]);

    metrics.forEach(([key, value]) => {
        const card = document.createElement("div");
        card.className = "page-metric-card";

        const label = document.createElement("div");
        label.className = "page-metric-label";
        label.textContent = formatLabel(key);

        const number = document.createElement("div");
        number.className = "page-metric-value";

        number.textContent =
            key === "completion_percentage"
                ? `${formatNumber(value)}%`
                : formatNumber(value);

        card.append(label, number);
        container.appendChild(card);
    });
}

/* =========================================
   CREATE DATA TABLE
========================================= */

function renderTable(data, title) {
    const panel = document.createElement("section");
    panel.className = "panel data-section";

    const header = document.createElement("div");
    header.className = "panel-header";

    const heading = document.createElement("h3");
    heading.textContent = formatLabel(title);

    const count = document.createElement("span");
    count.className = "record-count";
    count.textContent = `${data.length} records`;

    header.append(heading, count);
    panel.appendChild(header);

    if (data.length === 0) {
        const empty = document.createElement("div");
        empty.className = "section-empty-state";
        empty.textContent = "No records available.";
        panel.appendChild(empty);
        return panel;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "table-wrapper";

    const table = document.createElement("table");
    table.className = "analytics-table";

    const columns = Array.isArray(data[0])
        ? data[0].map((_, index) => `Column ${index + 1}`)
        : Object.keys(data[0]);

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");

    columns.forEach(column => {
        const th = document.createElement("th");
        th.textContent = formatLabel(column);
        headerRow.appendChild(th);
    });

    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");

    data.forEach(item => {
        const row = document.createElement("tr");

        columns.forEach((column, index) => {
            const cell = document.createElement("td");

            let value;

            if (Array.isArray(item)) {
                value = item[index];
            } else {
                value = item[column];
            }

            if (value === null || value === undefined) {
                cell.textContent = "—";
            } else if (isPlainObject(value) || Array.isArray(value)) {
                cell.textContent = JSON.stringify(value);
            } else {
                cell.textContent = formatNumber(value);
            }

            row.appendChild(cell);
        });

        tbody.appendChild(row);
    });

    table.appendChild(tbody);
    wrapper.appendChild(table);
    panel.appendChild(wrapper);

    return panel;
}

/* =========================================
   CREATE METRIC DETAIL SECTION
========================================= */

function renderMetricSection(data, title) {
    const panel = document.createElement("section");
    panel.className = "panel data-section";

    const heading = document.createElement("div");
    heading.className = "panel-header";

    const titleElement = document.createElement("h3");
    titleElement.textContent = formatLabel(title);

    heading.appendChild(titleElement);
    panel.appendChild(heading);

    const grid = document.createElement("div");
    grid.className = "detail-metric-grid";

    Object.entries(data).forEach(([key, value]) => {
        if (!isNumeric(value) && typeof value !== "string") {
            return;
        }

        const item = document.createElement("div");
        item.className = "detail-metric";

        const label = document.createElement("span");
        label.textContent = formatLabel(key);

        const result = document.createElement("strong");
        result.textContent = formatNumber(value);

        item.append(label, result);
        grid.appendChild(item);
    });

    if (grid.children.length > 0) {
        panel.appendChild(grid);
    }

    return panel;
}

/* =========================================
   RENDER NESTED ANALYTICS
========================================= */

function renderObject(data, title, container) {
    if (!isPlainObject(data)) {
        return;
    }

    const entries = Object.entries(data);

    const arrays = entries.filter(([, value]) =>
        Array.isArray(value)
    );

    const nestedObjects = entries.filter(([, value]) =>
        isPlainObject(value)
    );

    const scalarValues = Object.fromEntries(
        entries.filter(([, value]) =>
            isNumeric(value) || typeof value === "string"
        )
    );

    if (Object.keys(scalarValues).length > 0 && title !== "analytics") {
        const metrics = renderMetricSection(scalarValues, title);
        container.appendChild(metrics);
    }

    arrays.forEach(([key, value]) => {
        const table = renderTable(value, key);
        container.appendChild(table);
    });

    nestedObjects.forEach(([key, value]) => {
        const section = document.createElement("div");
        section.className = "analytics-group";

        const heading = document.createElement("h2");
        heading.className = "analytics-group-title";
        heading.textContent = formatLabel(key);

        section.appendChild(heading);
        renderObject(value, key, section);

        container.appendChild(section);
    });
}

/* =========================================
   MAIN RESPONSE RENDERER
========================================= */

function renderPageData(data) {
    const summary = document.getElementById("page-summary");
    const sections = document.getElementById("page-sections");
    const empty = document.getElementById("page-empty");
    const reportInfo = document.getElementById("page-report-info");

    summary.innerHTML = "";
    sections.innerHTML = "";
    if (reportInfo) reportInfo.innerHTML = "";
    empty.classList.add("hidden");

    if (!isPlainObject(data)) {
        throw new Error("The API returned an unexpected data format.");
    }

    // Consolidated analytics report
    if (isPlainObject(data.analytics)) {
        const analytics = data.analytics;

        renderSummary({
            ...analytics.warehouses,
            ...analytics.alarms,
            ...analytics.inventory,
            ...analytics.inspections,
            ...analytics.remediations
        });

        Object.entries(analytics).forEach(([key, value]) => {
            const group = document.createElement("div");
            group.className = "analytics-group";

            const heading = document.createElement("h2");
            heading.className = "analytics-group-title";
            heading.textContent = formatLabel(key);

            group.appendChild(heading);
            renderObject(value, key, group);

            sections.appendChild(group);
        });

        reportInfo.textContent =
            `${data.report_name || "Warehouse Analytics"} | ` +
            `Generated: ${data.generated_at || "Not provided"}`;

        return;
    }

    // Individual analytics pages
    renderSummary(data);

    const scalarValues = Object.fromEntries(
        Object.entries(data).filter(([, value]) =>
            isNumeric(value) || typeof value === "string"
        )
    );

    if (Object.keys(scalarValues).length > 0) {
        const metrics = renderMetricSection(
            scalarValues,
            "Overview"
        );

        sections.appendChild(metrics);
    }

    Object.entries(data).forEach(([key, value]) => {
        if (Array.isArray(value)) {
            sections.appendChild(renderTable(value, key));
        } else if (isPlainObject(value)) {
            const group = document.createElement("div");
            group.className = "analytics-group";

            const heading = document.createElement("h2");
            heading.className = "analytics-group-title";
            heading.textContent = formatLabel(key);

            group.appendChild(heading);
            renderObject(value, key, group);
            sections.appendChild(group);
        }
    });

    if (!sections.children.length && !summary.children.length) {
        empty.classList.remove("hidden");
    }
}

/* =========================================
   FETCH API
========================================= */

async function loadPageData() {
    const loading = document.getElementById("page-loading");
    const content = document.getElementById("page-content");
    const error = document.getElementById("page-error");

    loading.classList.remove("hidden");
    content.classList.add("hidden");
    error.classList.add("hidden");

    try {
        const endpoint = getPageApiEndpoint();

        const response = await fetch(endpoint, {
            method: "GET",
            headers: {
                "Accept": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(
                `API request failed with status ${response.status}`
            );
        }

        const result = await response.json();

        if (result.status !== "success") {
            throw new Error(
                result.message || "Unable to retrieve analytics."
            );
        }

        renderPageData(result.data);

        loading.classList.add("hidden");
        content.classList.remove("hidden");

    } catch (exception) {
        loading.classList.add("hidden");
        error.classList.remove("hidden");
        error.textContent = exception.message;

        console.error("Page data loading error:", exception);
    }
}

/* =========================================
   PAGE INITIALIZATION
========================================= */

document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.getElementById(
        "refresh-page-data"
    );

    if (refreshButton) {
        refreshButton.addEventListener("click", loadPageData);
    }

    loadPageData();
});
