/* Lightweight SVG charts: multi-line with crosshair tooltip, stacked bars,
   diverging bars. No external libraries - fully offline. */

const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const W = 720, H = 260, M = { top: 14, right: 74, bottom: 26, left: 40 };
  const IW = W - M.left - M.right, IH = H - M.top - M.bottom;

  const cssVar = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function el(tag, attrs = {}) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  }

  function niceTicks(min, max, count = 4) {
    if (min === max) { min -= 1; max += 1; }
    const span = max - min;
    const step = Math.pow(10, Math.floor(Math.log10(span / count)));
    const err = span / count / step;
    const mult = err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
    const s = mult * step;
    const ticks = [];
    for (let v = Math.ceil(min / s) * s; v <= max + 1e-9; v += s) ticks.push(+v.toFixed(6));
    return ticks;
  }

  function fmtDate(iso) {
    const [y, m, d] = iso.split("-");
    return `${d}/${m}`;
  }

  const tooltip = () => document.getElementById("tooltip");

  function showTooltip(html, x, y) {
    const t = tooltip();
    t.innerHTML = html;
    t.classList.remove("hidden");
    const r = t.getBoundingClientRect();
    let left = x + 14, top = y + 12;
    if (left + r.width > window.innerWidth - 8) left = x - r.width - 14;
    if (top + r.height > window.innerHeight - 8) top = y - r.height - 12;
    t.style.left = left + "px";
    t.style.top = top + "px";
  }
  const hideTooltip = () => tooltip().classList.add("hidden");

  function frame(svg, yTicks, yFmt) {
    for (const v of yTicks.ticks) {
      const y = yTicks.scale(v);
      svg.appendChild(el("line", {
        x1: M.left, x2: M.left + IW, y1: y, y2: y,
        stroke: cssVar("--grid"), "stroke-width": 1,
      }));
      const label = el("text", {
        x: M.left - 7, y: y + 4, "text-anchor": "end",
        "font-size": 11, fill: cssVar("--muted"),
      });
      label.textContent = yFmt ? yFmt(v) : v;
      svg.appendChild(label);
    }
    svg.appendChild(el("line", {
      x1: M.left, x2: M.left + IW, y1: M.top + IH, y2: M.top + IH,
      stroke: cssVar("--baseline"), "stroke-width": 1,
    }));
  }

  function xLabels(svg, data, xOf) {
    const step = Math.max(1, Math.ceil(data.length / 8));
    const idx = [];
    for (let i = 0; i < data.length; i += step) idx.push(i);
    // keep the last date without colliding with the previous tick
    const last = data.length - 1;
    if (last - idx[idx.length - 1] < step * 0.6) idx[idx.length - 1] = last;
    else idx.push(last);
    for (const i of idx) {
      const label = el("text", {
        x: xOf(i), y: M.top + IH + 17, "text-anchor": "middle",
        "font-size": 10.5, fill: cssVar("--muted"),
      });
      label.textContent = fmtDate(data[i].date);
      svg.appendChild(label);
    }
  }

  function makeScales(data, values) {
    const nums = values.filter((v) => v != null && isFinite(v));
    let min = Math.min(...nums), max = Math.max(...nums);
    const pad = (max - min) * 0.12 || 1;
    min -= pad; max += pad;
    const ticks = niceTicks(min, max);
    min = Math.min(min, ticks[0]); max = Math.max(max, ticks[ticks.length - 1]);
    const scale = (v) => M.top + IH - ((v - min) / (max - min)) * IH;
    const xOf = data.length === 1
      ? () => M.left + IW / 2
      : (i) => M.left + (i / (data.length - 1)) * IW;
    return { min, max, ticks, scale, xOf };
  }

  function legend(container, series) {
    if (series.length < 2) return;
    const box = document.createElement("div");
    box.className = "legend";
    box.setAttribute("dir", "rtl");
    for (const s of series) {
      const item = document.createElement("span");
      item.className = "item";
      item.innerHTML = `<span class="swatch" style="background:${s.color}"></span>${s.label}`;
      box.appendChild(item);
    }
    container.appendChild(box);
  }

  /* ---------------- line chart (multi-series, optional band) -------------- */
  function line(container, { data, series, band, yFmt, valueFmt }) {
    container.innerHTML = "";
    if (!data.length) { container.innerHTML = '<p class="empty-note">אין נתונים</p>'; return; }
    const fmt = valueFmt || ((v) => Math.round(v * 10) / 10);
    const allVals = [];
    for (const row of data) {
      for (const s of series) if (row[s.key] != null) allVals.push(+row[s.key]);
      if (band) {
        if (row[band.lowKey] != null) allVals.push(+row[band.lowKey]);
        if (row[band.highKey] != null) allVals.push(+row[band.highKey]);
      }
    }
    if (!allVals.length) { container.innerHTML = '<p class="empty-note">אין נתונים</p>'; return; }

    const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
    const sc = makeScales(data, allVals);
    frame(svg, sc, yFmt);
    xLabels(svg, data, sc.xOf);

    if (band) {
      let up = "", down = "";
      data.forEach((row, i) => {
        const lo = row[band.lowKey], hi = row[band.highKey];
        if (lo == null || hi == null) return;
        up += `${up ? "L" : "M"}${sc.xOf(i)},${sc.scale(hi)} `;
        down = `L${sc.xOf(i)},${sc.scale(lo)} ` + down;
      });
      if (up) svg.appendChild(el("path", { d: up + down + "Z", fill: cssVar("--band") }));
    }

    const resolved = series.map((s) => ({ ...s, color: cssVar(s.colorVar) }));
    for (const s of resolved) {
      let d = "", pen = false;
      data.forEach((row, i) => {
        const v = row[s.key];
        if (v == null) { pen = false; return; }
        d += `${pen ? "L" : "M"}${sc.xOf(i).toFixed(1)},${sc.scale(+v).toFixed(1)} `;
        pen = true;
      });
      svg.appendChild(el("path", {
        d, fill: "none", stroke: s.color, "stroke-width": 2,
        "stroke-linejoin": "round", "stroke-linecap": "round",
      }));
      // direct label at line end
      for (let i = data.length - 1; i >= 0; i--) {
        if (data[i][s.key] != null) {
          const label = el("text", {
            x: M.left + IW + 6, y: sc.scale(+data[i][s.key]) + 4,
            "font-size": 11, "font-weight": 600, fill: s.color,
          });
          label.textContent = s.label;
          svg.appendChild(label);
          break;
        }
      }
    }

    // crosshair + tooltip
    const cursor = el("line", {
      y1: M.top, y2: M.top + IH, stroke: cssVar("--baseline"),
      "stroke-width": 1, "stroke-dasharray": "3,3", visibility: "hidden",
    });
    svg.appendChild(cursor);
    const overlay = el("rect", {
      x: M.left, y: M.top, width: IW, height: IH, fill: "transparent",
    });
    overlay.addEventListener("mousemove", (ev) => {
      const rect = svg.getBoundingClientRect();
      const px = ((ev.clientX - rect.left) / rect.width) * W;
      const i = Math.round(((px - M.left) / IW) * (data.length - 1));
      if (i < 0 || i >= data.length) return;
      const x = sc.xOf(i);
      cursor.setAttribute("x1", x); cursor.setAttribute("x2", x);
      cursor.setAttribute("visibility", "visible");
      const rows = resolved
        .filter((s) => data[i][s.key] != null)
        .map((s) => `<div class="t-row"><span class="swatch" style="width:8px;height:8px;border-radius:2px;background:${s.color}"></span>${s.label}: <b>${fmt(+data[i][s.key])}</b></div>`)
        .join("");
      showTooltip(`<div class="t-date">${data[i].date}</div>${rows}`, ev.clientX, ev.clientY);
    });
    overlay.addEventListener("mouseleave", () => {
      cursor.setAttribute("visibility", "hidden"); hideTooltip();
    });
    svg.appendChild(overlay);

    container.appendChild(svg);
    legend(container, resolved);
  }

  /* ---------------- stacked bars (sleep stages, hours) -------------------- */
  function stackedBar(container, { data, series, yFmt, valueFmt }) {
    container.innerHTML = "";
    if (!data.length) { container.innerHTML = '<p class="empty-note">אין נתונים</p>'; return; }
    const resolved = series.map((s) => ({ ...s, color: cssVar(s.colorVar) }));
    const totals = data.map((row) =>
      resolved.reduce((acc, s) => acc + (+row[s.key] || 0), 0));
    if (!totals.some((t) => t > 0)) { container.innerHTML = '<p class="empty-note">אין נתונים</p>'; return; }

    const max = Math.max(...totals) * 1.08;
    const ticks = niceTicks(0, max);
    const scale = (v) => M.top + IH - (v / max) * IH;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
    frame(svg, { ticks, scale }, yFmt);

    const n = data.length;
    const slot = IW / n;
    const bw = Math.max(3, Math.min(26, slot - 2));
    const xOf = (i) => M.left + slot * i + (slot - bw) / 2;
    xLabels(svg, data, (i) => xOf(i) + bw / 2);
    const fmt = valueFmt || ((v) => v);

    data.forEach((row, i) => {
      let acc = 0;
      const group = el("g");
      for (const s of resolved) {
        const v = +row[s.key] || 0;
        if (v <= 0) continue;
        const y1 = scale(acc + v), y2 = scale(acc);
        const isTop = acc + v >= totals[i] - 1e-9;
        const rect = el("rect", {
          x: xOf(i).toFixed(1), y: y1.toFixed(1),
          width: bw, height: Math.max(1, y2 - y1 - 1).toFixed(1), /* 1px surface gap */
          fill: s.color, rx: isTop ? 3 : 0,
        });
        group.appendChild(rect);
        acc += v;
      }
      group.addEventListener("mousemove", (ev) => {
        const rows = resolved
          .filter((s) => +row[s.key] > 0)
          .map((s) => `<div class="t-row"><span style="width:8px;height:8px;border-radius:2px;background:${s.color}"></span>${s.label}: <b>${fmt(+row[s.key])}</b></div>`)
          .join("");
        showTooltip(`<div class="t-date">${row.date}</div>${rows}`, ev.clientX, ev.clientY);
      });
      group.addEventListener("mouseleave", hideTooltip);
      svg.appendChild(group);
    });

    container.appendChild(svg);
    legend(container, resolved);
  }

  /* ------------- diverging bars (body battery charge/drain) --------------- */
  function divergingBar(container, { data, upKey, downKey, upLabel, downLabel }) {
    container.innerHTML = "";
    if (!data.length) { container.innerHTML = '<p class="empty-note">אין נתונים</p>'; return; }
    const upColor = cssVar("--series-1"), downColor = cssVar("--series-red");
    const ups = data.map((r) => +r[upKey] || 0);
    const downs = data.map((r) => +r[downKey] || 0);
    if (!ups.some(Boolean) && !downs.some(Boolean)) {
      container.innerHTML = '<p class="empty-note">אין נתונים</p>'; return;
    }
    const maxAbs = Math.max(...ups, ...downs) * 1.1 || 1;
    const scale = (v) => M.top + IH / 2 - (v / maxAbs) * (IH / 2);
    const ticks = niceTicks(-maxAbs, maxAbs, 4);
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
    frame(svg, { ticks, scale }, (v) => Math.abs(v));
    // zero baseline
    svg.appendChild(el("line", {
      x1: M.left, x2: M.left + IW, y1: scale(0), y2: scale(0),
      stroke: cssVar("--baseline"), "stroke-width": 1.5,
    }));

    const n = data.length;
    const slot = IW / n;
    const bw = Math.max(3, Math.min(22, slot - 2));
    const xOf = (i) => M.left + slot * i + (slot - bw) / 2;
    xLabels(svg, data, (i) => xOf(i) + bw / 2);

    data.forEach((row, i) => {
      const group = el("g");
      const up = +row[upKey] || 0, down = +row[downKey] || 0;
      if (up > 0) group.appendChild(el("rect", {
        x: xOf(i).toFixed(1), y: scale(up).toFixed(1),
        width: bw, height: (scale(0) - scale(up)).toFixed(1),
        fill: upColor, rx: 3,
      }));
      if (down > 0) group.appendChild(el("rect", {
        x: xOf(i).toFixed(1), y: (scale(0) + 1).toFixed(1),
        width: bw, height: (scale(0) - scale(down)).toFixed(1),
        fill: downColor, rx: 3,
      }));
      group.addEventListener("mousemove", (ev) => showTooltip(
        `<div class="t-date">${row.date}</div>` +
        `<div class="t-row"><span style="width:8px;height:8px;border-radius:2px;background:${upColor}"></span>${upLabel}: <b>+${up}</b></div>` +
        `<div class="t-row"><span style="width:8px;height:8px;border-radius:2px;background:${downColor}"></span>${downLabel}: <b>-${down}</b></div>`,
        ev.clientX, ev.clientY));
      group.addEventListener("mouseleave", hideTooltip);
      svg.appendChild(group);
    });

    container.appendChild(svg);
    legend(container, [
      { label: upLabel, color: upColor },
      { label: downLabel, color: downColor },
    ]);
  }

  return { line, stackedBar, divergingBar };
})();
