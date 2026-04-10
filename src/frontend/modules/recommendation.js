/**
 * recommendation.js
 *
 * 智慧分析推薦 UI：
 * - loadRecommendations: 取得推薦清單並渲染卡片
 * - runAllRecommended: 一鍵執行所有推薦分析
 */

import { state } from "./state.js";
import { dispatchAnalysis } from "./analysis-runner.js";

// 分析 key → 人類可讀標籤（與後端 capabilities 同步）
const ANALYSIS_LABELS = {
  time_trend: "時間序列趨勢",
  top_products: "熱門商品排行",
  top_members: "高貢獻會員排行",
  aov: "平均客單價（AOV）",
  new_vs_returning: "新客 vs 回購客占比",
};

/**
 * 載入智慧分析推薦並渲染卡片
 */
export async function loadRecommendations(analysisId) {
  const section = document.getElementById("recommendation-section");
  const listContainer = document.getElementById("recommendation-list");
  if (!section || !listContainer) return;

  while (listContainer.firstChild) {
    listContainer.removeChild(listContainer.firstChild);
  }

  try {
    const resp = await fetch("/analysis/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: analysisId }),
    });
    if (!resp.ok) throw new Error("無法取得推薦");
    const data = await resp.json();

    data.recommendations.forEach((rec) => {
      listContainer.appendChild(_renderRecommendationCard(rec));
    });

    section.classList.remove("hidden");
  } catch (err) {
    console.error("Load recommendations failed:", err);
    section.classList.add("hidden");
  }
}

/**
 * 一鍵執行所有推薦分析（依序執行避免競態）
 */
export async function runAllRecommended() {
  if (!state.latestAnalysisId) {
    alert("請先上傳資料");
    return;
  }

  const cards = document.querySelectorAll(".recommendation-card");
  const recommended = Array.from(cards).filter(c =>
    c.classList.contains("status-recommended")
  );

  if (recommended.length === 0) {
    alert("沒有推薦的分析");
    return;
  }

  for (const card of recommended) {
    const key = card.getAttribute("data-key");
    const analysisCard = document.querySelector(
      `.analysis-option-card[data-key="${key}"]`
    );
    if (analysisCard && !analysisCard.classList.contains("disabled")) {
      await dispatchAnalysis(analysisCard);
      await new Promise(r => setTimeout(r, 300));
    }
  }
}

// ----------- internal helpers -----------

function _renderRecommendationCard(rec) {
  const card = document.createElement("div");
  card.className = `recommendation-card status-${rec.status}`;
  card.setAttribute("data-key", rec.key);

  const header = document.createElement("div");
  header.className = "rec-header";

  const label = document.createElement("strong");
  label.textContent = ANALYSIS_LABELS[rec.key] || rec.key;
  header.appendChild(label);

  const scoreSpan = document.createElement("span");
  scoreSpan.className = "rec-score";
  scoreSpan.textContent = `${rec.score} 分`;
  header.appendChild(scoreSpan);

  const statusBadge = document.createElement("span");
  statusBadge.className = `rec-badge badge-${rec.status}`;
  statusBadge.textContent =
    rec.status === "recommended" ? "推薦" :
    rec.status === "caution" ? "注意" : "不建議";
  header.appendChild(statusBadge);

  card.appendChild(header);

  const reason = document.createElement("p");
  reason.className = "rec-reason";
  reason.textContent = rec.reason;
  card.appendChild(reason);

  // 點擊卡片執行對應分析（blocked 除外）
  if (rec.status !== "blocked") {
    card.style.cursor = "pointer";
    card.addEventListener("click", () => {
      const analysisCard = document.querySelector(
        `.analysis-option-card[data-key="${rec.key}"]`
      );
      if (analysisCard && !analysisCard.classList.contains("disabled")) {
        analysisCard.click();
        analysisCard.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  return card;
}
