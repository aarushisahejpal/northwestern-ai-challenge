/* Tiny self-contained chart lib — SVG, theme-aware via CSS vars, hover layer + table views. */
"use strict";
const NS = "http://www.w3.org/2000/svg";
const SLOT = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)"];
// per-slot in-mark label ink (yellow/aqua too light for white text)
const SLOT_LABEL = ["#ffffff", "#08351f", "#3a2800", "#ffffff", "#ffffff", "#ffffff"];

function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function div(cls, parent, text) {
  const d = document.createElement("div");
  if (cls) d.className = cls;
  if (text != null) d.textContent = text;
  if (parent) parent.appendChild(d);
  return d;
}
function fmtMoney(v) {
  if (v == null || isNaN(v)) return "–";
  const a = Math.abs(v), s = v < 0 ? "-" : "";
  if (a >= 995e6) return s + "$" + (a / 1e9).toFixed(a >= 9.95e9 ? 0 : 1) + "B";
  if (a >= 995e3) return s + "$" + (a / 1e6).toFixed(a >= 9.95e6 ? 0 : 1) + "M";
  if (a >= 1e3) return s + "$" + Math.round(a / 1e3) + "K";
  return s + "$" + Math.round(a);
}
function fmtNum(v) {
  if (v == null || isNaN(v)) return "–";
  return Number(v).toLocaleString("en-US");
}
function fmtPct(v) { return v == null ? "–" : v.toFixed(v < 10 ? 1 : 0) + "%"; }
function niceTicks(max, n) {
  if (max <= 0) return [0, 1];
  const raw = max / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => max / s <= n) || 10 * mag;
  const ticks = [];
  for (let v = 0; v <= max * 1.0001 + step * 0.999; v += step) { ticks.push(v); if (v >= max) break; }
  return ticks;
}

/* singleton tooltip */
let TT = null;
function tt() {
  if (!TT) { TT = div("tt", document.body); }
  return TT;
}
function ttShow(x, y, titleText, rows) {
  const t = tt();
  t.innerHTML = "";
  if (titleText) div("tt-title", t, titleText);
  for (const r of rows) {
    const row = div("row", t);
    if (r.color) { const k = div("k", row); k.style.background = r.color; }
    const v = document.createElement("span"); v.className = "v"; v.textContent = r.value; row.appendChild(v);
    const n = document.createElement("span"); n.className = "n"; n.textContent = r.name; row.appendChild(n);
  }
  t.style.display = "block";
  const bw = t.offsetWidth, bh = t.offsetHeight;
  let px = x + 14, py = y + 12;
  if (px + bw > innerWidth - 8) px = x - bw - 14;
  if (py + bh > innerHeight - 8) py = y - bh - 12;
  t.style.left = px + "px"; t.style.top = py + "px";
}
function ttHide() { if (TT) TT.style.display = "none"; }

function legend(parent, items, kind) {
  const lg = div("legend", parent);
  for (const it of items) {
    const k = div("key", lg);
    const sw = div(kind === "line" ? "sw-line" : "sw-rect", k);
    sw.style.background = it.color;
    k.appendChild(document.createTextNode(it.name));
  }
  return lg;
}

function tableView(parent, cols, rows, fmts) {
  const det = document.createElement("details"); det.className = "tv"; parent.appendChild(det);
  const sum = document.createElement("summary"); sum.textContent = "Table view"; det.appendChild(sum);
  const scroll = div("scroll", det);
  const tb = document.createElement("table"); tb.className = "dt"; scroll.appendChild(tb);
  const trh = tb.insertRow();
  cols.forEach((c, i) => {
    const th = document.createElement("th"); th.textContent = c;
    if (fmts && fmts[i] !== "s") th.className = "num";
    trh.appendChild(th);
  });
  for (const r of rows) {
    const tr = tb.insertRow();
    r.forEach((v, i) => {
      const td = tr.insertCell();
      const f = fmts ? fmts[i] : "s";
      td.textContent = f === "$" ? fmtMoney(v) : f === "#" ? fmtNum(v) : f === "%" ? (v == null ? "–" : v + "%") : (v == null ? "–" : v);
      if (f !== "s") td.className = "num";
    });
  }
}

