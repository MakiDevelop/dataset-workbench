/**
 * analysis-runner.js
 *
 * 分析執行邏輯：從點擊分析卡片到 render 圖表的完整流程。
 * - dispatchAnalysis: 主入口，呼叫 API 並渲染結果
 * - renderGranularityControls: 日/月切換 UI
 * - setAnalyzingState: 分析中鎖定狀態
 * - fetchInsight: 取得文字摘要
 */

import { state } from "./state.js";
import { ANALYSIS_MAP, GRANULARITY_SUPPORTED } from "./capabilities.js";
import {
  renderPlotlyChart,
  renderTimeTrendChart,
  renderTopProductsChart,
  renderNewVsReturningPie,
  exportCurrentChartAsPNG,
} from "./chart-renderer.js";

/**
 * 設定分析進行中狀態，鎖定 UI 並顯示狀態訊息
 */
export function setAnalyzingState(isBusy, message) {
  state.isAnalyzing = isBusy;
  const optionsContainer = document.getElementById("analysis-options");
  if (!optionsContainer) return;

  Array.from(optionsContainer.querySelectorAll(".analysis-option-card")).forEach(card => {
    card.style.pointerEvents = isBusy ? "none" : "";
    card.style.opacity = isBusy ? "0.6" : "";
  });

  let statusDiv = optionsContainer.querySelector(".analyzing-status");
  if (!statusDiv) {
    statusDiv = document.createElement("div");
    statusDiv.className = "analyzing-status";
    statusDiv.style.marginTop = "8px";
    statusDiv.style.color = "#0074d9";
    optionsContainer.appendChild(statusDiv);
  }
  statusDiv.textContent = message || "";
  statusDiv.style.display = isBusy ? "" : "none";
}

/**
 * 渲染 granularity 切換 UI（僅 day / month）
 */
export function renderGranularityControls(container, current, onChange) {
  const wrapper = document.createElement("div");
  wrapper.style.display = "flex";
  wrapper.style.gap = "8px";
  wrapper.style.marginBottom = "12px";

  const options = [
    { key: "day", label: "日" },
    { key: "month", label: "月" },
  ];

  options.forEach(opt => {
    const btn = document.createElement("div");
    btn.className = "analysis-option-card";
    btn.textContent = opt.label;
    btn.style.padding = "6px 12px";
    btn.style.cursor = "pointer";
    btn.style.userSelect = "none";

    if (opt.key === current) {
      btn.classList.add("active");
    }

    btn.addEventListener("click", () => {
      if (state.isAnalyzing || opt.key === state.currentGranularity) return;
      onChange(opt.key);
    });

    wrapper.appendChild(btn);
  });

  return wrapper;
}

/**
 * 取得分析結果的文字 insight
 */
export async function fetchInsight(analysisKey, resultData) {
  try {
    const resp = await fetch("/analysis/insight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        analysis_id: state.latestAnalysisId,
        analysis_key: analysisKey,
        result_data: resultData,
      }),
    });
    if (!resp.ok) return "";
    const data = await resp.json();
    return data.insight || "";
  } catch (err) {
    return "";
  }
}

/**
 * 依分析 key 直接執行分析（用於 granularity 切換）
 */
export function runAnalysisByKey(analysisKey) {
  if (!analysisKey) return;
  const card = document.querySelector(
    `.analysis-option-card[data-key="${analysisKey}"]`
  );
  if (!card) return;
  dispatchAnalysis(card);
}

/**
 * 實際執行分析：API 呼叫 + 圖表 render + insight 顯示
 */
