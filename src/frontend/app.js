const form = document.getElementById("upload-form");
const result = document.getElementById("result");



let latestAnalysisId = null; // 用來儲存最新的 analysis_id，供 Step B 使用

// ===== Dataset status snapshot (derived from Overview) =====
// 僅描述資料狀態，不直接影響 UI，供分析卡片判斷使用
let datasetStatus = {
  hasTimeColumn: false,
  hasAmount: false,
  hasProductId: false,
  hasMemberId: false,

  // 風險與不穩定性旗標
  timeUnstable: false,
  hasSpike: false,
  amountInconsistent: false,
  memberUnreliable: false,
};

// 工具函式：格式化檔案大小（MB）
function formatFileSizeMB(sizeMB) {
  if (sizeMB === null || sizeMB === undefined) return "-";
  return `${sizeMB} MB`;
}

let currentChartContainer = null; // 目前圖表所屬的 container（保存 Chart.js instance 用）

// ===== Granularity（時間粒度）狀態 =====
// 只允許 day / month，由 UI 控制，避免不合法參數
let currentGranularity = "day";
let currentAnalysisKey = null; // 記住目前執行中的分析

// ===== Step A: 顯示可用分析 =====
// 這裡定義一個函式用來渲染分析選項，顯示 label 與 description，並將 key 存在 data-key 屬性中
// 目前僅呈現選項，尚未綁定點擊行為（Step B 會負責）
function renderCapabilities(capabilities) {
  const optionsContainer = document.getElementById("analysis-options");
  optionsContainer.innerHTML = ""; // 清空舊內容

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

    // ===== 套用分析卡片狀態（ok / caution / disabled）=====
    const status = evaluateAnalysisStatus(item.key, datasetStatus);
    card.classList.add(`status-${status}`);
    if (status === "disabled") {
      card.classList.add("disabled");
    }

    optionsContainer.appendChild(card);
  });
  // Debug：顯示目前 datasetStatus 狀態
  console.debug("[analysis card status rendered]", datasetStatus);
}