function card(root, title, sub, foot) {
  const c = div("card", root);
  const h = document.createElement("h2"); h.textContent = title; c.appendChild(h);
  if (sub) div("sub", c, sub);
  const box = div("chart-box", c);
  if (foot) { const f = div("foot", c, foot); c.appendChild(f); }
  return { cardEl: c, box: box };
}

function statTiles(root, tiles) {
  const k = div("kpis", root);
  for (const t of tiles) {
    const tile = div("tile", k);
    div("lbl", tile, t.label);
    div("val", tile, t.value);
    if (t.note) div("note", tile, t.note);
  }
  return k;
}

/* ---- per-widget "more options" → query-info panel (debugging aid) ----
   info = { title, note, blocks: [{label, text}] } — text is the ACTUAL SQL /
   pipeline the widget's numbers came from (extracted from the build scripts). */
function moreOptions(host, info) {
  if (!host || !info) return;
  host.classList.add("has-more");
  const btn = document.createElement("button");
  btn.className = "more-btn"; btn.type = "button"; btn.textContent = "⋯";
  btn.title = "More options";
  btn.setAttribute("aria-label", "More options");
  btn.setAttribute("aria-expanded", "false");
  host.appendChild(btn);
  const menu = div("more-menu", host);
  menu.style.display = "none";
  const item = document.createElement("button");
  item.type = "button"; item.className = "more-item";
  item.textContent = "View query info";
  menu.appendChild(item);
  btn.addEventListener("click", ev => {
    ev.stopPropagation();
    const open = menu.style.display !== "none";
    menu.style.display = open ? "none" : "block";
    btn.setAttribute("aria-expanded", String(!open));
  });
  document.addEventListener("click", () => {
    menu.style.display = "none";
    btn.setAttribute("aria-expanded", "false");
  });
  item.addEventListener("click", ev => {
    ev.stopPropagation();
    menu.style.display = "none";
    btn.setAttribute("aria-expanded", "false");
    openQueryModal(info, btn);
  });
}

function openQueryModal(info, returnFocus) {
  const overlay = div("qmodal-overlay", document.body);
  const modal = div("qmodal", overlay);
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-label", info.title || "Query info");
  const head = div("qp-head", modal);
  const t = document.createElement("strong");
  t.textContent = info.title || "Query info"; head.appendChild(t);
  const close = document.createElement("button");
  close.type = "button"; close.className = "qp-close"; close.textContent = "×";
  close.setAttribute("aria-label", "Close query info");
  head.appendChild(close);
  const body = div("qmodal-body", modal);
  if (info.note) div("qp-note", body, info.note);
  for (const b of (info.blocks || [])) {
    const bh = div("qp-block-head", body);
    const lbl = document.createElement("span");
    lbl.textContent = b.label; bh.appendChild(lbl);
    const pre = document.createElement("pre");
    pre.className = "qp-sql"; pre.textContent = b.text;
    const cp = document.createElement("button");
    cp.type = "button"; cp.className = "qp-copy"; cp.textContent = "Copy";
    cp.addEventListener("click", () => {
      const done = () => { cp.textContent = "Copied"; setTimeout(() => { cp.textContent = "Copy"; }, 1200); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(b.text).then(done, () => {});
      } else {
        const r = document.createRange(); r.selectNodeContents(pre);
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
      }
    });
    bh.appendChild(cp);
    body.appendChild(pre);
  }
  if (info.dict) {
    const foot = div("qmodal-foot", modal);
    foot.appendChild(document.createTextNode("Every table and column referenced here is defined in the data dictionary: "));
    const a = document.createElement("a");
    a.href = info.dict; a.textContent = info.dict;
    foot.appendChild(a);
    foot.appendChild(document.createTextNode(" (in this package, next to the dashboard)."));
  }
  const onKey = ev => { if (ev.key === "Escape") closeModal(); };
  function closeModal() {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
    if (returnFocus) returnFocus.focus();
  }
  close.addEventListener("click", closeModal);
  overlay.addEventListener("click", ev => { if (ev.target === overlay) closeModal(); });
  document.addEventListener("keydown", onKey);
  close.focus();
}