export async function dispatchAnalysis(card) {
  const analysisKey = card.getAttribute("data-key");
  if (!analysisKey) return;

  state.currentAnalysisKey = analysisKey;
  state.currentGranularity = state.currentGranularity || "day";

  if (!state.latestAnalysisId) {
    alert("尚未有有效的分析 ID，請先上傳資料。");
    return;
  }

  const mapping = ANALYSIS_MAP[analysisKey];
  if (!mapping) return;

  const panel = document.getElementById("analysis-chart-panel");
  const chartContent = document.getElementById("analysis-chart-content");
  while (chartContent.firstChild) chartContent.removeChild(chartContent.firstChild);

  const chartSection = document.createElement("section");
  chartSection.id = "chart-section";
  state.currentChartContainer = chartSection;

  // granularity UI
  if (GRANULARITY_SUPPORTED.has(analysisKey)) {
    const granularityUI = renderGranularityControls(
      chartSection,
      state.currentGranularity,
      (next) => {
        state.currentGranularity = next;
        runAnalysisByKey(state.currentAnalysisKey);
      }
    );
    chartSection.appendChild(granularityUI);
  }

  // 標題與說明
  const labelElem = card.querySelector("h3");
  const descElem = card.querySelector("p");
  const headerDiv = document.createElement("div");
  headerDiv.style.marginBottom = "16px";

  const h2 = document.createElement("h2");
  h2.textContent = labelElem ? labelElem.textContent : "";
  headerDiv.appendChild(h2);

  const p = document.createElement("p");
  p.textContent = descElem ? descElem.textContent : "";
  p.style.color = "var(--text-muted, #888)";
  headerDiv.appendChild(p);

  // 匯出 PNG 按鈕
  const exportBtn = document.createElement("button");
  exportBtn.type = "button";
  exportBtn.textContent = "匯出 PNG";
  exportBtn.style.marginLeft = "8px";
  exportBtn.addEventListener("click", exportCurrentChartAsPNG);
  headerDiv.appendChild(exportBtn);

  chartSection.appendChild(headerDiv);

  // chart-area：專屬圖表繪製區
  const chartArea = document.createElement("div");
  chartArea.className = "chart-area";
  chartSection.appendChild(chartArea);

  chartContent.appendChild(chartSection);
  panel.classList.remove("hidden");
  panel.classList.add("expanded");

  setAnalyzingState(true, "分析中，請稍候…");

  try {
    let payload = {};
    if (analysisKey === "time_trend" || analysisKey === "aov") {
      payload = { analysis_id: state.latestAnalysisId, granularity: state.currentGranularity };
    } else if (analysisKey === "top_products" || analysisKey === "top_members") {
      payload = { analysis_id: state.latestAnalysisId, limit: 10 };
    } else if (analysisKey === "new_vs_returning") {
      payload = { analysis_id: state.latestAnalysisId };
    }

    const resp = await fetch(mapping.api, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(errText || "無法取得分析資料");
    }

    const data = await resp.json();
    setAnalyzingState(false, "");

    // ===== KPI 摘要（僅適用於時間序列與 AOV） =====
    if ((analysisKey === "time_trend" || analysisKey === "aov") && Array.isArray(data.series)) {
      const kpiWrapper = document.createElement("div");
      kpiWrapper.className = "kpi-summary";
      kpiWrapper.style.display = "flex";
      kpiWrapper.style.gap = "16px";
      kpiWrapper.style.marginBottom = "16px";

      const values = data.series.map(d => typeof d.value === "number" ? d.value : 0);
      const total = values.reduce((a, b) => a + b, 0);
      const avg = values.length ? total / values.length : 0;
      const max = values.length ? Math.max(...values) : 0;

      const kpi1 = _createKpiCard(
        analysisKey === "aov" ? "平均 AOV" : "總金額",
        analysisKey === "aov" ? avg.toFixed(2) : Math.round(total).toLocaleString()
      );
      const kpi2 = _createKpiCard("最大值", Math.round(max).toLocaleString());

      chartSection.insertBefore(kpiWrapper, chartSection.querySelector(".chart-area"));
      kpiWrapper.appendChild(kpi1);
      kpiWrapper.appendChild(kpi2);
    }

    // ===== 渲染圖表（Plotly 優先） =====
    if (data.chart && data.chart.data && typeof Plotly !== "undefined") {
      renderPlotlyChart(chartSection, data.chart);
    } else if (mapping.chart === "line") {
      renderTimeTrendChart(chartSection, data.series);
    } else if (mapping.chart === "bar") {
      const arr = Array.isArray(data.items)
        ? data.items.map((i) => ({ product: i.key, sales: i.value }))
        : [];
      renderTopProductsChart(chartSection, arr);
    } else if (mapping.chart === "pie") {
      renderNewVsReturningPie(chartSection, data.items);
    }

    // ===== 顯示文字 insight =====
    const insightText = await fetchInsight(analysisKey, data);
    if (insightText) {
      const insightDiv = document.createElement("div");
      insightDiv.className = "insight-box";
      const icon = document.createElement("span");
      icon.className = "insight-icon";
      icon.textContent = "💡";
      insightDiv.appendChild(icon);
      const textEl = document.createElement("span");
      textEl.className = "insight-text";
      textEl.textContent = insightText;
      insightDiv.appendChild(textEl);
      chartSection.appendChild(insightDiv);
    }
  } catch (err) {
    setAnalyzingState(false, "");
    const errP = document.createElement("p");
    errP.style.color = "red";
    errP.textContent = "取得分析資料失敗：" + err.message;
    chartSection.appendChild(errP);
  }
}

// ----------- internal helpers -----------

function _createKpiCard(title, value) {
  const card = document.createElement("div");
  card.className = "kpi-card";
  card.style.padding = "12px";
  card.style.border = "1px solid #ddd";
  card.style.borderRadius = "8px";
  card.style.minWidth = "140px";

  const titleEl = document.createElement("div");
  titleEl.style.fontSize = "13px";
  titleEl.style.color = "#666";
  titleEl.textContent = title;

  const valueEl = document.createElement("div");
  valueEl.style.fontSize = "20px";
  valueEl.style.fontWeight = "bold";
  valueEl.textContent = value;

  card.appendChild(titleEl);
  card.appendChild(valueEl);
  return card;
}