// 取得分析能力清單，成功後呼叫 renderCapabilities，失敗則顯示錯誤訊息
async function loadCapabilities() {
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

    // ===== Populate datasetStatus from bootstrap result =====
    // 基本欄位存在性（結構）
    datasetStatus.hasTimeColumn = !!(
      data.overview &&
      (
        data.overview.time_column ||
        (data.overview.datetime_columns && data.overview.datetime_columns.length > 0) ||
        (data.overview.date_range && Object.keys(data.overview.date_range).length > 0)
      )
    );

    datasetStatus.hasAmount = !!(
      data.preview &&
      Array.isArray(data.preview) &&
      data.preview.length > 0 &&
      (
        "order_total" in data.preview[0] ||
        "order_total_amount" in data.preview[0] ||
        "total_amount" in data.preview[0]
      )
    );

    datasetStatus.hasProductId = !!(
      data.preview &&
      Array.isArray(data.preview) &&
      data.preview.length > 0 &&
      (
        "product_id" in data.preview[0] ||
        "product_name" in data.preview[0]
      )
    );

    datasetStatus.hasMemberId = !!(
      data.preview &&
      Array.isArray(data.preview) &&
      data.preview.length > 0 &&
      "member_id" in data.preview[0]
    );

    // ===== 風險與不穩定性（吃 blacklist）=====
    datasetStatus.timeUnstable = false;
    datasetStatus.hasSpike = false;
    datasetStatus.amountInconsistent = false;
    datasetStatus.memberUnreliable = false;

    if (Array.isArray(data.blacklist)) {
      data.blacklist.forEach(item => {
        const reason = typeof item.reason === "string"
          ? item.reason.toLowerCase()
          : "";

        const metric = typeof item.metric === "string"
          ? item.metric.toLowerCase()
          : "";

        // 時間不穩定 / 尖峰
        if (reason.includes("time") || metric.includes("time")) {
          datasetStatus.timeUnstable = true;
        }
        if (reason.includes("spike") || reason.includes("波動")) {
          datasetStatus.hasSpike = true;
        }

        // 金額一致性
        if (reason.includes("amount") || metric.includes("amount") || reason.includes("金額")) {
          datasetStatus.amountInconsistent = true;
        }

        // 會員可信度
        if (reason.includes("member") || reason.includes("會員")) {
          datasetStatus.memberUnreliable = true;
        }
      });
    }

    // Debug（可在穩定後移除或改成 console.debug）
    console.debug("[datasetStatus]", datasetStatus);

    // 儲存最新的 analysis_id 供 Step B 使用
    latestAnalysisId = data.analysis_id || null;

    // ===== 顯示 Analysis ID 與 Overview 入口 =====
    const entrySection = document.getElementById("analysis-entry");
    const idValue = document.getElementById("analysis-id-value");
    const overviewLink = document.getElementById("go-overview-link");

    if (entrySection && idValue && overviewLink && latestAnalysisId) {
      idValue.textContent = latestAnalysisId;
      overviewLink.href = `/overview?analysis_id=${latestAnalysisId}`;
      entrySection.classList.remove("hidden");
    }

    // 清空結果區域
    result.textContent = "";

    // 建立一個容器用於所有內容
    const container = document.createElement("div");

    // ===== 資料總覽 =====
    // 根據 API 結構，overview 資料位於 data.overview，time_range 為物件 { min, max }
    const overviewSection = document.createElement("section");
    const overviewTitle = document.createElement("h2");
    overviewTitle.textContent = "資料總覽";
    overviewSection.appendChild(overviewTitle);

    const overviewList = document.createElement("ul");

    if (data.overview) {
      // row_count
      if ("row_count" in data.overview) {
        const li = document.createElement("li");
        li.textContent = `資料筆數: ${data.overview.row_count}`;
        overviewList.appendChild(li);
      }

      // time_column
      if ("time_column" in data.overview) {
        const li = document.createElement("li");
        li.textContent = `時間欄位: ${data.overview.time_column}`;
        overviewList.appendChild(li);
      }

      // time_range
      if ("time_range" in data.overview && data.overview.time_range && typeof data.overview.time_range === "object") {
        const tr = data.overview.time_range;
        if ("min" in tr && "max" in tr) {
          const li = document.createElement("li");
          li.textContent = `時間範圍: ${tr.min} ~ ${tr.max}`;
          overviewList.appendChild(li);
        }
      }
    }

    overviewSection.appendChild(overviewList);
    container.appendChild(overviewSection);

    // ===== 資料粒度 =====
    // grains 保持不變，讀取自 data.grains
    const grainsSection = document.createElement("section");
    const grainsTitle = document.createElement("h2");
    grainsTitle.textContent = "資料粒度";
    grainsSection.appendChild(grainsTitle);

    if ("grains" in data && Array.isArray(data.grains) && data.grains.length > 0) {
      const grainsList = document.createElement("ul");
      data.grains.forEach((grain) => {
        const li = document.createElement("li");
        li.textContent = grain;
        grainsList.appendChild(li);
      });
      grainsSection.appendChild(grainsList);
    } else {
      const noGrains = document.createElement("p");
      noGrains.textContent = "無資料粒度資訊";
      grainsSection.appendChild(noGrains);
    }
    container.appendChild(grainsSection);

    // ===== 分析風險提示 =====
    // blacklist 依據新 API，severity 用 "block" 和 "warning" ，顯示 reason，並顯示 grain 與 metric
    const riskSection = document.createElement("section");
    const riskTitle = document.createElement("h2");
    riskTitle.textContent = "分析風險提示";
    riskSection.appendChild(riskTitle);

    if ("blacklist" in data && Array.isArray(data.blacklist) && data.blacklist.length > 0) {
      const riskList = document.createElement("ul");
      data.blacklist.forEach((item) => {
        const li = document.createElement("li");
        let icon = "";
        if (item.severity === "block") {
          icon = "🚫";
        } else if (item.severity === "warning") {
          icon = "⚠️";
        } else {
          icon = "ℹ️";
        }
        // 顯示 reason，並加上 grain 與 metric 以增加清晰度
        const grainText = item.grain ? ` [粒度: ${item.grain}]` : "";
        const metricText = item.metric ? ` [指標: ${item.metric}]` : "";
        li.textContent = `${icon} ${item.reason || ""}${grainText}${metricText}`;
        riskList.appendChild(li);
      });
      riskSection.appendChild(riskList);
    } else {
      const noRisk = document.createElement("p");
      noRisk.textContent = "無風險提示";
      riskSection.appendChild(noRisk);
    }
    container.appendChild(riskSection);

    // ===== 資料預覽 =====
    // 不一定有 preview，若無則顯示提示訊息
    const previewSection = document.createElement("section");
    previewSection.className = "section";
    const previewTitle = document.createElement("h2");
    previewTitle.textContent = "資料預覽（前 100 筆）";
    previewSection.appendChild(previewTitle);

    const previewData = data.preview;
    if (!previewData || !Array.isArray(previewData) || previewData.length === 0) {
      // 新增提示訊息：此階段尚未提供資料預覽
      const noPreview = document.createElement("p");
      noPreview.textContent = "（此階段尚未提供資料預覽）";
      previewSection.appendChild(noPreview);
    } else {
      // 只取前 100 筆
      const previewRows = previewData.slice(0, 100);

      // 取得所有欄位名稱 (keys) - 以第一筆資料為基準
      const columns = Object.keys(previewRows[0] || {});

      // 建立表格元素
      const table = document.createElement("table");
      table.style.borderCollapse = "collapse";
      table.style.marginBottom = "8px";

      // 建立表頭
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

      // 建立表身
      const tbody = document.createElement("tbody");
      table.appendChild(tbody);

      // 分頁設定
      const rowsPerPage = 10;
      let currentPage = 1;
      const totalPages = Math.ceil(previewRows.length / rowsPerPage);

      // 更新表格內容函式
      function renderTablePage(page) {
        tbody.innerHTML = "";
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

      // 建立分頁控制按鈕
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

      // 按鈕事件
      prevBtn.addEventListener("click", () => {
        if (currentPage > 1) {
          currentPage--;
          renderTablePage(currentPage);
          pageInfo.textContent = `第 ${currentPage} 頁 / 共 ${totalPages} 頁`;
          nextBtn.disabled = false;
          if (currentPage === 1) {
            prevBtn.disabled = true;
          }
        }
      });

      nextBtn.addEventListener("click", () => {
        if (currentPage < totalPages) {
          currentPage++;
          renderTablePage(currentPage);
          pageInfo.textContent = `第 ${currentPage} 頁 / 共 ${totalPages} 頁`;
          prevBtn.disabled = false;
          if (currentPage === totalPages) {
            nextBtn.disabled = true;
          }
        }
      });

      paginationDiv.appendChild(prevBtn);
      paginationDiv.appendChild(pageInfo);
      paginationDiv.appendChild(nextBtn);

      // === 新增表格 scroll 容器 ===
      const tableWrapper = document.createElement("div");
      tableWrapper.className = "table-scroll";
      tableWrapper.style.maxHeight = "400px";
      tableWrapper.style.overflow = "auto";
      tableWrapper.appendChild(table);
      previewSection.appendChild(tableWrapper);
      previewSection.appendChild(paginationDiv);

      // 初始渲染第一頁
      renderTablePage(currentPage);
    }

    container.appendChild(previewSection);

    // 將整個容器加入結果區域
    result.appendChild(container);

    // ===== Step A: 為何在上傳後載入分析選項？ =====
    // 因為分析選項可能依據上傳的資料而異，故此處呼叫 loadCapabilities
    loadCapabilities();

  } catch (err) {
    result.textContent = "發生錯誤：\n" + err.message;
  }
});

