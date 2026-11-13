"use strict";

async function fetchApi(endpoint) {
    const response = await fetch(endpoint, {
        method: "GET",
        headers: {
            "Accept": "application/json"
        }
    });

    if (!response.ok) {
        throw new Error(
            `API request failed: ${endpoint} (${response.status})`
        );
    }

    const result = await response.json();

    if (result.status !== "success") {
        throw new Error(result.message || "API returned an error.");
    }

    return result.data;
}

function setMetric(elementId, value) {
    const element = document.getElementById(elementId);

    if (!element) {
        return;
    }

    element.textContent =
        value === null || value === undefined ? "--" : value;
}

function getReportAnalytics(report) {
    return report && report.analytics ? report.analytics : {};
}

async function loadDashboard() {
    const loading = document.getElementById("dashboard-loading");
    const content = document.getElementById("dashboard-content");
    const error = document.getElementById("dashboard-error");

    loading.classList.remove("hidden");
    content.classList.add("hidden");
    error.classList.add("hidden");

    try {
        const report = await fetchApi("/api/dashboard");
        const analytics = getReportAnalytics(report);

        const alarms = analytics.alarms || {};
        const warehouses = analytics.warehouses || {};
        const inventory = analytics.inventory || {};
        const inspections = analytics.inspections || {};
        const remediations = analytics.remediations || {};
        const trends = analytics.trends || {};

        setMetric(
            "total-warehouses",
            warehouses.total_warehouses
        );

        setMetric(
            "total-alarms",
            alarms.total_alarms
        );

        setMetric(
            "affected-lots",
            inventory.unique_affected_lots
        );

        setMetric(
            "total-inventory",
            inventory.total_inventory_lots
        );

        setMetric(
            "total-inspections",
            inspections.total_inspections
        );

        setMetric(
            "total-remediations",
            remediations.total_remediations
        );

        renderLineChart(
            "alarmTrendChart",
            trends.daily_alarm_trends,
            "Daily alarms"
        );

        renderDoughnutChart(
            "alarmDistributionChart",
            alarms.by_severity,
            "Alarms by severity"
        );

        renderDoughnutChart(
            "inspectionChart",
            inspections.by_status,
            "Inspection status"
        );

        renderDoughnutChart(
            "remediationChart",
            remediations.by_status,
            "Remediation status"
        );

        const reportInformation =
            document.getElementById("report-information");

        reportInformation.textContent =
            `${report.report_name || "Warehouse Analytics"} | ` +
            `Generated: ${report.generated_at || "Not provided"}`;

        loading.classList.add("hidden");
        content.classList.remove("hidden");

    } catch (exception) {
        loading.classList.add("hidden");
        error.classList.remove("hidden");
        error.textContent = exception.message;

        console.error("Dashboard loading error:", exception);
    }
}

document.addEventListener("DOMContentLoaded", loadDashboard);