/**
 * state.js
 *
 * 共用的前端應用狀態。
 * 其他模組 import state 後直接讀寫屬性（mutable live binding）。
 */

export const state = {
  // 最新上傳的 analysis_id（bootstrap 後設定）
  latestAnalysisId: null,

  // 目前選中的分析 key
  currentAnalysisKey: null,

  // 時間粒度（day / month）
  currentGranularity: "day",

  // 分析中狀態鎖
  isAnalyzing: false,

  // 目前顯示中的 chart container（供 PNG 匯出用）
  currentChartContainer: null,

  // Dataset 狀態快照（由 bootstrap 結果推導，供分析卡片狀態判斷使用）
  datasetStatus: {
    hasTimeColumn: false,
    hasAmount: false,
    hasProductId: false,
    hasMemberId: false,
    timeUnstable: false,
    hasSpike: false,
    amountInconsistent: false,
    memberUnreliable: false,
  },
};

/**
 * 重置 datasetStatus 為初始值（新檔案上傳時呼叫）。
 */
export function resetDatasetStatus() {
  state.datasetStatus = {
    hasTimeColumn: false,
    hasAmount: false,
    hasProductId: false,
    hasMemberId: false,
    timeUnstable: false,
    hasSpike: false,
    amountInconsistent: false,
    memberUnreliable: false,
  };
}
