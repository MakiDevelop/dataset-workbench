/**
 * capabilities.js
 *
 * 分析能力清單的載入、渲染、與狀態判斷。
 */

import { state } from "./state.js";

// 分析項目統一映射表：分析選項 key → API 與圖表型態
// 固定映射，避免前端自由選擇造成資料與圖表不符
export const ANALYSIS_MAP = {
  time_trend: { api: "/analysis/time-trend", chart: "line" },
  top_products: { api: "/analysis/top-products", chart: "bar" },
  top_members: { api: "/analysis/top-members", chart: "bar" },
  aov: { api: "/analysis/aov", chart: "line" },
  new_vs_returning: { api: "/analysis/new-vs-returning", chart: "pie" },
};

// 哪些分析支援 granularity（日/月切換）
export const GRANULARITY_SUPPORTED = new Set(["time_trend", "aov"]);

/**
 * 根據資料狀態判斷分析卡片的可用性
 * 回傳值：
 *  - "ok"       : 可直接使用
 *  - "caution"  : 可使用，但需留意
 *  - "disabled" : 不建議或不可使用
 */
export function evaluateAnalysisStatus(analysisKey, status) {
  switch (analysisKey) {
    case "time_trend":
      if (!status.hasTimeColumn) return "disabled";
      if (status.timeUnstable || status.hasSpike) return "caution";
      return "ok";

    case "aov":
      if (!status.hasAmount) return "disabled";
      if (status.amountInconsistent) return "caution";
      return "ok";

    case "top_products":
      if (!status.hasProductId) return "disabled";
      return "ok";

    case "top_members":
      if (!status.hasMemberId) return "disabled";
      if (status.memberUnreliable) return "caution";
      return "ok";

    case "new_vs_returning":
      if (!status.hasMemberId || !status.hasTimeColumn) return "disabled";
      if (status.memberUnreliable) return "caution";
      return "ok";

    default:
      return "ok";
  }
}

/**
 * 渲染分析選項卡片
 */
export function renderCapabilities(capabilities) {
  const optionsContainer = document.getElementById("analysis-options");
  while (optionsContainer.firstChild) {
    optionsContainer.removeChild(optionsContainer.firstChild);
  }

  if (!capabilities || capabilities.length === 0) {
    optionsContainer.textContent = "沒有可用的分析選項";
    return;
  }

  capabilities.forEach((item) => {
    const card = document.createElement("div");
    card.className = "analysis-option-card";
    card.setAttribute("data-key", item.key);

    const label = document.createElement("h3");
    label.textContent = item.label || "無標題";

    const desc = document.createElement("p");
    desc.textContent = item.description || "無描述";

    card.appendChild(label);
    card.appendChild(desc);

    // 套用分析卡片狀態（ok / caution / disabled）
    const status = evaluateAnalysisStatus(item.key, state.datasetStatus);
    card.classList.add(`status-${status}`);
    if (status === "disabled") {
      card.classList.add("disabled");
    }

    optionsContainer.appendChild(card);
  });

  console.debug("[analysis card status rendered]", state.datasetStatus);
}

/**
 * 從後端取得分析能力清單並渲染
 */
export async function loadCapabilities() {
  const optionsContainer = document.getElementById("analysis-options");
  optionsContainer.textContent = "載入分析選項中…";

  try {
    const response = await fetch("/analysis/capabilities");
    if (!response.ok) {
      const errText = await response.text();
      throw new Error(errText || "無法取得分析能力");
    }
    const data = await response.json();
    renderCapabilities(data);
  } catch (err) {
    optionsContainer.textContent = "載入分析選項失敗：" + err.message;
  }
}
