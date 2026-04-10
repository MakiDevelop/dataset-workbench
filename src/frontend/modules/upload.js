/**
 * upload.js
 *
 * 檔案上傳 + bootstrap 分析流程。
 * 負責：
 * - 處理 upload form submit
 * - 呼叫 /analysis/bootstrap
 * - 更新 datasetStatus
 * - 渲染 overview / grains / risk / preview
 * - 觸發 capabilities 與 recommendation 載入
 */

import { state, resetDatasetStatus } from "./state.js";
import { loadCapabilities } from "./capabilities.js";
import { loadRecommendations } from "./recommendation.js";

/**
 * 初始化上傳表單（在 DOMContentLoaded 後呼叫）
 */
export function initUploadForm() {
  const form = document.getElementById("upload-form");
  const result = document.getElementById("result");
  if (!form || !result) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fileInput = document.getElementById("file");
    const file = fileInput.files[0];

    if (!file) {
      alert("請先選擇檔案");
      return;
    }

    result.textContent = "分析中，請稍候…";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/analysis/bootstrap", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.text();
        throw new Error(err);
      }

      const data = await response.json();

      // ===== 重置 datasetStatus + 從 bootstrap 結果填入 =====
      resetDatasetStatus();
      _populateDatasetStatus(data);

      console.debug("[datasetStatus]", state.datasetStatus);

      // 儲存最新的 analysis_id
      state.latestAnalysisId = data.analysis_id || null;

      // ===== 顯示 Analysis ID 與 Overview 入口 =====
      _showAnalysisEntry(state.latestAnalysisId);

      // 清空結果區域
      result.textContent = "";

      // 建立結果容器並渲染各區塊
      const container = document.createElement("div");
      container.appendChild(_renderOverviewSection(data));
      container.appendChild(_renderGrainsSection(data));
      container.appendChild(_renderRiskSection(data));
      container.appendChild(_renderPreviewSection(data));
      result.appendChild(container);

      // ===== 載入可用分析 + 智慧推薦 =====
      loadCapabilities();
      loadRecommendations(state.latestAnalysisId);

    } catch (err) {
      result.textContent = "發生錯誤：\n" + err.message;
    }
  });
}

// ----------- internal: datasetStatus population -----------

function _populateDatasetStatus(data) {
  state.datasetStatus.hasTimeColumn = !!(
    data.overview &&
    (
      data.overview.time_column ||
      (data.overview.datetime_columns && data.overview.datetime_columns.length > 0) ||
      (data.overview.date_range && Object.keys(data.overview.date_range).length > 0)
    )
  );

  state.datasetStatus.hasAmount = !!(
    data.preview &&
    Array.isArray(data.preview) &&
    data.preview.length > 0 &&
    (
      "order_total" in data.preview[0] ||
      "order_total_amount" in data.preview[0] ||
      "total_amount" in data.preview[0]
    )
  );

  state.datasetStatus.hasProductId = !!(
    data.preview &&
    Array.isArray(data.preview) &&
    data.preview.length > 0 &&
    (
      "product_id" in data.preview[0] ||
      "product_name" in data.preview[0]
    )
  );

  state.datasetStatus.hasMemberId = !!(
    data.preview &&
    Array.isArray(data.preview) &&
    data.preview.length > 0 &&
    "member_id" in data.preview[0]
  );

  // 風險旗標（從 blacklist 推導）
  if (Array.isArray(data.blacklist)) {
    data.blacklist.forEach(item => {
      const reason = typeof item.reason === "string" ? item.reason.toLowerCase() : "";
      const metric = typeof item.metric === "string" ? item.metric.toLowerCase() : "";

      if (reason.includes("time") || metric.includes("time")) {
        state.datasetStatus.timeUnstable = true;
      }
      if (reason.includes("spike") || reason.includes("波動")) {
        state.datasetStatus.hasSpike = true;
      }
      if (reason.includes("amount") || metric.includes("amount") || reason.includes("金額")) {
        state.datasetStatus.amountInconsistent = true;
      }
      if (reason.includes("member") || reason.includes("會員")) {
        state.datasetStatus.memberUnreliable = true;
      }
    });
  }
}

function _showAnalysisEntry(analysisId) {
  const entrySection = document.getElementById("analysis-entry");
  const idValue = document.getElementById("analysis-id-value");
  const overviewLink = document.getElementById("go-overview-link");

  if (entrySection && idValue && overviewLink && analysisId) {
    idValue.textContent = analysisId;
    overviewLink.href = `/overview?analysis_id=${analysisId}`;
    entrySection.classList.remove("hidden");
  }
}

// ----------- internal: section renderers -----------

function _renderOverviewSection(data) {
  const section = document.createElement("section");
  const title = document.createElement("h2");
  title.textContent = "資料總覽";
  section.appendChild(title);

  const list = document.createElement("ul");
  if (data.overview) {
    if ("row_count" in data.overview) {
      const li = document.createElement("li");
      li.textContent = `資料筆數: ${data.overview.row_count}`;
      list.appendChild(li);
    }
    if ("time_column" in data.overview) {
      const li = document.createElement("li");
      li.textContent = `時間欄位: ${data.overview.time_column}`;
      list.appendChild(li);
    }
    if ("time_range" in data.overview && data.overview.time_range && typeof data.overview.time_range === "object") {
      const tr = data.overview.time_range;
      if ("min" in tr && "max" in tr) {
        const li = document.createElement("li");
        li.textContent = `時間範圍: ${tr.min} ~ ${tr.max}`;
        list.appendChild(li);
      }
    }
  }
  section.appendChild(list);
  return section;
}