/**
 * 渲染 granularity（時間粒度）切換 UI
 * - 僅支援 day / month
 * - 使用按鈕避免自由輸入造成錯誤
 * - 切換後自動重跑當前分析（安全，因為 mapping 固定）
 */
function renderGranularityControls(container, current, onChange) {
  const wrapper = document.createElement("div");
  wrapper.style.display = "flex";
  wrapper.style.gap = "8px";
  wrapper.style.marginBottom = "12px";

  const options = [
    { key: "day", label: "日" },
    { key: "month", label: "月" }
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
      if (isAnalyzing || opt.key === currentGranularity) return;
      onChange(opt.key);
    });

    wrapper.appendChild(btn);
  });

  return wrapper;
}

// 哪些分析支援 granularity
const GRANULARITY_SUPPORTED = new Set(["time_trend", "aov"]);

/**
 * 實際執行分析（API 呼叫 + 圖表 render）
 * 與 click handler 分離，避免 granularity 切換被 isAnalyzing 擋住
 */
async function dispatchAnalysis(card) {
  const analysisKey = card.getAttribute("data-key");
  if (!analysisKey) return;

  currentAnalysisKey = analysisKey;
  currentGranularity = currentGranularity || "day";

  if (!latestAnalysisId) {
    alert("尚未有有效的分析 ID，請先上傳資料。");
    return;
  }

  const mapping = ANALYSIS_MAP[analysisKey];
  if (!mapping) return;

  const panel = document.getElementById("analysis-chart-panel");
  const chartContent = document.getElementById("analysis-chart-content");

  chartContent.innerHTML = "";
  const chartSection = document.createElement("section");
  chartSection.id = "chart-section";

  // 設定目前圖表 container 供匯出 PNG 用
  currentChartContainer = chartSection;

  // granularity UI
  if (GRANULARITY_SUPPORTED.has(analysisKey)) {
    const granularityUI = renderGranularityControls(
      chartSection,
      currentGranularity,
      (next) => {
        currentGranularity = next;
        runAnalysisByKey(currentAnalysisKey);
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
  // ==== 新增 chart-area ====
  // 專屬圖表繪製區，renderer 只會清這一塊，避免誤刪 header / 按鈕
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
      payload = { analysis_id: latestAnalysisId, granularity: currentGranularity };
    } else if (analysisKey === "top_products" || analysisKey === "top_members") {
      payload = { analysis_id: latestAnalysisId, limit: 10 };
    } else if (analysisKey === "new_vs_returning") {
      payload = { analysis_id: latestAnalysisId };
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

      // KPI 1：總量 / 平均（依分析不同）
      const kpi1 = document.createElement("div");
      kpi1.className = "kpi-card";
      kpi1.style.padding = "12px";
      kpi1.style.border = "1px solid #ddd";
      kpi1.style.borderRadius = "8px";
      kpi1.style.minWidth = "140px";

      const kpi1Title = document.createElement("div");
      kpi1Title.style.fontSize = "13px";
      kpi1Title.style.color = "#666";
      kpi1Title.textContent = analysisKey === "aov" ? "平均 AOV" : "總金額";

      const kpi1Value = document.createElement("div");
      kpi1Value.style.fontSize = "20px";
      kpi1Value.style.fontWeight = "bold";
      kpi1Value.textContent =
        analysisKey === "aov"
          ? avg.toFixed(2)
          : Math.round(total).toLocaleString();

      kpi1.appendChild(kpi1Title);
      kpi1.appendChild(kpi1Value);

      // KPI 2：最大值
      const kpi2 = document.createElement("div");
      kpi2.className = "kpi-card";
      kpi2.style.padding = "12px";
      kpi2.style.border = "1px solid #ddd";
      kpi2.style.borderRadius = "8px";
      kpi2.style.minWidth = "140px";

      const kpi2Title = document.createElement("div");
      kpi2Title.style.fontSize = "13px";
      kpi2Title.style.color = "#666";
      kpi2Title.textContent = "最大值";

      const kpi2Value = document.createElement("div");
      kpi2Value.style.fontSize = "20px";
      kpi2Value.style.fontWeight = "bold";
      kpi2Value.textContent = Math.round(max).toLocaleString();

      kpi2.appendChild(kpi2Title);
      kpi2.appendChild(kpi2Value);

      // 插入 KPI 區塊（在 chart-area 之前）
      chartSection.insertBefore(kpiWrapper, chartSection.querySelector(".chart-area"));
      kpiWrapper.appendChild(kpi1);
      kpiWrapper.appendChild(kpi2);
    }

    // ===== Plotly 優先：後端有 chart spec 就用 Plotly =====
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
  } catch (err) {
    setAnalyzingState(false, "");
    const errP = document.createElement("p");
    errP.style.color = "red";
    errP.textContent = "取得分析資料失敗：" + err.message;
    chartSection.appendChild(errP);
  }
}

/**
 * 依分析 key 直接執行分析（不走 click event）
 * 用於 granularity（日/月）切換
 */
function runAnalysisByKey(analysisKey) {
  if (!analysisKey) return;
  const card = document.querySelector(
    `.analysis-option-card[data-key="${analysisKey}"]`
  );
  if (!card) return;
  dispatchAnalysis(card);
}

/**
 * 匯出目前顯示中的圖表為 PNG（使用 Chart.js 原生 toBase64Image）
 * - 不重新跑 API
 * - 直接輸出目前畫面上的圖表
 */
function exportCurrentChartAsPNG() {
  const key = currentAnalysisKey || "chart";
  const gran = currentGranularity || "day";
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `${key}_${gran}_${ts}.png`;

  // Plotly 圖表匯出
  if (currentChartContainer && currentChartContainer._plotlyDiv) {
    Plotly.downloadImage(currentChartContainer._plotlyDiv, {
      format: "png",
      filename: filename.replace(".png", ""),
      height: 600,
      width: 1000,
      scale: 2,
    });
    return;
  }

  // Chart.js fallback
  if (currentChartContainer && currentChartContainer._chart) {
    const chart = currentChartContainer._chart;
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

// ===== Step B: 分析選項點擊事件統一派發與狀態管理 =====
// 為什麼分析選項需固定對應圖表？（見下方繁體中文說明）
// - 每個分析選項（capability）對應特定 API 與資料結構，固定對應圖表型態可避免前端複雜度與誤用。
// - 不允許自由選擇圖表型態，確保 UI 簡潔且資料正確對應。
// - 鎖定（lock/loading）狀態能防止重複點擊、競態與多重請求造成的 UI 混亂。

let isAnalyzing = false; // 全域分析中狀態

/**
 * 設定分析進行中狀態，鎖定 UI 並顯示狀態訊息
 * @param {boolean} isBusy 是否鎖定
 * @param {string} message 狀態訊息
 */
function setAnalyzingState(isBusy, message) {
  isAnalyzing = isBusy;
  const optionsContainer = document.getElementById("analysis-options");
  // 鎖定所有分析選項卡
  Array.from(optionsContainer.querySelectorAll(".analysis-option-card")).forEach(card => {
    card.style.pointerEvents = isBusy ? "none" : "";
    card.style.opacity = isBusy ? "0.6" : "";
  });
  // 顯示狀態訊息
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

// 分析項目統一映射表（分析選項 key → API 與圖表型態）
// 固定映射，避免自由選擇造成資料與圖表不符
// 為什麼 AOV 用折線圖？AOV（客單價）隨時間變化，適合用 line chart 呈現趨勢。
// 為什麼新客與回購客用圓餅圖？新客/回購客占比為比例型資料，適合 pie chart 呈現分布。
// 為什麼這裡要固定 mapping？確保每個分析選項的資料結構與圖表型態一一對應，避免誤用。
// 為什麼 top_members 也用 bar chart？→ 高貢獻會員排行與熱門產品排行資料結構類似，皆為排行型資料，適合用 bar chart 呈現。
// 之前「高貢獻會員排行」點擊無反應，是因為這裡缺少 mapping 導致前端無法正確取得 API 與圖表型態。
const ANALYSIS_MAP = {
  // 固定對應：不允許自由圖表選擇
  time_trend: {
    api: "/analysis/time-trend",
    chart: "line"
  },
  top_products: {
    api: "/analysis/top-products",
    chart: "bar"
  },
  top_members: {
    api: "/analysis/top-members",
    chart: "bar"
  },
  // AOV 客單價：用折線圖（line chart）顯示每日變化
  aov: {
    api: "/analysis/aov",
    chart: "line"
  },
  // 新客與回購客占比：用圓餅圖（pie chart）顯示比例
  new_vs_returning: {
    api: "/analysis/new-vs-returning",
    chart: "pie"
  }
};

document.getElementById("analysis-options").addEventListener("click", async (e) => {
  // 找出被點擊的分析選項卡
  let card = e.target;
  while (card && !card.classList.contains("analysis-option-card")) {
    card = card.parentElement;
  }
  if (!card) return;

  // ====== 分析選項 active 狀態在 JS 處理 ======
  // 因為需要根據點擊行為即時切換 active 樣式，並確保同時只有一個選項 active
  // 若為 disabled 或分析進行中，不允許切換 active 狀態（避免誤觸與競態）
  // ====== 為什麼鎖定狀態要阻擋 active 切換？ ======
  // 分析進行中時，避免用戶切換選項造成多重請求與 UI 混亂
  if (card.classList.contains("disabled") || isAnalyzing) {
    return;
  }

  // 立即切換 active 狀態
  const allCards = card.parentElement.querySelectorAll(".analysis-option-card");
  allCards.forEach(c => c.classList.remove("active"));
  card.classList.add("active");

  // 記住目前分析 key，並重置 granularity
  const analysisKey = card.getAttribute("data-key");
  currentAnalysisKey = analysisKey;
  currentGranularity = "day";

  // active 狀態切換後
  dispatchAnalysis(card);
});

// ===== 分析圖表面板收合/展開功能 =====
// 為什麼面板使用 toggle 而不是重建？→ 保持動畫與狀態，避免不必要的 DOM 操作
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

// ===== Plotly 通用渲染函式 =====
// 接收後端回傳的 chart spec（{ data, layout }），用 Plotly.newPlot 渲染
// 安全性：chartSpec 來自自建後端 API，非使用者輸入，不含 HTML
function renderPlotlyChart(container, chartSpec) {
  const chartArea = container.querySelector(".chart-area");
  if (!chartArea) return;

  // 清空子元素（安全方式，不使用 innerHTML）
  while (chartArea.firstChild) {
    chartArea.removeChild(chartArea.firstChild);
  }

  // 先清掉舊的 Chart.js 實例（如果有）
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
      filename: `${currentAnalysisKey || "chart"}_${currentGranularity || "day"}_${new Date().toISOString().slice(0, 10)}`,
      height: 600,
      width: 1000,
      scale: 2,
    },
    displaylogo: false,
  };

  Plotly.newPlot(plotDiv, chartSpec.data, chartSpec.layout, config);

  // 標記為 Plotly 圖表（PNG 匯出用）
  container._plotlyDiv = plotDiv;
  container._chart = null;
}

// 用 Chart.js 繪製時間趨勢/客單價折線圖（fallback）
// data 格式: [{ time: string, value: number }, ...]
function renderTimeTrendChart(container, data) {
  // 只清空 .chart-area
  const chartArea = container.querySelector(".chart-area");
  if (!chartArea) return;
  chartArea.innerHTML = "";

  // 若資料為空，顯示友善訊息
  if (!Array.isArray(data) || data.length === 0) {
    const p = document.createElement("p");
    p.textContent = "無時間趨勢資料。";
    chartArea.appendChild(p);
    // 若前一個 Chart.js 實例存在，也要清掉
    if (container._chart) {
      container._chart.destroy();
      container._chart = null;
    }
    return;
  }

  // Chart.js: 若前一個 chart 實例存在，必須先 destroy 釋放資源，避免記憶體洩漏
  // 為什麼要 destroy？→ Chart.js 會佔用 canvas 與事件，重複建立會造成多重繪圖與效能問題
  if (container._chart) {
    container._chart.destroy();
    container._chart = null;
  }

  // 建立 canvas（不要設定 width/height，讓父容器 CSS 控制尺寸）
  const canvas = document.createElement("canvas");
  chartArea.appendChild(canvas);

  // 取得資料
  const labels = data.map(d => d.time);
  const values = data.map(d => d.value);

  // Chart.js 配置
  const ctx = canvas.getContext("2d");
  const chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "", // 不顯示圖例
        data: values,
        borderColor: "#0074d9",
        backgroundColor: "rgba(0,116,217,0.08)",
        fill: false,
        tension: 0.3, // 線條平滑
        pointRadius: 3,
        pointHoverRadius: 5,
      }]
    },
    options: {
      // --- 圖表響應式尺寸設定 ---
      // 當外層容器（如 .analysis-chart-panel）控制高度時，必須設 maintainAspectRatio: false
      // 否則 Chart.js 會自動維持寬高比，導致圖表高度無法隨容器變化
      // canvas.width/canvas.height 不能手動指定，否則會覆蓋 CSS 響應式
      // （如需更改圖表大小，請用父容器 CSS 控制）
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: "#333",
            autoSkip: true,
            maxTicksLimit: 10,
          },
        },
        y: {
          grid: {
            display: true,
            color: "#eee"
          },
          beginAtZero: false,
          ticks: {
            color: "#333"
          }
        }
      }
    }
  });
  // 將 Chart.js 實例存放在 container 上，方便下次 destroy
  container._chart = chart;
}

