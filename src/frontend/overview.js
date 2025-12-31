/* =========================================================
 * overview.js
 * Dataset Overview – Analyst-first implementation (v0.1)
 *
 * Responsibilities:
 * 1. Read analysis_id from URL
 * 2. Fetch /analysis/overview
 * 3. Render big-number facts (no charts here)
 * 4. Render ONE preview chart: daily order count
 * ========================================================= */

(function () {
  // ---------- spike detection (robust, overview-only) ----------
  function detectSpikes(values) {
    if (!Array.isArray(values) || values.length < 8) {
      return { high: [], low: [] };
    }

    const sorted = [...values].sort((a, b) => a - b);
    const q1 = sorted[Math.floor(sorted.length * 0.25)];
    const q3 = sorted[Math.floor(sorted.length * 0.75)];
    const iqr = q3 - q1;

    const highThreshold = q3 + 2 * iqr;
    const lowThreshold = Math.max(0, q1 - 2 * iqr);

    return {
      high: values.map(v => v > highThreshold),
      low: values.map(v => v < lowThreshold),
    };
  }
  // ---------- chart helper ----------
  function renderDailyOrdersChart(canvasId, series) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !Array.isArray(series) || series.length === 0) return;

    const ctx = canvas.getContext("2d");

    // 清掉舊圖（避免重複 render）
    if (canvas._chart) {
      canvas._chart.destroy();
      canvas._chart = null;
    }

    const labels = series.map(p => p.date);
    const values = series.map(p => p.value);

    const spikes = detectSpikes(values);

    const pointColors = values.map((_, i) =>
      spikes.high[i]
        ? "rgba(220, 38, 38, 0.9)"     // 高於常態：紅
        : spikes.low[i]
          ? "rgba(234, 179, 8, 0.9)"  // 低於常態：黃
          : "rgba(37, 99, 235, 0.9)"  // 常態：藍
    );

    const pointRadii = values.map((_, i) =>
      spikes.high[i] || spikes.low[i] ? 4 : 0
    );

    canvas._chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: "#2563eb",
          backgroundColor: "rgba(37, 99, 235, 0.1)",
          borderWidth: 2,
          tension: 0.25,
          pointRadius: pointRadii,
          pointBackgroundColor: pointColors,
          pointHoverRadius: pointRadii.map(r => r + 2),
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(ctx) {
                const v = ctx.parsed.y;
                const i = ctx.dataIndex;

                if (spikes.high[i]) {
                  return `訂單數 ${v}（高於常態區間）`;
                }
                if (spikes.low[i]) {
                  return `訂單數 ${v}（低於常態區間）`;
                }
                return `訂單數 ${v}`;
              }
            }
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { maxTicksLimit: 8 }
          },
          y: {
            grid: { color: "#f1f5f9" },
            ticks: { precision: 0 }
          }
        }
      }
    });
  }
  // ---------- utils ----------
  function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
  }

  function formatDateRange(start, end) {
    if (!start || !end) return "—";
    return `${start.slice(0, 10)} ～ ${end.slice(0, 10)}`;
  }

  function daysFromNow(dateStr) {
    if (!dateStr) return "—";
    const d = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - d) / (1000 * 60 * 60 * 24));
    return diff < 0 ? "—" : `${diff} 天前`;
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function safeRatio(numerator, denominator, digits = 2) {
    if (
      numerator === null || numerator === undefined ||
      denominator === null || denominator === undefined ||
      denominator === 0
    ) {
      return null;
    }
    const v = numerator / denominator;
    return Number.isFinite(v) ? v.toFixed(digits) : null;
  }

  // ---------- main ----------
  const analysisId = getQueryParam("analysis_id");

  if (!analysisId) {
    setText("dataset-date-range", "請先上傳資料");
    return;
  }

  // ---------- fetch overview ----------
  fetch("/analysis/overview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_id: analysisId }),
  })
    .then((r) => r.json())
    .then((data) => {
      const ov = data.overview;
      if (!ov) return;

      // ===== Dataset Health =====
      const dateCols = ov.date_range || {};
      const dateColNames = Object.keys(dateCols);

      if (dateColNames.length > 0) {
        const mainCol = dateColNames[0];
        const range = dateCols[mainCol];

        setText(
          "dataset-date-range",
          formatDateRange(range.start, range.end)
        );
        setText(
          "dataset-recent-date",
          daysFromNow(range.end)
        );
        setText(
          "dataset-main-time-col",
          mainCol
        );
      }

      // ===== Dataset Scale =====
      // order_count / order_item_count / member_count / product_count
      setText(
        "metric-order-count",
        ov.order_count !== null && ov.order_count !== undefined
          ? ov.order_count.toLocaleString()
          : "—"
      );

      setText(
        "metric-item-count",
        ov.order_item_count !== null && ov.order_item_count !== undefined
          ? ov.order_item_count.toLocaleString()
          : "—"
      );

      setText(
        "metric-member-count",
        ov.member_count !== null && ov.member_count !== undefined
          ? ov.member_count.toLocaleString()
          : "—"
      );

      setText(
        "metric-product-count",
        ov.product_count !== null && ov.product_count !== undefined
          ? ov.product_count.toLocaleString()
          : "—"
      );

      // ===== Derived Ratios (micro insights) =====
      const ratios = {
        ordersPerMember: safeRatio(ov.order_count, ov.member_count, 2),
        itemsPerOrder: safeRatio(ov.order_item_count, ov.order_count, 2),
        memberPenetration: safeRatio(ov.member_count, ov.order_count, 2),
      };

      console.log("[Overview Ratios]", ratios);

      // ===== Render micro metrics (UI, low emphasis) =====
      if (ratios.ordersPerMember !== null) {
        setText("micro-orders-per-member", ratios.ordersPerMember);
      }

      if (ratios.itemsPerOrder !== null) {
        setText("micro-items-per-order", ratios.itemsPerOrder);
      }

      // ===== Data Quality (textual diagnosis only) =====
      const qualityList = document.getElementById("data-quality-list");
      if (qualityList) {
        qualityList.innerHTML = "";

        const missing = ov.missing_value_top_columns || {};
        const entries = Object.entries(missing);

        if (entries.length === 0) {
          qualityList.innerHTML = "<li>未發現明顯資料品質風險</li>";
        } else {
          entries.forEach(([col, ratio]) => {
            const li = document.createElement("li");
            li.textContent = `${col} 缺失率約 ${(ratio * 100).toFixed(1)}%`;
            qualityList.appendChild(li);
          });
        }
      }
      // ===== Daily Orders Trend (Preview) =====
      fetch("/analysis/overview/daily-orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis_id: analysisId }),
      })
        .then(r => r.json())
        .then(trend => {
          if (Array.isArray(trend.series)) {
            renderDailyOrdersChart("chart-daily-orders", trend.series);
          }
        })
        .catch(() => {
          // Preview chart failure should not block Overview
        });
    })
    .catch((err) => {
      console.error("Overview load failed:", err);
    });

})(); 