function _renderGrainsSection(data) {
  const section = document.createElement("section");
  const title = document.createElement("h2");
  title.textContent = "資料粒度";
  section.appendChild(title);

  if ("grains" in data && Array.isArray(data.grains) && data.grains.length > 0) {
    const list = document.createElement("ul");
    data.grains.forEach((grain) => {
      const li = document.createElement("li");
      li.textContent = grain;
      list.appendChild(li);
    });
    section.appendChild(list);
  } else {
    const p = document.createElement("p");
    p.textContent = "無資料粒度資訊";
    section.appendChild(p);
  }
  return section;
}

function _renderRiskSection(data) {
  const section = document.createElement("section");
  const title = document.createElement("h2");
  title.textContent = "分析風險提示";
  section.appendChild(title);

  if ("blacklist" in data && Array.isArray(data.blacklist) && data.blacklist.length > 0) {
    const list = document.createElement("ul");
    data.blacklist.forEach((item) => {
      const li = document.createElement("li");
      let icon = "ℹ️";
      if (item.severity === "block") icon = "🚫";
      else if (item.severity === "warning") icon = "⚠️";
      const grainText = item.grain ? ` [粒度: ${item.grain}]` : "";
      const metricText = item.metric ? ` [指標: ${item.metric}]` : "";
      li.textContent = `${icon} ${item.reason || ""}${grainText}${metricText}`;
      list.appendChild(li);
    });
    section.appendChild(list);
  } else {
    const p = document.createElement("p");
    p.textContent = "無風險提示";
    section.appendChild(p);
  }
  return section;
}

function _renderPreviewSection(data) {
  const section = document.createElement("section");
  section.className = "section";
  const title = document.createElement("h2");
  title.textContent = "資料預覽（前 100 筆）";
  section.appendChild(title);

  const previewData = data.preview;
  if (!previewData || !Array.isArray(previewData) || previewData.length === 0) {
    const p = document.createElement("p");
    p.textContent = "（此階段尚未提供資料預覽）";
    section.appendChild(p);
    return section;
  }

  const previewRows = previewData.slice(0, 100);
  const columns = Object.keys(previewRows[0] || {});

  const table = document.createElement("table");
  table.style.borderCollapse = "collapse";
  table.style.marginBottom = "8px";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    th.style.border = "1px solid #ccc";
    th.style.padding = "4px";
    th.style.backgroundColor = "#f0f0f0";
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  table.appendChild(tbody);

  // 分頁
  const rowsPerPage = 10;
  let currentPage = 1;
  const totalPages = Math.ceil(previewRows.length / rowsPerPage);

  function renderTablePage(page) {
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
    const startIdx = (page - 1) * rowsPerPage;
    const endIdx = Math.min(startIdx + rowsPerPage, previewRows.length);
    for (let i = startIdx; i < endIdx; i++) {
      const row = previewRows[i];
      const tr = document.createElement("tr");
      columns.forEach((col) => {
        const td = document.createElement("td");
        td.textContent = row[col] !== undefined && row[col] !== null ? row[col] : "";
        td.style.border = "1px solid #ccc";
        td.style.padding = "4px";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
  }

  const paginationDiv = document.createElement("div");
  paginationDiv.style.display = "flex";
  paginationDiv.style.justifyContent = "center";
  paginationDiv.style.gap = "8px";
  paginationDiv.style.marginBottom = "16px";

  const prevBtn = document.createElement("button");
  prevBtn.textContent = "上一頁";
  prevBtn.disabled = true;

  const pageInfo = document.createElement("span");
  pageInfo.textContent = `第 ${currentPage} 頁 / 共 ${totalPages} 頁`;
  pageInfo.style.alignSelf = "center";

  const nextBtn = document.createElement("button");
  nextBtn.textContent = "下一頁";
  nextBtn.disabled = totalPages <= 1;

  prevBtn.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      renderTablePage(currentPage);
      pageInfo.textContent = `第 ${currentPage} 頁 / 共 ${totalPages} 頁`;
      nextBtn.disabled = false;
      if (currentPage === 1) prevBtn.disabled = true;
    }
  });

  nextBtn.addEventListener("click", () => {
    if (currentPage < totalPages) {
      currentPage++;
      renderTablePage(currentPage);
      pageInfo.textContent = `第 ${currentPage} 頁 / 共 ${totalPages} 頁`;
      prevBtn.disabled = false;
      if (currentPage === totalPages) nextBtn.disabled = true;
    }
  });

  paginationDiv.appendChild(prevBtn);
  paginationDiv.appendChild(pageInfo);
  paginationDiv.appendChild(nextBtn);

  const tableWrapper = document.createElement("div");
  tableWrapper.className = "table-scroll";
  tableWrapper.style.maxHeight = "400px";
  tableWrapper.style.overflow = "auto";
  tableWrapper.appendChild(table);

  section.appendChild(tableWrapper);
  section.appendChild(paginationDiv);

  renderTablePage(currentPage);
  return section;
}