// 用 Chart.js 繪製熱門產品長條圖
// 為什麼用 Chart.js？→ 提供互動性、響應式與美觀，維護方便，避免自行處理繪圖與座標。
// 假設 data 格式為：[{ product: "產品名稱", sales: number }, ...]
function renderTopProductsChart(container, data) {
  // 只清空 .chart-area
  const chartArea = container.querySelector(".chart-area");
  if (!chartArea) return;
  chartArea.innerHTML = "";

  // 若資料為空，顯示友善訊息
  if (!Array.isArray(data) || data.length === 0) {
    const p = document.createElement("p");
    p.textContent = "無熱門產品資料。";
    chartArea.appendChild(p);
    // 若前一個 Chart.js 實例存在，也要清掉
    if (container._chart) {
      container._chart.destroy();
      container._chart = null;
    }
    return;
  }

  // Chart.js: 若前一個 chart 實例存在，必須先 destroy 釋放資源，避免記憶體洩漏
  // 為什麼要 destroy？→ Chart.js 會佔用 canvas 與事件，重複建立會造成多重繪圖與效能問題
  if (container._chart) {
    container._chart.destroy();
    container._chart = null;
  }

  // 建立 canvas（不要設定 width/height，讓父容器 CSS 控制尺寸）
  const canvas = document.createElement("canvas");
  chartArea.appendChild(canvas);

  // 取得資料
  const labels = data.map(d => d.product);
  const values = data.map(d => d.sales);

  // Chart.js 配置
  const ctx = canvas.getContext("2d");
  const chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "", // 不顯示圖例
        data: values,
        backgroundColor: "#0074d9"
      }]
    },
    options: {
      // --- 圖表響應式尺寸設定 ---
      // 當外層容器（如 .analysis-chart-panel）控制高度時，必須設 maintainAspectRatio: false
      // 否則 Chart.js 會自動維持寬高比，導致圖表高度無法隨容器變化
      // canvas.width/canvas.height 不能手動指定，否則會覆蓋 CSS 響應式
      // （如需更改圖表大小，請用父容器 CSS 控制）
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: "#333",
            autoSkip: false,
            font: { size: 13 }
          }
        },
        y: {
          grid: {
            display: true,
            color: "#eee"
          },
          beginAtZero: true,
          ticks: {
            color: "#333"
          }
        }
      }
    }
  });
  // 將 Chart.js 實例存放在 container 上，方便下次 destroy
  container._chart = chart;
}
// 用 Chart.js 繪製新客與回購客占比圓餅圖
// items 格式：[{ key: "新客"|"回購客", value: 數值 }, ...]
// 為什麼用圓餅圖？→ 比例型資料（如新客/回購客占比）用 pie chart 可直觀顯示各部分比例。
function renderNewVsReturningPie(container, items) {
  // 只清空 .chart-area
  const chartArea = container.querySelector(".chart-area");
  if (!chartArea) return;
  chartArea.innerHTML = "";
  // 資料檢查：空或全為零，不顯示圖表
  if (!Array.isArray(items) || items.length === 0 || items.every(x => !x.value || x.value === 0)) {
    const p = document.createElement("p");
    p.textContent = "無新客與回購客占比資料。";
    chartArea.appendChild(p);
    // 若前一個 Chart.js 實例存在，也要清掉
    if (container._chart) {
      container._chart.destroy();
      container._chart = null;
    }
    return;
  }
  // Chart.js: 若前一個 chart 實例存在，必須先 destroy 釋放資源，避免記憶體洩漏
  // 為什麼要 destroy？→ Chart.js 會佔用 canvas 與事件，重複建立會造成多重繪圖與效能問題
  if (container._chart) {
    container._chart.destroy();
    container._chart = null;
  }
  // 取前兩項，保證只有新客/回購客
  const safeItems = items.slice(0, 2).map((x, i) => ({
    key: x.key || (i === 0 ? "新客" : "回購客"),
    value: typeof x.value === "number" ? x.value : parseFloat(x.value) || 0
  }));
  const total = safeItems.reduce((a, b) => a + (b.value || 0), 0);
  if (!total) {
    const p = document.createElement("p");
    p.textContent = "無新客與回購客占比資料。";
    chartArea.appendChild(p);
    return;
  }
  // 建立 canvas（不要設定 width/height，讓父容器 CSS 控制尺寸）
  const canvas = document.createElement("canvas");
  chartArea.appendChild(canvas);
  // 顏色（與長條圖相同 palette）
  const colors = ["#0074d9", "#FF851B"];
  // 取得資料
  const labels = safeItems.map(item => item.key);
  const values = safeItems.map(item => item.value);
  // Chart.js 配置
  const ctx = canvas.getContext("2d");
  const chart = new Chart(ctx, {
    type: "pie",
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
      }]
    },
    options: {
      // --- 圖表響應式尺寸設定 ---
      // 當外層容器（如 .analysis-chart-panel）控制高度時，必須設 maintainAspectRatio: false
      // 否則 Chart.js 會自動維持寬高比，導致圖表高度無法隨容器變化
      // canvas.width/canvas.height 不能手動指定，否則會覆蓋 CSS 響應式
      // （如需更改圖表大小，請用父容器 CSS 控制）
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: "right",
          labels: {
            color: "#333",
            font: { size: 15 }
          }
        }
      }
    }
  });
  // 將 Chart.js 實例存放在 container 上，方便下次 destroy
  container._chart = chart;
}
/**
 * 根據資料狀態，判斷分析卡片的可用性
 * 回傳值：
 *  - "ok"        : 可直接使用
 *  - "caution"   : 可使用，但需留意
 *  - "disabled"  : 不建議或不可使用
 */
function evaluateAnalysisStatus(analysisKey, status) {
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