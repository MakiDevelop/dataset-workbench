/**
 * app.js — Entry Point
 *
 * 模組結構（Epic 6 重構後）：
 * - modules/state.js          共用狀態
 * - modules/chart-renderer.js Plotly + Chart.js + PNG 匯出
 * - modules/capabilities.js   分析能力清單 + 狀態判斷
 * - modules/analysis-runner.js 分析執行主流程
 * - modules/recommendation.js 智慧推薦 UI
 * - modules/upload.js         上傳 + bootstrap 流程
 *
 * 此檔只負責：
 * 1. 初始化 upload form
 * 2. 綁定分析卡片的點擊事件
 * 3. 綁定圖表面板收合/展開
 * 4. 綁定一鍵執行推薦按鈕
 */

import { state } from "./modules/state.js";
import { initUploadForm } from "./modules/upload.js";
import { dispatchAnalysis } from "./modules/analysis-runner.js";
import { runAllRecommended } from "./modules/recommendation.js";

// ===== 初始化 upload form =====
initUploadForm();

// ===== 分析選項卡片點擊事件（event delegation） =====
const optionsContainer = document.getElementById("analysis-options");
if (optionsContainer) {
  optionsContainer.addEventListener("click", (e) => {
    // 從點擊目標向上找分析卡片
    let card = e.target;
    while (card && !card.classList?.contains("analysis-option-card")) {
      card = card.parentElement;
    }
    if (!card) return;

    // disabled 或分析中 → 禁止點擊
    if (card.classList.contains("disabled") || state.isAnalyzing) {
      return;
    }

    // 切換 active 樣式（單選）
    const allCards = card.parentElement.querySelectorAll(".analysis-option-card");
    allCards.forEach(c => c.classList.remove("active"));
    card.classList.add("active");

    // 記住目前分析 key，並重置 granularity
    state.currentAnalysisKey = card.getAttribute("data-key");
    state.currentGranularity = "day";

    dispatchAnalysis(card);
  });
}

// ===== 分析圖表面板收合/展開 =====
const chartToggleBtn = document.getElementById("chart-toggle");
const chartPanel = document.getElementById("analysis-chart-panel");
if (chartToggleBtn && chartPanel) {
  chartToggleBtn.addEventListener("click", () => {
    if (chartPanel.classList.contains("expanded")) {
      chartPanel.classList.remove("expanded");
      chartPanel.classList.add("hidden");
      chartToggleBtn.textContent = "展開圖表 ▼";
    } else {
      chartPanel.classList.remove("hidden");
      chartPanel.classList.add("expanded");
      chartToggleBtn.textContent = "收合圖表 ▲";
    }
  });
}

// ===== 一鍵執行所有推薦分析 =====
const runAllBtn = document.getElementById("run-all-recommended");
if (runAllBtn) {
  runAllBtn.addEventListener("click", runAllRecommended);
}
