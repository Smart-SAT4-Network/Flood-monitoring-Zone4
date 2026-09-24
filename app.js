(function () {
  "use strict";

  const cacheBust = () => "?t=" + Date.now();

  async function fetchJson(path) {
    const res = await fetch(path + cacheBust());
    if (!res.ok) throw new Error("โหลด " + path + " ไม่สำเร็จ (" + res.status + ")");
    return res.json();
  }

  function formatDateLabel(isoDate) {
    // 2025-09-24 -> 24/9
    const [y, m, d] = isoDate.split("-");
    return `${parseInt(d, 10)}/${parseInt(m, 10)}`;
  }

  function buildLegendHtml(basin) {
    const seriesItems = basin.series
      .map(
        (s) =>
          `<span class="legend-item"><span class="legend-swatch" style="background:${s.color}"></span>${s.name}</span>`
      )
      .join("");
    const thresholdItems = basin.thresholds
      .map(
        (t) =>
          `<span class="legend-item" style="color:${t.color}"><span class="legend-swatch dashed"></span>${t.label} ${t.value.toLocaleString()} ${basin.unit}</span>`
      )
      .join("");
    return seriesItems + thresholdItems;
  }

  function buildChartDatasets(basin, historyRows) {
    const labels = historyRows.map((r) => formatDateLabel(r.date));
    const datasets = [];

    basin.series.forEach((s) => {
      datasets.push({
        label: s.name,
        data: historyRows.map((r) => (r.values ? r.values[s.id] : null)),
        borderColor: s.color,
        backgroundColor: s.color,
        pointRadius: 3,
        pointBackgroundColor: "#fff",
        pointBorderColor: s.color,
        pointBorderWidth: 2,
        borderWidth: 2,
        spanGaps: true,
        tension: 0.15,
      });
    });

    basin.thresholds.forEach((t) => {
      datasets.push({
        label: t.label + " " + t.value,
        data: labels.map(() => t.value),
        borderColor: t.color,
        borderDash: t.dash || [4, 4],
        borderWidth: 1.5,
        pointRadius: 0,
        fill: false,
        tension: 0,
      });
    });

    return { labels, datasets };
  }

  function renderChart(canvas, basin, historyRows) {
    const { labels, datasets } = buildChartDatasets(basin, historyRows);
    return new Chart(canvas.getContext("2d"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${ctx.formattedValue} ${basin.unit}`,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            title: { display: false },
            grid: { color: "#efe9c0" },
          },
          x: {
            grid: { display: false },
            ticks: { maxRotation: 90, minRotation: 45, autoSkip: true, maxTicksLimit: 16 },
          },
        },
      },
    });
  }

  function hasAnyData(basin, historyRows) {
    return historyRows.some(
      (r) => r.values && basin.series.some((s) => r.values[s.id] !== null && r.values[s.id] !== undefined)
    );
  }

  function renderBasinCard(container, basin, historyRows) {
    const card = document.createElement("article");
    card.className = "basin-card";

    const badge = document.createElement("div");
    badge.className = "basin-card__badge";
    badge.textContent = basin.title;
    card.appendChild(badge);

    const unitLine = document.createElement("div");
    unitLine.className = "basin-card__unit";
    unitLine.textContent = `ปริมาณน้ำ (${basin.unit})`;
    card.appendChild(unitLine);

    const chartWrap = document.createElement("div");
    chartWrap.className = "basin-card__chart-wrap";
    const chartBox = document.createElement("div");
    chartBox.className = "chart-canvas-box";
    const canvas = document.createElement("canvas");
    chartBox.appendChild(canvas);
    chartWrap.appendChild(chartBox);
    card.appendChild(chartWrap);

    const legend = document.createElement("div");
    legend.className = "basin-card__legend";
    legend.innerHTML = buildLegendHtml(basin);
    card.appendChild(legend);

    if (!hasAnyData(basin, historyRows)) {
      const status = document.createElement("div");
      status.className = "basin-card__status no-data";
      status.textContent =
        "ยังไม่มีข้อมูลจริงจากสถานีนี้ในไฟล์ data/history.json — รอรอบอัปเดตอัตโนมัติถัดไป หรือรัน scripts/fetch_data.py แล้ว push ขึ้น GitHub อีกครั้ง";
      card.appendChild(status);
    }

    container.appendChild(card);
    renderChart(canvas, basin, historyRows);
  }

  function renderStorageTable(container, storageRows) {
    if (!storageRows || storageRows.length === 0) {
      container.innerHTML = "<p>ยังไม่มีข้อมูล — รอรอบอัปเดตอัตโนมัติถัดไป</p>";
      return;
    }
    const latest = storageRows[storageRows.length - 1];
    const dams = (latest.dams || [])
      .filter((d) => d.name)
      .sort((a, b) => (b.percent_storage || 0) - (a.percent_storage || 0));

    if (dams.length === 0) {
      container.innerHTML = "<p>ยังไม่มีข้อมูล — รอรอบอัปเดตอัตโนมัติถัดไป</p>";
      return;
    }

    const rows = dams
      .map((d) => {
        const pct = d.percent_storage != null ? d.percent_storage : 0;
        const highClass = pct >= 80 ? "high" : "";
        return `<tr>
          <td>${d.name}</td>
          <td>${d.percent_storage != null ? d.percent_storage.toFixed(1) + "%" : "-"}</td>
          <td><div class="pct-bar-wrap"><div class="pct-bar ${highClass}" style="width:${Math.min(pct, 100)}%"></div></div></td>
          <td>${d.inflow != null ? d.inflow.toFixed(2) : "-"}</td>
          <td>${d.outflow != null ? d.outflow.toFixed(2) : "-"}</td>
        </tr>`;
      })
      .join("");

    container.innerHTML = `
      <table class="storage-table">
        <thead>
          <tr>
            <th>ชื่อเขื่อน/อ่างเก็บน้ำ</th>
            <th>% เก็บกัก</th>
            <th></th>
            <th>Inflow (ล้าน ลบ.ม.)</th>
            <th>Outflow (ล้าน ลบ.ม.)</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  async function loadAndRender() {
    const lastUpdatedEl = document.getElementById("last-updated");
    const basinsContainer = document.getElementById("basins-container");
    const storageContainer = document.getElementById("storage-table-wrap");

    basinsContainer.innerHTML = "";
    lastUpdatedEl.textContent = "กำลังโหลดข้อมูล...";

    try {
      const [stationsConfig, history, storageHistory] = await Promise.all([
        fetchJson(window.APP_PATHS.stationsConfig),
        fetchJson(window.APP_PATHS.history).catch(() => []),
        fetchJson(window.APP_PATHS.storageHistory).catch(() => []),
      ]);

      stationsConfig.basins.forEach((basin) => renderBasinCard(basinsContainer, basin, history));
      renderStorageTable(storageContainer, storageHistory);

      const latestDate =
        history.length > 0 ? history[history.length - 1].date : null;
      lastUpdatedEl.textContent = latestDate
        ? "ข้อมูลล่าสุด: " + latestDate
        : "ยังไม่มีข้อมูล (รอรอบอัปเดตอัตโนมัติแรก)";
    } catch (err) {
      console.error(err);
      lastUpdatedEl.textContent = "โหลดข้อมูลไม่สำเร็จ";
      basinsContainer.innerHTML =
        '<p style="color:#fff">เกิดข้อผิดพลาดในการโหลดข้อมูล: ' + err.message + "</p>";
    }
  }

  document.getElementById("refresh-btn").addEventListener("click", loadAndRender);
  document.addEventListener("DOMContentLoaded", loadAndRender);
})();
