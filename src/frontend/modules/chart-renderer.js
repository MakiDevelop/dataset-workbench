/**
 * chart-renderer.js
 *
 * 圖表渲染引擎。
 * - Plotly 優先（後端回傳 chart spec 時）
 * - Chart.js fallback（時間趨勢、排行、圓餅）
 * - PNG 匯出（兩種引擎都支援）
 */

import { state } from "./state.js";

/**
 * Plotly 通用渲染函式
 * 接收後端回傳的 chart spec（{ data, layout }）
 * chartSpec 來自自建後端，非使用者輸入，不含 HTML。
 */
export function renderPlotlyChart(container, chartSpec) {
  const chartArea = container.querySelector(".chart-area");
  if (!chartArea) return;

  while (chartArea.firstChild) {
    chartArea.removeChild(chartArea.firstChild);
  }

  if (container._chart) {
    container._chart.destroy();
    container._chart = null;
  }

  const plotDiv = document.createElement("div");
  plotDiv.style.width = "100%";
  plotDiv.style.minHeight = "400px";
  chartArea.appendChild(plotDiv);

  const config = {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToAdd: ["toImage"],
    toImageButtonOptions: {
      format: "png",
      filename: `${state.currentAnalysisKey || "chart"}_${state.currentGranularity || "day"}_${new Date().toISOString().slice(0, 10)}`,
      height: 600,
      width: 1000,
      scale: 2,
    },
    displaylogo: false,
  };

  Plotly.newPlot(plotDiv, chartSpec.data, chartSpec.layout, config);

  container._plotlyDiv = plotDiv;
  container._chart = null;
}

/**
 * Chart.js fallback：時間趨勢折線圖
 * data 格式: [{ time: string, value: number }, ...]
 */
export function renderTimeTrendChart(container, data) {
  const chartArea = container.querySelector(".chart-area");
  if (!chartArea) return;
  while (chartArea.firstChild) chartArea.removeChild(chartArea.firstChild);

  if (!Array.isArray(data) || data.length === 0) {
    const p = document.createElement("p");
    p.textContent = "無時間趨勢資料。";
    chartArea.appendChild(p);
    if (container._chart) {
      container._chart.destroy();
      container._chart = null;
    }
    return;
  }

  if (container._chart) {
    container._chart.destroy();
    container._chart = null;
  }

  const canvas = document.createElement("canvas");
  chartArea.appendChild(canvas);

  const labels = data.map(d => d.time);
  const values = data.map(d => d.value);

  const ctx = canvas.getContext("2d");
  container._chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "",
        data: values,
        borderColor: "#0074d9",
        backgroundColor: "rgba(0,116,217,0.08)",
        fill: false,
        tension: 0.3,
        pointRadius: 3,
        pointHoverRadius: 5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#333", autoSkip: true, maxTicksLimit: 10 } },
        y: { grid: { display: true, color: "#eee" }, beginAtZero: false, ticks: { color: "#333" } },
      },
    },
  });
}

/**
 * Chart.js fallback：熱門商品長條圖
 * data 格式: [{ product: string, sales: number }, ...]
 */
export function renderTopProductsChart(container, data) {
  const chartArea = container.querySelector(".chart-area");
  if (!chartArea) return;
  while (chartArea.firstChild) chartArea.removeChild(chartArea.firstChild);

  if (!Array.isArray(data) || data.length === 0) {
    const p = document.createElement("p");
    p.textContent = "無熱門產品資料。";
    chartArea.appendChild(p);
    if (container._chart) {
      container._chart.destroy();
      container._chart = null;
    }
    return;
  }

  if (container._chart) {
    container._chart.destroy();
    container._chart = null;
  }

  const canvas = document.createElement("canvas");
  chartArea.appendChild(canvas);

  const labels = data.map(d => d.product);
  const values = data.map(d => d.sales);

  const ctx = canvas.getContext("2d");
  container._chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "", data: values, backgroundColor: "#0074d9" }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#333", autoSkip: false, font: { size: 13 } } },
        y: { grid: { display: true, color: "#eee" }, beginAtZero: true, ticks: { color: "#333" } },
      },
    },
  });
}

/**
 * Chart.js fallback：新客 vs 回購客圓餅圖
 * items 格式: [{ key: string, value: number }, ...]
 */
export function renderNewVsReturningPie(container, items) {
  const chartArea = container.querySelector(".chart-area");
  if (!chartArea) return;
  while (chartArea.firstChild) chartArea.removeChild(chartArea.firstChild);

  if (!Array.isArray(items) || items.length === 0 || items.every(x => !x.value || x.value === 0)) {
    const p = document.createElement("p");
    p.textContent = "無新客與回購客占比資料。";
    chartArea.appendChild(p);
    if (container._chart) {
      container._chart.destroy();
      container._chart = null;
    }
    return;
  }

  if (container._chart) {
    container._chart.destroy();
    container._chart = null;
  }

  const safeItems = items.slice(0, 2).map((x, i) => ({
    key: x.key || (i === 0 ? "新客" : "回購客"),
    value: typeof x.value === "number" ? x.value : parseFloat(x.value) || 0,
  }));
  const total = safeItems.reduce((a, b) => a + (b.value || 0), 0);
  if (!total) {
    const p = document.createElement("p");
    p.textContent = "無新客與回購客占比資料。";
    chartArea.appendChild(p);
    return;
  }

  const canvas = document.createElement("canvas");
  chartArea.appendChild(canvas);

  const ctx = canvas.getContext("2d");
  container._chart = new Chart(ctx, {
    type: "pie",
    data: {
      labels: safeItems.map(item => item.key),
      datasets: [{
        data: safeItems.map(item => item.value),
        backgroundColor: ["#0074d9", "#FF851B"],
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: "right",
          labels: { color: "#333", font: { size: 15 } },
        },
      },
    },
  });
}

/**
 * 匯出當前圖表為 PNG
 * 優先 Plotly（用 Plotly.downloadImage），fallback 到 Chart.js（toBase64Image）
 */
export function exportCurrentChartAsPNG() {
  const key = state.currentAnalysisKey || "chart";
  const gran = state.currentGranularity || "day";
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `${key}_${gran}_${ts}.png`;

  if (state.currentChartContainer && state.currentChartContainer._plotlyDiv) {
    Plotly.downloadImage(state.currentChartContainer._plotlyDiv, {
      format: "png",
      filename: filename.replace(".png", ""),
      height: 600,
      width: 1000,
      scale: 2,
    });
    return;
  }

  if (state.currentChartContainer && state.currentChartContainer._chart) {
    const chart = state.currentChartContainer._chart;
    const dataUrl = chart.toBase64Image("image/png", 1);
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return;
  }

  alert("目前沒有可匯出的圖表，請先點選一個分析。");
}