/* ---- line panel: series share one x; crosshair + all-series tooltip ---- */
function linePanel(box, cfg) {
  const W = 980, xs = cfg.x, n = xs.length;
  const H = cfg.height || 240, mL = 46, mR = cfg.marginRight || 76, mT = 14, mB = 30;
  const pw = W - mL - mR, ph = H - mT - mB;
  const maxV = cfg.max || Math.max(...cfg.series.flatMap(s => s.values.filter(v => v != null))) * 1.08;
  const ticks = niceTicks(maxV, 4);
  const yMax = ticks[ticks.length - 1];
  const X = i => mL + (n === 1 ? pw / 2 : (i * pw) / (n - 1));
  const Y = v => mT + ph - (v / yMax) * ph;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" }, null);
  box.appendChild(svg);
  for (const tv of ticks) {
    el("line", { x1: mL, x2: W - mR, y1: Y(tv), y2: Y(tv), class: tv === 0 ? "baseline" : "gridline" }, svg);
    const t = el("text", { x: mL - 8, y: Y(tv) + 4, "text-anchor": "end", class: "ax ax-tab" }, svg);
    t.textContent = cfg.fmt === "$" ? fmtMoney(tv) : cfg.fmt === "%" ? tv + "%" : fmtNum(tv);
  }
  const step = Math.max(1, Math.ceil(n / 12));
  xs.forEach((lab, i) => {
    if (i % step !== 0 && i !== n - 1) return;
    const t = el("text", { x: X(i), y: H - 8, "text-anchor": "middle", class: "ax" }, svg);
    t.textContent = lab;
  });
  const placedLabels = [];
  cfg.series.forEach((s, si) => {
    const col = s.color || SLOT[si];
    const pts = s.values.map((v, i) => (v == null ? null : [X(i), Y(v)]));
    let d = "";
    pts.forEach(p => { if (p) d += (d ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); });
    const path = el("path", { d, fill: "none", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    path.style.stroke = col;
    const last = pts.map((p, i) => (p ? i : -1)).filter(i => i >= 0).pop();
    if (last != null) {
      const ring = el("circle", { cx: pts[last][0], cy: pts[last][1], r: 6 }, svg);
      ring.style.fill = "var(--surface-1)";
      const dot = el("circle", { cx: pts[last][0], cy: pts[last][1], r: 4 }, svg);
      dot.style.fill = col;
      const ly = pts[last][1] + 4;
      // when end-labels collide, fall back to legend + tooltip (skip the label)
      if (!placedLabels.some(p => Math.abs(p - ly) < 14)) {
        const lb = el("text", { x: pts[last][0] + 10, y: ly, class: "dlabel-strong" }, svg);
        lb.textContent = (cfg.endLabel === "name" ? s.name : (cfg.fmt === "$" ? fmtMoney(s.values[last]) : cfg.fmt === "%" ? s.values[last] + "%" : fmtNum(s.values[last])));
        placedLabels.push(ly);
      }
    }
  });
  /* crosshair + tooltip (+ optional per-x click via cfg.onClick(i, xLabel)) */
  const ch = el("line", { y1: mT, y2: mT + ph, class: "crosshair", visibility: "hidden" }, svg);
  const hit = el("rect", { x: mL, y: mT, width: pw, height: ph, fill: "transparent" }, svg);
  const idxAt = ev => {
    const r = svg.getBoundingClientRect();
    const fx = ((ev.clientX - r.left) / r.width) * W;
    let i = Math.round(((fx - mL) / pw) * (n - 1));
    return Math.max(0, Math.min(n - 1, i));
  };
  hit.addEventListener("pointermove", ev => {
    const i = idxAt(ev);
    ch.setAttribute("x1", X(i)); ch.setAttribute("x2", X(i));
    ch.setAttribute("visibility", "visible");
    if (cfg.onClick) hit.style.cursor = "pointer";
    ttShow(ev.clientX, ev.clientY, xs[i], cfg.series.map((s, si) => ({
      color: s.color || SLOT[si],
      value: s.values[i] == null ? "–" : cfg.fmt === "$" ? fmtMoney(s.values[i]) : cfg.fmt === "%" ? s.values[i] + "%" : fmtNum(s.values[i]),
      name: s.name
    })));
  });
  hit.addEventListener("pointerleave", () => { ch.setAttribute("visibility", "hidden"); ttHide(); });
  if (cfg.onClick) {
    hit.addEventListener("click", ev => cfg.onClick(idxAt(ev), xs[idxAt(ev)]));
  }
}

/* ---- columns (single series or stacked) ---- */
function columns(box, cfg) {
  const W = 980, xs = cfg.x, n = xs.length;
  const H = cfg.height || 250, mL = 46, mR = 14, mT = 14, mB = 30;
  const pw = W - mL - mR, ph = H - mT - mB;
  const series = cfg.series; // [{name,color,values}]
  const totals = xs.map((_, i) => series.reduce((a, s) => a + (s.values[i] || 0), 0));
  const ticks = niceTicks(Math.max(...totals) * 1.05, 4);
  const yMax = ticks[ticks.length - 1];
  const Y = v => mT + ph - (v / yMax) * ph;
  const band = pw / n, bw = Math.min(24, band * 0.55);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" }, null);
  box.appendChild(svg);
  for (const tv of ticks) {
    el("line", { x1: mL, x2: W - mR, y1: Y(tv), y2: Y(tv), class: tv === 0 ? "baseline" : "gridline" }, svg);
    const t = el("text", { x: mL - 8, y: Y(tv) + 4, "text-anchor": "end", class: "ax ax-tab" }, svg);
    t.textContent = cfg.fmt === "$" ? fmtMoney(tv) : fmtNum(tv);
  }
  const step = Math.max(1, Math.ceil(n / 12));
  xs.forEach((lab, i) => {
    if (i % step !== 0 && i !== n - 1) return;
    const t = el("text", { x: mL + band * i + band / 2, y: H - 8, "text-anchor": "middle", class: "ax" }, svg);
    t.textContent = lab;
  });
  xs.forEach((lab, i) => {
    const cx = mL + band * i + band / 2;
    let acc = 0;
    series.forEach((s, si) => {
      const v = s.values[i] || 0;
      if (v <= 0) { return; }
      const y1 = Y(acc + v), y0 = Y(acc);
      const hpx = Math.max(0, y0 - y1 - (si < series.length - 1 && acc + v < totals[i] ? 2 : 0)); // 2px surface gap
      const isTop = acc + v >= totals[i] - 1e-9;
      const rTop = isTop ? 4 : 0;
      const x0 = cx - bw / 2;
      const p = el("path", {
        d: `M${x0} ${y0} L${x0} ${y1 + rTop} Q${x0} ${y1} ${x0 + rTop} ${y1} L${x0 + bw - rTop} ${y1} Q${x0 + bw} ${y1} ${x0 + bw} ${y1 + rTop} L${x0 + bw} ${y0} Z`
      }, svg);
      p.style.fill = s.color || SLOT[si];
      acc += v;
    });
    const hit = el("rect", { x: mL + band * i, y: mT, width: band, height: ph, fill: "transparent" }, svg);
    hit.addEventListener("pointermove", ev => {
      const rows = series.map((s, si) => ({
        color: s.color || SLOT[si],
        value: cfg.fmt === "$" ? fmtMoney(s.values[i]) : fmtNum(s.values[i]),
        name: s.name
      }));
      if (series.length > 1) rows.push({ color: null, value: cfg.fmt === "$" ? fmtMoney(totals[i]) : fmtNum(totals[i]), name: "total" });
      ttShow(ev.clientX, ev.clientY, lab, rows);
    });
    hit.addEventListener("pointerleave", ttHide);
  });
}

/* ---- horizontal bars ---- */
function hbars(box, cfg) {
  const items = cfg.items; // [{label, value, value2?, note?, color?}]
  const W = cfg.width || 980, rowH = cfg.rowH || 30, mL = cfg.labelW || 300, mR = cfg.width ? 64 : 90, mT = 6, mB = 8;
  const H = mT + rowH * items.length + mB;
  const pw = W - mL - mR;
  const maxV = Math.max(...items.map(d => d.value)) * 1.02;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" }, null);
  box.appendChild(svg);
  el("line", { x1: mL, x2: mL, y1: mT, y2: H - mB, class: "baseline" }, svg);
  items.forEach((d, i) => {
    const y = mT + i * rowH + (rowH - Math.min(20, rowH - 8)) / 2;
    const bh = Math.min(20, rowH - 8);
    const w = Math.max(1.5, (d.value / maxV) * pw);
    const p = el("path", {
      d: `M${mL} ${y} L${mL + w - 4} ${y} Q${mL + w} ${y} ${mL + w} ${y + 4} L${mL + w} ${y + bh - 4} Q${mL + w} ${y + bh} ${mL + w - 4} ${y + bh} L${mL} ${y + bh} Z`
    }, svg);
    p.style.fill = d.color || cfg.color || SLOT[0];
    const maxChars = Math.floor((mL - 14) / 6.4);
    const lb = el("text", { x: mL - 10, y: y + bh / 2 + 4, "text-anchor": "end", class: "dlabel" }, svg);
    lb.textContent = d.label.length > maxChars ? d.label.slice(0, maxChars - 1) + "…" : d.label;
    const vl = el("text", { x: mL + w + 8, y: y + bh / 2 + 4, class: "dlabel-strong ax-tab" }, svg);
    vl.textContent = cfg.fmt === "$" ? fmtMoney(d.value) : cfg.fmt === "%" ? d.value + "%" : fmtNum(d.value);
    const hit = el("rect", { x: 0, y: mT + i * rowH, width: W, height: rowH, fill: "transparent" }, svg);
    hit.addEventListener("pointermove", ev => {
      const rows = [{ color: d.color || cfg.color || SLOT[0], value: cfg.fmt === "$" ? fmtMoney(d.value) : cfg.fmt === "%" ? d.value + "%" : fmtNum(d.value), name: cfg.valueName || "value" }];
      if (d.note) rows.push({ color: null, value: "", name: d.note });
      if (cfg.onClick) { rows.push({ color: null, value: "click", name: "list the underlying records" }); hit.style.cursor = "pointer"; }
      ttShow(ev.clientX, ev.clientY, d.label, rows);
    });
    hit.addEventListener("pointerleave", ttHide);
    if (cfg.onClick) hit.addEventListener("click", () => cfg.onClick(d, i));
  });
}

/* ---- grouped horizontal bars (2 series) ---- */
function groupedHBars(box, cfg) {
  const items = cfg.items; // [{label, a, b}]
  const W = cfg.width || 980, groupH = 44, mL = cfg.labelW || 300, mR = cfg.width ? 66 : 96, mT = 6, mB = 8;
  const H = mT + groupH * items.length + mB;
  const pw = W - mL - mR;
  const maxV = Math.max(...items.flatMap(d => [d.a, d.b])) * 1.02;
  const F = v => cfg.fmt === "#" ? fmtNum(v) : cfg.fmt === "%" ? fmtPct(v) : fmtMoney(v); // default "$" (existing pages unchanged)
  const colA = cfg.aColor || SLOT[0], colB = cfg.bColor || SLOT[1];
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" }, null);
  box.appendChild(svg);
  el("line", { x1: mL, x2: mL, y1: mT, y2: H - mB, class: "baseline" }, svg);
  const maxChars = Math.floor((mL - 14) / 6.4);
  items.forEach((d, i) => {
    const y0 = mT + i * groupH;
    [["a", colA, cfg.aName, 4], ["b", colB, cfg.bName, 24]].forEach(([k, col, nm, dy]) => {
      const v = d[k], bh = 14;
      const w = Math.max(1.5, (v / maxV) * pw);
      const y = y0 + dy;
      const p = el("path", { d: `M${mL} ${y} L${mL + w - 4} ${y} Q${mL + w} ${y} ${mL + w} ${y + 4} L${mL + w} ${y + bh - 4} Q${mL + w} ${y + bh} ${mL + w - 4} ${y + bh} L${mL} ${y + bh} Z` }, svg);
      p.style.fill = col;
      const vl = el("text", { x: mL + w + 8, y: y + bh / 2 + 4, class: "dlabel ax-tab" }, svg);
      vl.textContent = F(v);
    });
    const lb = el("text", { x: mL - 10, y: y0 + groupH / 2 + 2, "text-anchor": "end", class: "dlabel" }, svg);
    lb.textContent = d.label.length > maxChars ? d.label.slice(0, maxChars - 1) + "…" : d.label;
    const hit = el("rect", { x: 0, y: y0, width: W, height: groupH, fill: "transparent" }, svg);
    hit.addEventListener("pointermove", ev => {
      const rows = [
        { color: colA, value: F(d.a), name: cfg.aName },
        { color: colB, value: F(d.b), name: cfg.bName }
      ];
      // optional tooltip-only context row (no bar, no series color): a value the
      // chart deliberately does not draw but must not hide (e.g. gated-out money)
      if (cfg.cName) rows.push({ color: null, value: F(d.c || 0), name: cfg.cName });
      if (cfg.onClick) { rows.push({ color: null, value: "click", name: "list the underlying records" }); hit.style.cursor = "pointer"; }
      ttShow(ev.clientX, ev.clientY, d.label, rows);
    });
    hit.addEventListener("pointerleave", ttHide);
    if (cfg.onClick) hit.addEventListener("click", () => cfg.onClick(d, i));
  });
}

/* ---- bubble pack (greedy spiral, collision-free) ---- */
function bubblePack(box, cfg) {
  const items = cfg.items.slice().sort((p, q) => q.r0 - p.r0); // r0 = raw size value
  const W = 980, H = cfg.height || 430;
  const maxV = Math.max(...items.map(d => d.r0));
  const R = v => 6 + 52 * Math.sqrt(v / maxV);
  const placed = [];
  const cx0 = W / 2, cy0 = H / 2;
  for (const d of items) {
    const r = R(d.r0);
    let ok = false, x = cx0, y = cy0;
    for (let a = 0, sp = 0; sp < 5200; sp += 4) {
      a = sp * 0.055;
      const rad = sp * 0.115;
      x = cx0 + rad * Math.cos(a) * 1.55;
      y = cy0 + rad * Math.sin(a) * 0.8;
      if (x - r < 6 || x + r > W - 6 || y - r < 6 || y + r > H - 6) continue;
      ok = placed.every(p => {
        const dx = p.x - x, dy = p.y - y;
        return dx * dx + dy * dy >= (p.r + r + 2.5) * (p.r + r + 2.5);
      });
      if (ok) break;
    }
    if (ok) placed.push({ x, y, r, d });
  }
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" }, null);
  box.appendChild(svg);
  const measure = el("text", { x: -1000, y: -1000, class: "blabel" }, svg);
  for (const p of placed) {
    const c = el("circle", { cx: p.x, cy: p.y, r: p.r }, svg);
    c.style.fill = SLOT[p.d.slot];
    c.style.stroke = "var(--surface-1)"; c.style.strokeWidth = "2";
    // label only if it fits
    measure.textContent = p.d.short || p.d.label;
    const tw = measure.getComputedTextLength ? 0 : 0; // measured after attach below
  }
  // second pass for labels (needs layout)
  requestAnimationFrame(() => {
    for (const p of placed) {
      const name = p.d.short || p.d.label;
      measure.textContent = name;
      let tw = 60;
      try { tw = measure.getComputedTextLength(); } catch (e) {}
      if (tw < p.r * 1.75 && p.r > 15) {
        const t = el("text", { x: p.x, y: p.y + (p.r > 26 ? -2 : 4), "text-anchor": "middle", class: "blabel" }, svg);
        t.textContent = name;
        t.style.fill = SLOT_LABEL[p.d.slot];
        if (p.r > 26) {
          const t2 = el("text", { x: p.x, y: p.y + 13, "text-anchor": "middle", class: "blabel" }, svg);
          t2.textContent = cfg.fmtSize === "$" ? fmtMoney(p.d.r0) : fmtNum(p.d.r0);
          t2.style.fill = SLOT_LABEL[p.d.slot];
          t2.style.opacity = "0.85";
        }
      }
    }
    measure.remove();
  });
  /* nearest-circle hover (+ optional click-through via cfg.onClick) */
  const hit = el("rect", { x: 0, y: 0, width: W, height: H, fill: "transparent" }, svg);
  const nearest = ev => {
    const rct = svg.getBoundingClientRect();
    const fx = ((ev.clientX - rct.left) / rct.width) * W;
    const fy = ((ev.clientY - rct.top) / rct.height) * H;
    let best = null, bd = 1e9;
    for (const p of placed) {
      const dx = p.x - fx, dy = p.y - fy;
      const dist = Math.sqrt(dx * dx + dy * dy) - p.r;
      if (dist < bd) { bd = dist; best = p; }
    }
    return bd < 14 ? best : null;
  };
  hit.addEventListener("pointermove", ev => {
    const best = nearest(ev);
    if (best) {
      ttShow(ev.clientX, ev.clientY, best.d.label, cfg.ttRows(best.d));
      if (cfg.onClick) hit.style.cursor = "pointer";
    } else {
      ttHide();
      hit.style.cursor = "";
    }
  });
  hit.addEventListener("pointerleave", ttHide);
  if (cfg.onClick) {
    hit.addEventListener("click", ev => {
      const best = nearest(ev);
      if (best) cfg.onClick(best.d);
    });
  }
}

/* ---- xy scatter: log-x option, sized dots, horizontal threshold rules ----
   cfg: items [{label, short?, x, y, size, slot, extra?}] (x>0 required on log),
        xFmt "$"|"#", yMax (default 100), yFmt "%", rules [{y, label}] recessive
        dashed horizontals with right-margin band labels, labelTop (n of largest-x
        dots to direct-label; plus largest-y dots), ttRows(d), onClick(d) */
function scatterXY(box, cfg) {
  const W = 980, H = cfg.height || 470, mL = 56, mR = 118, mT = 14, mB = 34;
  const pw = W - mL - mR, ph = H - mT - mB;
  const items = cfg.items.filter(d => d.x > 0 && d.y != null);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" }, null);
  box.appendChild(svg);
  if (!items.length) return;
  const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...items.map(d => d.x)))));
  const hi = Math.pow(10, Math.ceil(Math.log10(Math.max(...items.map(d => d.x)))));
  const X = v => mL + ((Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo))) * pw;
  const yMax = cfg.yMax || 100;
  const Y = v => mT + ph - (Math.min(v, yMax) / yMax) * ph;
  const maxS = Math.max(...items.map(d => d.size || 1));
  const R = d => 4 + 9 * Math.sqrt((d.size || 1) / maxS);   // r >= 4 (8px marker floor)
  // y gridlines + labels
  for (const tv of [0, 25, 50, 75, 100].filter(v => v <= yMax)) {
    el("line", { x1: mL, x2: W - mR, y1: Y(tv), y2: Y(tv), class: tv === 0 ? "baseline" : "gridline" }, svg);
    const t = el("text", { x: mL - 8, y: Y(tv) + 4, "text-anchor": "end", class: "ax ax-tab" }, svg);
    t.textContent = tv + "%";
  }
  // x decade ticks
  for (let v = lo; v <= hi * 1.0001; v *= 10) {
    el("line", { x1: X(v), x2: X(v), y1: mT, y2: mT + ph, class: "gridline" }, svg);
    const t = el("text", { x: X(v), y: H - 8, "text-anchor": "middle", class: "ax ax-tab" }, svg);
    t.textContent = cfg.xFmt === "#" ? fmtNum(v) : fmtMoney(v);
  }
  // threshold rules + right-margin band labels (recessive: dashed, axis ink);
  // a label-only entry (noLine) names the band above the last rule
  for (const r of (cfg.rules || [])) {
    if (!r.noLine) {
      const ln = el("line", { x1: mL, x2: W - mR, y1: Y(r.y), y2: Y(r.y),
                              class: "gridline", "stroke-dasharray": "5 4" }, svg);
      ln.style.strokeOpacity = "0.9";
    }
    if (r.label) {
      const t = el("text", { x: W - mR + 8, y: Y(r.labelAt != null ? r.labelAt : r.y) + 4, class: "ax" }, svg);
      t.textContent = r.label;
    }
  }
  // dots (2px surface ring per mark spec), largest first so small dots stay hittable
  const placed = [];
  for (const d of items.slice().sort((p, q) => (q.size || 1) - (p.size || 1))) {
    const x = X(d.x), y = Y(d.y), r = R(d);
    const c = el("circle", { cx: x, cy: y, r: r }, svg);
    c.style.fill = SLOT[d.slot];
    c.style.stroke = "var(--surface-1)";
    c.style.strokeWidth = "2";
    placed.push({ x, y, r, d });
  }
  // selective direct labels: largest-x + largest-y + largest-size dots; on
  // collision try one slot lower before skipping (ties like Amazon/AARP stack)
  const nTop = cfg.labelTop || 12;
  const want = new Set();
  items.slice().sort((p, q) => q.x - p.x).slice(0, nTop).forEach(d => want.add(d));
  items.slice().sort((p, q) => q.y - p.y).slice(0, 8).forEach(d => want.add(d));
  items.slice().sort((p, q) => (q.size || 1) - (p.size || 1)).slice(0, 3).forEach(d => want.add(d));
  const taken = [];
  const collides = b => taken.some(t => Math.abs(t[1] - b[1]) < 12 &&
                        !(t[0] + t[2] < b[0] - 4 || b[0] + b[2] < t[0] - 4));
  for (const p of placed) {
    if (!want.has(p.d)) continue;
    const name = p.d.short || p.d.label;
    let lx = p.x + p.r + 5, anchor = "start";
    if (lx + name.length * 6.2 > W - mR) { lx = p.x - p.r - 5; anchor = "end"; }
    let box_ = [anchor === "end" ? lx - name.length * 6.2 : lx, p.y, name.length * 6.2];
    if (collides(box_)) {
      box_ = [box_[0], p.y + 12, box_[2]];             // one slot lower
      if (collides(box_) || box_[1] > mT + ph) continue;
    }
    const t = el("text", { x: lx, y: box_[1] + 4, "text-anchor": anchor, class: "dlabel" }, svg);
    t.textContent = name;
    taken.push(box_);
  }
  /* nearest-dot hover (+ optional click-through) — same pattern as bubblePack */
  const hit = el("rect", { x: 0, y: 0, width: W, height: H, fill: "transparent" }, svg);
  const nearest = ev => {
    const rct = svg.getBoundingClientRect();
    const fx = ((ev.clientX - rct.left) / rct.width) * W;
    const fy = ((ev.clientY - rct.top) / rct.height) * H;
    let best = null, bd = 1e9;
    for (const p of placed) {
      const dx = p.x - fx, dy = p.y - fy;
      const dist = Math.sqrt(dx * dx + dy * dy) - p.r;
      if (dist < bd) { bd = dist; best = p; }
    }
    return bd < 14 ? best : null;
  };
  hit.addEventListener("pointermove", ev => {
    const best = nearest(ev);
    if (best) {
      ttShow(ev.clientX, ev.clientY, best.d.label, cfg.ttRows(best.d));
      if (cfg.onClick) hit.style.cursor = "pointer";
    } else {
      ttHide();
      hit.style.cursor = "";
    }
  });
  hit.addEventListener("pointerleave", ttHide);
  if (cfg.onClick) {
    hit.addEventListener("click", ev => {
      const best = nearest(ev);
      if (best) cfg.onClick(best.d);
    });
  }
}
