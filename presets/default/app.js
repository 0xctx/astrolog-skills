/* astrolog-skills interactive chart. All data comes from the embedded JSON; text is always set via textContent. */
(function () {
  "use strict";
  const C = window.AstroCore;
  const D = JSON.parse(document.getElementById("chart-data").textContent);
  const chart = D.chart, pack = D.pack, theme = D.theme;
  const NS = "http://www.w3.org/2000/svg";
  const SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"];
  const SIGN_GLYPHS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"].map(g => g + "︎");
  const ELEMENTS = ["fire", "earth", "air", "water"];
  const SHORT = { north_node: "N Node", south_node: "S Node", asc: "Ascendant", mc: "Midheaven" };
  const GLYPH = Object.fromEntries(chart.points.map(p => [p.key, p.glyph]));
  GLYPH.asc = "AC"; GLYPH.mc = "MC";
  const NAME = Object.fromEntries(chart.points.map(p => [p.key, SHORT[p.key] || p.name]));
  NAME.asc = "Ascendant"; NAME.mc = "Midheaven";
  const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
  const mix = (a, b, t) => a.map((x, i) => Math.round(x + (b[i] - x) * t));
  const CX = 500, CY = 500, R_OUT = 476, R_SIGN = 418, R_PLANET = 356, R_ASPECT = 262;

  // theme → CSS variables (one palette with the terminal views)
  const css = document.documentElement.style;
  css.setProperty("--page", rgb(theme.ui.page)); css.setProperty("--frame", rgb(theme.ui.frame));
  css.setProperty("--text", rgb(theme.ui.text)); css.setProperty("--dim", rgb(theme.ui.dim));
  css.setProperty("--title", rgb(theme.ui.title)); css.setProperty("--panel", rgb(theme.ui.center_bg));
  css.setProperty("--label", rgb(theme.ui.label));

  // the harmonics this page shows: one (a single chart) or a range/series stepped through with the slider
  const HARMONICS = (D.harmonics && D.harmonics.length) ? D.harmonics : [D.harmonic || 1];
  const state = { h: HARMONICS[0], shown: null, links: new Map(), tab: "sun", section: "aspects",
                  mid: (pack.midpoints && pack.midpoints.method) || "old", rankBy: "new" };
  let drawStrongest = () => {};  // the strongest-harmonics strip, when the page steps through several harmonics
  const S = D.study || null;  // doctrine and time lords, precomputed in Python (they don't change with the harmonic)

  function fmt(lon) {
    const l = C.norm(lon), s = Math.floor(l / 30), d = l - s * 30;
    let deg = Math.floor(d), min = Math.floor((d - deg) * 60 + 1e-7);
    return `${deg}°${String(min).padStart(2, "0")}′ ${SIGNS[s]}`;
  }
  function el(tag, attrs, parent) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }
  function h(tag, text, cls, parent) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (cls) node.className = cls;
    if (parent) parent.appendChild(node);
    return node;
  }

  // ── geometry: rising sign's degree at 9 o'clock, zodiac counter-clockwise ──
  function asc() { return C.harmonicLon(chart.angles.asc ?? 0, state.h); }
  function xy(lon, r, a0) {
    const a = ((180 + (lon - (a0 ?? asc()))) * Math.PI) / 180;
    return [CX + r * Math.cos(a), CY - r * Math.sin(a)];
  }
  function arcPath(lon1, lon2, r1, r2) {
    const [x1, y1] = xy(lon1, r1), [x2, y2] = xy(lon2, r1), [x3, y3] = xy(lon2, r2), [x4, y4] = xy(lon1, r2);
    return `M${x1},${y1} A${r1},${r1} 0 0 0 ${x2},${y2} L${x3},${y3} A${r2},${r2} 0 0 1 ${x4},${y4} Z`;
  }

  // ── tooltip ──
  const tip = document.getElementById("tip");
  function showTip(evt, lines) {
    tip.replaceChildren();
    lines.forEach((line, i) => { const n = h(i === 0 ? "b" : "div", line); tip.appendChild(n); });
    tip.hidden = false;
    tip.style.left = Math.max(8, Math.min(evt.clientX + 14, window.innerWidth - 360)) + "px";
    tip.style.top = evt.clientY + 14 + "px";
  }
  function hideTip() { tip.hidden = true; }

  // ── the wheel ──
  function spread(items, minGap) {
    const sorted = items.slice().sort((a, b) => a.lon - b.lon);
    for (let pass = 0; pass < 6; pass++) {
      for (let i = 0; i < sorted.length; i++) {
        const a = sorted[i], b = sorted[(i + 1) % sorted.length];
        if (sorted.length < 2) break;
        const gap = C.norm(b.show - a.show);
        if (gap < minGap && !(i === sorted.length - 1 && gap > 180)) {
          const push = (minGap - gap) / 2;
          a.show = C.norm(a.show - push); b.show = C.norm(b.show + push);
        }
      }
    }
    return sorted;
  }

  // what's highlighted: a planet (hover/tap), one aspect (hover a tree row) or a midpoint picture's three bodies
  const focus = { planet: null, pair: null, group: null };
  function related(key) {
    if (focus.pair) return focus.pair.includes(key);
    if (focus.group) return focus.group.includes(key);
    if (focus.planet) return key === focus.planet || state.links.get(focus.planet)?.has(key);
    return true;
  }
  function applyFocus() {
    const any = focus.planet || focus.pair || focus.group;
    const studying = S && state.section !== "aspects";
    drawDoctrine(studying ? focus.planet : null);
    for (const line of document.querySelectorAll("#wheel .aspect")) {
      if (studying) { line.classList.remove("lit"); continue; }
      const a = line.dataset.a, b = line.dataset.b;
      const lit = focus.pair || focus.group
        ? Boolean(focus.pair && focus.pair.includes(a) && focus.pair.includes(b))
        : Boolean(focus.planet && (a === focus.planet || b === focus.planet));
      line.classList.toggle("lit", Boolean(lit));
    }
    for (const g of document.querySelectorAll("#wheel .planet")) {
      g.classList.toggle("faded", Boolean(any) && !related(g.dataset.key));
      g.classList.toggle("focus", !focus.pair && !focus.group && g.dataset.key === focus.planet);
    }
    if (studying) for (const g of document.querySelectorAll("#wheel .planet")) g.classList.remove("faded");
    drawMidpoint();
  }

  // study mode: the signs a planet can't see dim, and lines come in from whoever bonifies (green) or maltreats (red) it
  function drawDoctrine(key) {
    const svg = document.getElementById("wheel");
    svg.querySelector(".doctrine")?.remove();
    const p = key && S ? S.planets.find(x => x.key === key) : null;
    for (const g of document.querySelectorAll("#wheel .sign")) {
      const apart = p ? (((Number(g.dataset.sign) - Math.floor(C.norm(p.lon) / 30)) % 12) + 12) % 12 : 0;
      g.classList.toggle("away", Boolean(p) && [1, 5, 7, 11].includes(apart));
    }
    if (!p || !state.lons || state.h !== 1) return;
    const g = el("g", { class: "doctrine" }, svg);
    for (const c of p.conditions) {
      for (const a of c.actor.split("+")) {
        if (state.lons[a] === undefined) continue;
        const [x1, y1] = xy(state.lons[a], R_ASPECT), [x2, y2] = xy(state.lons[key], R_ASPECT);
        el("line", { x1, y1, x2, y2, class: "doctrine-line", stroke: c.effect === "bonify" ? "var(--good)" : "var(--bad)", "stroke-width": 3, "stroke-linecap": "round", opacity: ".9" }, g);
      }
    }
  }

  // hovering a midpoint row: a marker at the midpoint, dashed lines from the pair, and the aspect line from the body
  function drawMidpoint() {
    const svg = document.getElementById("wheel");
    svg.querySelector(".midpoint")?.remove();
    const m = focus.mid;
    if (!m || !state.lons) return;
    const L = state.lons;
    if (L[m.a] === undefined || L[m.b] === undefined || L[m.focus] === undefined) return;
    const mid = C.midpoint(L[m.a], L[m.b]);
    const g = el("g", { class: "midpoint" }, svg);
    const [mx, my] = xy(mid, R_ASPECT);
    const col = rgb(theme.aspects[m.family]);
    for (const k of [m.a, m.b]) {
      const [x, y] = xy(L[k], R_ASPECT);
      el("line", { x1: x, y1: y, x2: mx, y2: my, stroke: rgb(theme.ui.dim), "stroke-width": 1.5, "stroke-dasharray": "5 6", opacity: ".8" }, g);
    }
    const [fx, fy] = xy(L[m.focus], R_ASPECT);
    el("line", { x1: fx, y1: fy, x2: mx, y2: my, stroke: col, "stroke-width": 3, "stroke-linecap": "round", opacity: ".95" }, g);
    el("circle", { cx: mx, cy: my, r: 7, fill: rgb(theme.ui.page), stroke: col, "stroke-width": 2.5 }, g);
  }

  function drawWheel(positions) {
    const svg = document.getElementById("wheel");
    svg.replaceChildren();
    const ui = theme.ui;
    const defs = el("defs", {}, svg);
    const glow = el("filter", { id: "glow", x: "-50%", y: "-50%", width: "200%", height: "200%" }, defs);
    el("feGaussianBlur", { stdDeviation: "10" }, glow);
    const core = el("radialGradient", { id: "core", cx: "50%", cy: "50%", r: "50%" }, defs);
    el("stop", { offset: "0%", "stop-color": rgb(ui.center_bg), "stop-opacity": "1" }, core);
    el("stop", { offset: "70%", "stop-color": rgb(ui.center_bg), "stop-opacity": ".55" }, core);
    el("stop", { offset: "100%", "stop-color": rgb(ui.page), "stop-opacity": "0" }, core);

    // soft halo, then the body of the wheel
    el("circle", { cx: CX, cy: CY, r: R_OUT, fill: rgb(ui.frame), opacity: ".10", filter: "url(#glow)" }, svg);
    el("circle", { cx: CX, cy: CY, r: R_OUT, fill: "url(#core)" }, svg);

    // sign ring: each sign in its element's deep tone, a bright rim, and the glyph in the element colour
    for (let s = 0; s < 12; s++) {
      const e = theme.elements[ELEMENTS[s % 4]];
      const sg = el("g", { class: "sign", "data-sign": s }, svg);
      el("path", { d: arcPath(s * 30, s * 30 + 30, R_OUT, R_SIGN), fill: rgb(mix(e.body_bg, e.header_bg, 0.22)), stroke: rgb(ui.page), "stroke-width": 1.5 }, sg);
      el("path", { d: arcPath(s * 30 + 0.4, s * 30 + 29.6, R_OUT, R_OUT - 5), fill: rgb(e.header_bg), opacity: ".9" }, sg);
      const [gx, gy] = xy(s * 30 + 15, (R_OUT - 5 + R_SIGN) / 2);
      const t = el("text", { x: gx, y: gy, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 28, fill: rgb(mix(e.header_bg, ui.white, 0.25)), class: "glyph" }, sg);
      t.textContent = SIGN_GLYPHS[s];
      const title = el("title", {}, t); title.textContent = SIGNS[s];
    }
    // degree scale just inside the signs
    for (let d = 0; d < 360; d += 1) {
      const len = d % 10 === 0 ? 10 : d % 5 === 0 ? 6 : 3;
      const [x1, y1] = xy(d, R_SIGN), [x2, y2] = xy(d, R_SIGN - len);
      el("line", { x1, y1, x2, y2, stroke: rgb(ui.dim), "stroke-opacity": d % 5 === 0 ? ".55" : ".3", "stroke-width": 1 }, svg);
    }
    el("circle", { cx: CX, cy: CY, r: R_SIGN - 10, fill: "none", stroke: rgb(ui.dim), "stroke-opacity": ".18" }, svg);
    el("circle", { cx: CX, cy: CY, r: R_ASPECT, fill: "none", stroke: rgb(ui.dim), "stroke-opacity": ".22" }, svg);

    // house cusps (natal only): quiet lines and numbers, no angle axes
    if (state.h === 1 && chart.cusps && chart.cusps.length === 12) {
      chart.cusps.forEach((c, i) => {
        const [x1, y1] = xy(c, R_SIGN - 10), [x2, y2] = xy(c, R_ASPECT);
        el("line", { x1, y1, x2, y2, stroke: rgb(ui.dim), "stroke-opacity": ".22", "stroke-width": 1 }, svg);
        const next = chart.cusps[(i + 1) % 12];
        const [tx, ty] = xy(c + C.norm(next - c) / 2, R_ASPECT + 14);
        const t = el("text", { x: tx, y: ty, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 12, fill: rgb(ui.dim), "fill-opacity": ".7" }, svg);
        t.textContent = String(i + 1);
      });
    }

    // aspect lines between planets: hidden until a planet (or a tree row) is hovered
    const pos = Object.fromEntries(positions.map(p => [p.key, p]));
    state.lons = Object.fromEntries(positions.map(p => [p.key, p.lon]));
    for (const k of ["asc", "mc"]) if (chart.angles[k] !== undefined) state.lons[k] = C.harmonicLon(chart.angles[k], state.h);
    const lines = el("g", { class: "aspects" }, svg);
    state.links = new Map();
    for (const a of C.aspects(chart, pack, state.h)) {
      if (!pos[a.a] || !pos[a.b]) continue;  // the angles stay out of the wheel
      for (const [x, y] of [[a.a, a.b], [a.b, a.a]]) {
        if (!state.links.has(x)) state.links.set(x, new Set());
        state.links.get(x).add(y);
      }
      const [x1, y1] = xy(pos[a.a].lon, R_ASPECT), [x2, y2] = xy(pos[a.b].lon, R_ASPECT);
      const line = el("line", {
        x1, y1, x2, y2, class: "aspect", stroke: rgb(theme.aspects[a.family]), "stroke-linecap": "round",
        "stroke-width": (1.2 + 2.8 * a.strength).toFixed(2), style: `--o:${(0.35 + 0.65 * a.strength).toFixed(2)}`,
      }, lines);
      line.dataset.a = a.a; line.dataset.b = a.b;
    }

    // planets, spread apart when crowded, with a leader line to their exact degree
    const items = spread(positions.map(p => ({ ...p, show: p.lon })), 7.5);
    for (const p of items) {
      const e = theme.elements[ELEMENTS[Math.floor(C.norm(p.lon) / 30) % 4]];
      const g = el("g", { class: "planet", tabindex: 0 }, svg);
      g.dataset.key = p.key;
      const [ex, ey] = xy(p.lon, R_SIGN - 12), [lx, ly] = xy(p.show, R_PLANET + 21);
      el("line", { x1: ex, y1: ey, x2: lx, y2: ly, stroke: rgb(e.header_bg), "stroke-opacity": ".45", "stroke-width": 1 }, g);
      const [dx, dy] = xy(p.lon, R_SIGN - 12);
      el("circle", { cx: dx, cy: dy, r: 2.5, fill: rgb(e.header_bg) }, g);
      const [px, py] = xy(p.show, R_PLANET);
      el("circle", { class: "disc", cx: px, cy: py, r: 20, fill: rgb(ui.page), stroke: rgb(e.header_bg), "stroke-width": 1.5 }, g);
      const t = el("text", { x: px, y: py + 1, "text-anchor": "middle", "dominant-baseline": "central", "font-size": p.glyph.length > 1 ? 14 : 22, fill: rgb(e.accent), class: p.glyph.length > 1 ? "" : "glyph" }, g);
      t.textContent = p.glyph;
      const [nx, ny] = xy(p.show, R_PLANET - 34);
      const deg = el("text", { x: nx, y: ny, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 12, fill: rgb(ui.dim) }, g);
      deg.textContent = `${Math.floor(C.norm(p.lon) % 30)}°` + (p.speed < 0 && !p.key.endsWith("_node") ? " ℞" : "");
      g.addEventListener("mouseenter", () => { if (!focus.sticky) { focus.planet = p.key; applyFocus(); } });
      g.addEventListener("mouseleave", () => { if (!focus.sticky) { focus.planet = null; applyFocus(); } });
      g.addEventListener("click", evt => {  // tap (touch screens) or click: keep this planet's aspects lit
        evt.stopPropagation();
        const same = focus.sticky && focus.planet === p.key;
        Object.assign(focus, { planet: same ? null : p.key, pair: null, group: null, sticky: !same });
        if (!same) { state.tab = p.key; renderPanel(); }
        if (!same && S && state.section !== "aspects") {
          if (state.section !== "planets") showSection("planets");
          document.getElementById("study-" + p.key)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
        applyFocus();
      });
      g.addEventListener("focus", () => { focus.planet = p.key; applyFocus(); });
      g.addEventListener("blur", () => { if (!focus.sticky) { focus.planet = null; applyFocus(); } });
    }
    // centre: the harmonic number, or a small star for the natal chart
    const centre = el("text", { x: CX, y: CY, "text-anchor": "middle", "dominant-baseline": "central", "font-size": state.h > 1 ? 56 : 20, fill: rgb(ui.title), "fill-opacity": state.h > 1 ? ".85" : ".45", "font-weight": 600, class: state.h > 1 ? "" : "glyph" }, svg);
    centre.textContent = state.h > 1 ? `H${state.h}` : "✦";
    applyFocus();
  }
  document.addEventListener("click", () => { if (focus.sticky) { Object.assign(focus, { planet: null, sticky: false }); applyFocus(); } });

  // ── animation between harmonics (shortest way round) ──
  let anim = null;
  function target() {
    return chart.points.map(p => ({ key: p.key, glyph: p.glyph, lon: C.harmonicLon(p.lon, state.h), speed: p.speed * state.h, house: p.house }));
  }
  function animateTo(next, ms) {
    cancelAnimationFrame(anim);
    if (!state.shown || ms <= 0) { state.shown = next; drawWheel(next); return; }  // first draw: no animation
    const from = state.shown.map(p => p.lon);
    const start = performance.now();
    const step = now => {
      const t = Math.min(1, Math.max(0, (now - start) / ms)), e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      const frame = next.map((p, i) => {
        const d = ((p.lon - from[i] + 540) % 360) - 180;
        return { ...p, lon: C.norm(from[i] + d * e) };
      });
      drawWheel(frame);
      if (t < 1) anim = requestAnimationFrame(step); else { state.shown = next; drawWheel(next); }
    };
    anim = requestAnimationFrame(step);
  }

  // ── side panels ──
  // orbs in a harmonic chart show as measured there, or ÷ H when display.orbs = "natal"
  function scale() { return state.h > 1 && D.display && D.display.orbs === "natal" ? state.h : 1; }
  function orbDM(orb) { const m = Math.floor(orb * 60 + 1e-7); return `${Math.floor(m / 60)}°${String(m % 60).padStart(2, "0")}′`; }
  const ABBR = { asc: "AC", mc: "MC" };
  // ── hover text: the contact itself; plus the reading's note for it when exported with --interp ──
  const NOTES = D.interp ? D.notes || {} : {};
  function explain(focusKey, r) {
    const a = r.a;
    if (!r.mid) {
      const other = a.a === focusKey ? a.b : a.a;
      const note = NOTES[`h${state.h}:${a.a}-${a.aspect}-${a.b}`];
      return [`${NAME[focusKey]} ${a.name} ${NAME[other]}`, note].filter(Boolean);
    }
    const note = NOTES[`h${state.h}:${focusKey}@${a.a}/${a.b}-${a.aspect}`];
    const own = a.vibration && a.vibration !== state.h ? `Its own vibration is H${a.vibration}.` : "";
    const how = a.method === "new" ? "new method: the natal angle × H" : "old method: the midpoint in this harmonic chart";
    return [`${NAME[focusKey]} ${a.name} the ${NAME[a.a]}/${NAME[a.b]} midpoint`, `${(a.strength * 100).toFixed(0)}% · ${how}`,
            own, note].filter(Boolean);
  }

  // ── the panel beside the wheel: one tab per body, the selected body's aspects then midpoints ──
  function elementColour(lon) { return theme.elements[ELEMENTS[Math.floor(C.norm(lon) / 30) % 4]].header_bg; }
  function renderPanel() {
    const k = scale();
    const mp = pack.midpoints;
    const sw = document.querySelector(".mp-seg");
    if (sw) sw.hidden = state.h === 1;  // at H1 both methods measure the same angle: the classic one is shown
    const bodies = C.bodies(chart, state.h).filter(x => x.key !== "south_node");
    if (!bodies.some(b => b.key === state.tab)) state.tab = bodies[0].key;
    const tabs = document.getElementById("tabs");
    tabs.replaceChildren();
    for (const b of bodies) {
      const t = h("button", GLYPH[b.key], b.key === state.tab ? "tab active" : "tab", tabs);
      t.type = "button"; t.title = NAME[b.key];
      t.setAttribute("role", "tab"); t.setAttribute("aria-selected", String(b.key === state.tab));
      if (GLYPH[b.key].length > 1) t.classList.add("letters");
      t.style.setProperty("--el", rgb(elementColour(b.lon)));
      t.addEventListener("click", evt => {
        evt.stopPropagation();
        state.tab = b.key;
        const onWheel = chart.points.some(p => p.key === b.key);
        Object.assign(focus, { planet: onWheel ? b.key : null, pair: null, group: null, sticky: onWheel });
        renderPanel(); applyFocus();
      });
    }
    const b = bodies.find(x => x.key === state.tab);
    const tree = document.getElementById("tree");
    tree.replaceChildren();
    const head = h("h3", null, null, tree);
    const hg = h("span", GLYPH[b.key], "g", head);
    hg.style.color = rgb(elementColour(b.lon));
    h("span", NAME[b.key], "who", head);
    h("span", fmt(b.lon), "pos", head);
    const rows = [];
    for (const a of C.aspects(chart, pack, state.h).filter(a => a.a === b.key || a.b === b.key).sort((x, y) => x.orb - y.orb)) {
      const other = a.a === b.key ? a.b : a.a;
      if (other !== "south_node") rows.push({ a, text: NAME[other], mid: false });
    }
    const mids = mp.aspects.length ? C.midpointContacts(chart, pack, state.h, state.h === 1 ? "old" : state.mid)[b.key] || [] : [];
    if (rows.length && mids.length) rows.push(null);  // a quiet divider between planets and midpoints
    for (const c of mids) rows.push({ a: c, text: `${ABBR[c.a] || NAME[c.a]}/${ABBR[c.b] || NAME[c.b]}`, mid: true });
    if (!rows.length) h("div", "no contacts", "none", tree);
    for (const r of rows) {
      if (r === null) { h("div", "midpoints", "divider", tree); continue; }
      const row = h("div", null, r.mid ? "row mid" : "row", tree);
      const sym = h("span", r.a.glyph, "sym", row);
      sym.style.color = rgb(theme.aspects[r.a.family]);
      sym.style.opacity = (0.45 + 0.55 * r.a.strength).toFixed(2);
      h("span", r.text, "name", row);
      h("span", orbDM(r.a.orb / k), "orb", row);
      row.addEventListener("mousemove", evt => showTip(evt, explain(b.key, r)));
      row.addEventListener("mouseleave", hideTip);
      if (r.a.strength > 0.5) row.classList.add("tight");
      const who = r.mid ? [b.key, r.a.a, r.a.b] : [r.a.a, r.a.b];
      row.addEventListener("mouseenter", () => {
        Object.assign(focus, r.mid
          ? { pair: null, group: who, mid: { focus: b.key, a: r.a.a, b: r.a.b, family: r.a.family } }
          : { pair: who, group: null, mid: null });
        applyFocus();
      });
      row.addEventListener("mouseleave", () => { Object.assign(focus, { pair: null, group: null, mid: null }); applyFocus(); });
    }
  }
  function update(ms) {
    document.getElementById("hval").textContent = `H${state.h}`;
    renderPanel();
    drawStrongest();
    renderGrid();
    animateTo(target(), ms);
  }

  // ── the aspect table beside the wheel (study pages): configurations by whole sign, the close ones in bold ──
  const ASPECT_GLYPH = { conjunction: "☌", sextile: "⚹", square: "□", trine: "△", opposition: "☍" };
  const ASPECT_FAMILY = { conjunction: "conjunction", sextile: "soft", square: "hard", trine: "soft", opposition: "hard" };
  function renderGrid() {
    const box = document.getElementById("grid");
    if (!box || !S || !S.configurations) return;
    box.replaceChildren();
    const keys = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "asc", "mc"];
    const pairs = new Map(S.configurations.map(c => [`${c.a}|${c.b}`, c]));
    const table = h("table", null, "grid", box);
    const body = h("tbody", null, null, table);
    keys.forEach((row, i) => {
      const tr = h("tr", null, null, body);
      for (let j = 0; j < i; j++) {
        const col = keys[j], c = pairs.get(`${col}|${row}`) || pairs.get(`${row}|${col}`);
        const td = h("td", null, c && c.aspect ? "hit" : "away", tr);
        if (!c || !c.aspect) {
          td.addEventListener("mousemove", evt => showTip(evt, [`${NAME[col]} · ${NAME[row]}`, "aversion"]));
          td.addEventListener("mouseleave", hideTip);
          continue;
        }
        const close = c.distance <= 3;
        const g = h("span", ASPECT_GLYPH[c.aspect] + "︎", "sym", td);
        g.style.color = rgb(theme.aspects[ASPECT_FAMILY[c.aspect]]);
        g.style.opacity = close ? "1" : ".7";
        if (close) td.classList.add("tight");
        td.tabIndex = 0;
        const facts = [orbDM(c.distance), c.applying === true ? "applying" : c.applying === false ? "separating" : "", c.overcomes ? `${NAME[c.overcomes]} overcomes` : ""].filter(Boolean);
        const lines = [`${NAME[c.a]} ${ASPECT_GLYPH[c.aspect]}︎ ${NAME[c.b]}`, facts.join(" · ")];
        td.addEventListener("mousemove", evt => showTip(evt, lines));
        td.addEventListener("mouseleave", () => { hideTip(); focus.pair = null; applyFocus(); });
        td.addEventListener("mouseenter", () => { Object.assign(focus, { pair: [c.a, c.b], group: null, mid: null }); applyFocus(); });
      }
      const head = h("th", GLYPH[row], row === "asc" || row === "mc" ? "letters" : "", tr);
      head.title = NAME[row];
      const pl = S.planets.find(p => p.key === row);
      head.style.color = pl ? rgb(elementColour(pl.lon)) : "var(--text)";
    });
  }


  // ── study: teaching popovers, sect, planets, lots, time lords, the life timeline ──
  const ORD = n => n + ((n % 100 >= 11 && n % 100 <= 13) ? "th" : ({ 1: "st", 2: "nd", 3: "rd" })[n % 10] || "th");
  const PNAME = k => NAME[k] || k;
  // why it holds here, then the pack's own glossary entry and its pages — shown on hover, focus or tap
  function teach(node, title, here, term, note) {
    if (node.tabIndex < 0) node.tabIndex = 0;
    const entry = term && S && S.glossary ? S.glossary[term] : null;
    const show = (x, y) => {
      tip.replaceChildren();
      h("b", title || (entry && entry.title) || "", null, tip);
      if (note) { h("div", "In this reading", "label", tip); h("div", note, "note", tip); }
      if (here) { if (note) h("div", "Why", "label", tip); h("div", here, "here", tip); }
      if (entry) {
        h("div", entry.text, "learn", tip);
        if (entry.pages) h("div", "Read " + entry.pages, "read", tip);
      }
      tip.hidden = false;
      const r = tip.getBoundingClientRect();
      tip.style.left = Math.max(8, Math.min(x + 14, window.innerWidth - r.width - 8)) + "px";
      tip.style.top = Math.max(8, Math.min(y + 14, window.innerHeight - r.height - 8)) + "px";
    };
    node.addEventListener("mousemove", evt => show(evt.clientX, evt.clientY));
    node.addEventListener("mouseleave", hideTip);
    node.addEventListener("focus", () => { const b = node.getBoundingClientRect(); show(b.left, b.bottom); });
    node.addEventListener("blur", hideTip);
    node.addEventListener("click", evt => { evt.stopPropagation(); const b = node.getBoundingClientRect(); show(b.left, b.bottom); });
  }
  document.addEventListener("click", hideTip);

  function niceDate(iso) {
    return new Date(iso + "T00:00:00Z").toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  }
  function dm(x) { const m = Math.floor(Math.abs(x) * 60 + 1e-7); return `${Math.floor(m / 60)}°${String(m % 60).padStart(2, "0")}′`; }

  function renderSect() {
    const box = document.getElementById("sect");
    box.hidden = false;
    const day = h("span", (S.sect.day ? "Day chart" : "Night chart") + " · sect light " + (S.sect.day ? "Sun" : "Moon"), "day", box);
    teach(day, S.sect.day ? "Day chart" : "Night chart", S.sect.why, S.sect.term, S.sect.note);
    for (const w of S.sect.spectrum) {
      const c = h("span", null, "who", box);
      const g = h("span", (GLYPH[w.key] || "") + " " + w.name + " ", null, c);
      g.style.color = "var(--text)";
      h("small", w.role, null, c);
      teach(c, `${w.name}: ${w.role}`, w.why, w.term);
    }
    if (S.sect.spectrum.length) h("span", null, "scale", box);
  }

  function renderStudyPlanets(box) {
    for (const p of S.planets) {
      const d = h("div", null, "pl", box);
      d.id = "study-" + p.key;
      const head = h("h3", null, null, d);
      const g = h("span", GLYPH[p.key], "g", head);
      g.style.color = rgb(elementColour(p.lon));
      h("span", p.name, null, head);
      h("span", `${p.pos} · ${ORD(p.place)} place`, "pos", head);
      if (p.note) h("p", p.note, "synth", d);
      const chips = h("div", null, "chips", d);
      const quiet = p.tokens.filter(t => !t.tone && !t.note);
      for (const t of p.tokens.filter(t => t.tone || t.note)) teach(h("span", t.label, "chip " + t.tone + (t.note ? " noted" : ""), chips), t.label, t.why, t.term, t.note);
      if (quiet.length) {
        const more = h("button", `+${quiet.length} details`, "chip more", chips);
        more.type = "button";
        more.addEventListener("click", evt => {
          evt.stopPropagation();
          more.remove();
          for (const t of quiet) teach(h("span", t.label, "chip", chips), t.label, t.why, t.term, t.note);
        });
      }
      for (const c of p.conditions) {
        const row = h("div", null, "cond " + c.effect, d);
        h("span", c.effect === "bonify" ? "+" : "−", "mk", row);
        const txt = h("span", null, null, row);
        h("span", `${c.effect === "bonify" ? "Bonified" : "Maltreated"} by ${c.actors.join(" and ")} `, null, txt);
        const how = [c.label.toLowerCase(), c.aspect, c.distance != null ? `${dm(c.distance)} ${c.applying ? "applying" : "separating"}` : ""].filter(Boolean).join(" · ");
        h("span", how + (c.reception ? " · reception" : ""), "how", txt);
        teach(row, c.label, c.why, c.term, c.note);
        if (c.note) row.classList.add("noted");
        row.addEventListener("mouseenter", () => { focus.planet = p.key; applyFocus(); });
      }
      d.addEventListener("mouseenter", () => { focus.planet = p.key; applyFocus(); });
    }
    // chart-wide findings the pack switched on: the Midheaven degree's place, assembly, the Moon's course, Mercury's role
    if (S.further && S.further.length) {
      h("h3", "Also in this chart", "also", box);
      for (const f of S.further) {
        const d = h("div", null, "lot", box);
        h("b", f.title, null, h("div", null, "top", d));
        h("p", f.text, "synth", d);
        teach(d, f.title, f.text, f.term, f.note);
      }
    }
  }

  function renderStudyLots(box) {
    for (const l of S.lots) {
      const d = h("div", null, "lot", box);
      const top = h("div", null, "top", d);
      h("b", "Lot of " + l.title, null, top);
      h("span", `${l.pos} · ${ORD(l.place)} place` + (l.lord ? ` · lord ${l.lord_name} in the ${ORD(l.lord_place)}` : ""), null, top);
      const score = h("span", null, "score", top);
      h("span", "+" + l.good.length, null, score).style.color = "var(--good)";
      score.append(" ");
      h("span", "−" + l.bad.length, null, score).style.color = "var(--bad)";
      const m = h("div", null, "meter", d);
      h("div", null, "g", m).style.flex = String(l.good.length);
      h("div", null, "b", m).style.flex = String(l.bad.length);
      const here = `${l.why} For it: ${l.good.join(", ") || "nothing"}. Against it: ${l.bad.join(", ") || "nothing"}.`;
      if (l.note) h("p", l.note, "synth", d);
      teach(d, "Lot of " + l.title, here, l.term, l.note);
      d.addEventListener("mouseenter", () => { if (l.lord) { focus.planet = l.lord; applyFocus(); } });
    }
  }

  // ── time lords on a date ──
  const T0 = Date.parse(S ? S.birth : "2000-01-01"), T1 = Date.parse(S ? S.end : "2001-01-01");
  const isoOf = d => new Date(T0 + d * 864e5).toISOString().slice(0, 10);
  const when = document.getElementById("when");
  function periodWhy(r) {
    const bits = [`${r.sign}, ruled by ${PNAME(r.lord)}, from ${niceDate(r.begins)} to ${niceDate(r.ends)}; the ${ORD(r.from_fortune)} sign from Fortune.`];
    if (r.peak) bits.push(`A peak, rank ${r.peak} in the pack's order.`);
    if (r.loosing) bits.push("Here the subperiods jump to the opposite sign: the loosing of the bond.");
    if (r.completion) bits.push("Back at the starting sign after the loosing: a completion.");
    if (r.in_sign.length) bits.push("Natal " + r.in_sign.map(PNAME).join(" and ") + " in this sign colour the period.");
    if (r.superior_square.length) bits.push(r.superior_square.map(PNAME).join(" and ") + " overcome the sign by square.");
    if (r.benefic_angle) bits.push("The benefic of the sect sees it from an angle: easier.");
    if (r.malefic_angle) bits.push("The malefic contrary to the sect sees it from an angle: harder.");
    return bits.join(" ");
  }
  function termFor(r) { return r.peak ? "peak_period" : r.loosing ? "loosing_of_the_bond" : r.completion ? "completion" : "zodiacal_releasing"; }
  function renderStudyTime(box) {
    const day = isoOf(Number(when.value));
    const cards = h("div", null, "cards", box);
    const years = (S.profections || []).filter(y => y.begins <= day && day < y.ends);
    for (const y of years) {
      const c = h("div", null, "card", cards);
      const from = y.start === "asc" ? "" : y.start === "sect_light" ? " · from the sect light" : y.start === "contrary_light" ? " · from the other light" : ` · from ${y.start}`;
      h("div", `Profection year · age ${y.age}${from}`, "k", c);
      const v = h("div", null, "v", c);
      v.append(`${ORD(y.place)} place, ${y.sign} · lord ${PNAME(y.lord)} in the ${ORD(y.lord_place)} `);
      h("em", "· to " + niceDate(y.ends), null, v);
      const lord = S.planets.find(p => p.key === y.lord);
      const natal = lord && lord.conditions.length ? " Natally it is " + lord.conditions.map(c => `${c.effect === "bonify" ? "bonified" : "maltreated"} by ${c.actors.join(" and ")} (${c.label.toLowerCase()})`).join("; ") + "." : "";
      const inSign = y.planets_in_sign.length ? ` ${y.planets_in_sign.map(PNAME).join(" and ")} in the sign ${y.planets_in_sign.length > 1 ? "are" : "is"} activated too.` : "";
      if (y.note) h("p", y.note, "synth", c);
      teach(c, `Age ${y.age}: the ${ORD(y.place)} place`, `${y.sign} is ${y.age} signs on from the starting sign. Its lord ${PNAME(y.lord)} is lord of the year and sits in the ${ORD(y.lord_place)} place, whose topics join the year's.${inSign}${natal}`, "annual_profections", y.note);
    }
    for (const [lot, rel] of Object.entries(S.releasing || {})) {
      for (const r of rel.periods.filter(r => r.begins <= day && day < r.ends)) {
        const c = h("div", null, "card", cards);
        h("div", `Releasing from ${lot === "spirit" ? "Spirit" : lot === "fortune" ? "Fortune" : lot} · level ${r.level}`, "k", c);
        const v = h("div", null, "v", c);
        v.append(`${r.sign} · lord ${PNAME(r.lord)} `);
        h("em", `· ${niceDate(r.begins)} – ${niceDate(r.ends)}`, null, v);
        if (r.peak) h("span", "peak " + r.peak, "flag peak", v);
        if (r.loosing) h("span", "loosing of the bond", "flag lb", v);
        if (r.note) h("p", r.note, "synth", c);
        teach(c, `${lot === "spirit" ? "Spirit" : "Fortune"} L${r.level}: ${r.sign}`, periodWhy(r) + (rel.shifted && lot === "spirit" ? " Spirit shares Fortune's sign, so releasing starts from the next sign." : ""), termFor(r), r.note);
      }
    }
    if (S.lords) {
      const L = S.lords, c = h("div", null, "card", cards);
      h("div", "The sect light's lords", "k", c);
      h("div", L.lords.map(x => `${PNAME(x.planet)} (${ORD(x.place)}${x.quality ? ", " + x.quality : ""})`).join(" → "), "v", c);
      const change = L.changeover.length ? ` The second may take over in year ${L.changeover.map(x => x.year_of_life).join(" or ")} (${L.changeover.map(x => x.method.replace("_", " ")).join(" or ")}).` : "";
      if (L.note) h("p", L.note, "synth", c);
      teach(c, "The sect light's lords", `The ${L.light === "sun" ? "Sun" : "Moon"} in ${L.sign} gives ${L.lords.map(x => PNAME(x.planet)).join(", ")}: the first for the first part of life, the second for the second, the third throughout.${change}`, "triplicity_lords_of_the_sect_light", L.note);
    }
  }

  // the life: an overview, each topic judged by its three testimonies, and the chapters of the life
  function renderLife(box) {
    const intro = h("div", null, "life-intro", box);
    if (S.life.note) h("p", S.life.note, "overview", intro);
    else h("p", "No reading is written for this chart yet: each topic below shows its testimonies and how they lean. A reading adds what they mean for this person.", "overview empty", intro);
    const grid = h("div", null, "topics", box);
    for (const t of S.topics || []) {
      const card = h("div", null, "topic " + t.tone, grid);
      const head = h("div", null, "topic-head", card);
      h("b", t.label, null, head);
      const v = h("span", t.verdict, "verdict " + t.tone, head);
      teach(v, `${t.label}: ${t.verdict}`, t.why, null, null);
      if (t.note) h("p", t.note, "plain", card);
      const how = h("button", "How the chart shows this", "how-toggle", card);
      how.type = "button";
      const row = h("div", null, "testimonies", card);
      row.hidden = Boolean(t.note);  // with a reading, the evidence waits one click away
      how.addEventListener("click", evt => { evt.stopPropagation(); row.hidden = !row.hidden; });
      for (const c of t.components) {
        const chip = h("span", null, "testimony " + c.lean, row);
        h("span", c.title, null, chip);
        h("small", ` +${c.good.length} −${c.bad.length}`, null, chip);
        const here = `${c.why} For: ${c.good.join(", ") || "nothing"}. Against: ${c.bad.join(", ") || "nothing"}.`;
        const linked = c.ref.startsWith("planet:") ? S.planets.find(p => "planet:" + p.key === c.ref)
          : c.ref.startsWith("lot:") ? S.lots.find(l => "lot:" + l.name === c.ref)
          : S.places.find(p => "place:" + p.place === c.ref);
        teach(chip, c.title, here, null, linked ? linked.note : null);
        if (c.ref.startsWith("planet:")) chip.addEventListener("mouseenter", () => { focus.planet = c.ref.slice(7); applyFocus(); });
      }
      teach(head, t.label, t.why, null, t.note);
    }
    renderComingUp(box);
    const chapters = h("div", null, "chapters", box);
    for (const [lot, rel] of Object.entries(S.releasing || {})) {
      h("h4", `Chapters of the life · releasing from ${lot === "spirit" ? "Spirit (action, direction)" : lot === "fortune" ? "Fortune (body, circumstance)" : lot}`, null, chapters);
      const today = isoOf(Number(when.value));
      for (const r of rel.periods.filter(r => r.level === 1 && r.begins < S.end)) {
        const c = h("div", null, "chapter" + (r.begins <= today && today < r.ends ? " now" : ""), chapters);
        const top = h("div", null, "top", c);
        h("b", r.sign, null, top);
        h("span", `${r.begins.slice(0, 4)}–${r.ends.slice(0, 4)} · age ${Math.floor((Date.parse(r.begins) - T0) / 3.15576e10)}–${Math.floor((Date.parse(r.ends) - T0) / 3.15576e10)}`, null, top);
        if (r.peak) h("span", "peak " + r.peak, "flag peak", top);
        if (r.note) h("p", r.note, "synth", c);
        teach(c, `${r.sign} chapter`, periodWhy(r), termFor(r), r.note);
      }
    }
  }

  // what's ahead: the year's theme and the windows of the next two years, with the reading's guidance
  function renderComingUp(box) {
    const from = isoOf(Number(when.value));
    const d = new Date(from + "T00:00:00Z"); d.setUTCFullYear(d.getUTCFullYear() + 2);
    const until = d.toISOString().slice(0, 10);
    const items = [];
    for (const y of (S.profections || []).filter(y => y.start === "asc" && y.ends > from && y.begins < until)) {
      items.push({ begins: y.begins, ends: y.ends, title: `Year of the ${ORD(y.place)} place (${y.sign}), lord ${PNAME(y.lord)}`, note: y.note, kind: "year",
        why: `Age ${y.age}: the year's focus is the ${ORD(y.place)} place; ${PNAME(y.lord)} rules the year from the ${ORD(y.lord_place)} place.`, term: "annual_profections" });
    }
    for (const [lot, rel] of Object.entries(S.releasing || {})) {
      for (const r of rel.periods.filter(r => r.level === 2 && r.ends > from && r.begins < until)) {
        const area = lot === "spirit" ? "direction and work" : lot === "fortune" ? "body and circumstance" : lot;
        items.push({ begins: r.begins, ends: r.ends, title: `${r.sign} window for ${area}` + (r.peak ? " · a peak" : "") + (r.loosing ? " · a turning point" : ""),
          note: r.note, kind: r.peak ? "peak" : r.loosing ? "turn" : "window", why: periodWhy(r), term: termFor(r) });
      }
    }
    if (!items.length) return;
    const wrap = h("div", null, "coming", box);
    h("h4", `Coming up · from ${niceDate(from)}`, null, wrap);
    for (const it of items.sort((a, b) => a.begins.localeCompare(b.begins))) {
      const row = h("div", null, "coming-item " + it.kind + (it.begins <= from ? " now" : ""), wrap);
      const top = h("div", null, "top", row);
      h("span", `${niceDate(it.begins)} – ${niceDate(it.ends)}`, "when-range", top);
      h("b", it.title, null, top);
      if (it.note) h("p", it.note, "plain", row);
      teach(row, it.title, it.why, it.term, it.note);
    }
  }

  function renderStudyPlaces(box) {
    for (const pl of S.places) {
      const d = h("div", null, "lot", box);
      const top = h("div", null, "top", d);
      h("b", `${ORD(pl.place)} place`, null, top);
      const lord = S.planets.find(p => p.key === pl.lord);
      h("span", `${pl.sign} · ruler ${lord ? lord.name : "—"}${lord ? ` in the ${ORD(lord.place)}` : ""}`, null, top);
      const tone = h("span", pl.good ? "good" : pl.bad ? "bad" : "", "score", top);
      tone.style.color = pl.good ? "var(--good)" : pl.bad ? "var(--bad)" : "var(--dim)";
      if (pl.note) h("p", pl.note, "synth", d);
      teach(d, `The ${ORD(pl.place)} place`, pl.why, pl.term, pl.note);
      d.addEventListener("mouseenter", () => { if (pl.lord) { focus.planet = pl.lord; applyFocus(); } });
    }
  }

  // the written reading, from a safe Markdown subset (headings, paragraphs, lists, **bold**, *italic*, rules)
  function inline(text, parent) {
    const parts = text.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/);
    for (const part of parts) {
      if (!part) continue;
      if (part.startsWith("**") && part.endsWith("**")) h("strong", part.slice(2, -2), null, parent);
      else if (part.startsWith("*") && part.endsWith("*") && part.length > 2) h("em", part.slice(1, -1), null, parent);
      else parent.append(part);
    }
  }
  function renderReading(box) {
    const article = h("article", null, "reading", box);
    let list = null, para = [];
    const flush = () => { if (para.length) { inline(para.join(" "), h("p", null, null, article)); para = []; } };
    for (const raw of D.reading.text.split("\n")) {
      const line = raw.trimEnd();
      const head = /^(#{1,4})\s+(.*)$/.exec(line), item = /^\s*(?:[-*]|\d+[.)])\s+(.*)$/.exec(line);
      if (!line.trim()) { flush(); list = null; continue; }
      if (/^(-{3,}|\*{3,})$/.test(line.trim())) { flush(); list = null; h("hr", null, null, article); continue; }
      if (head) { flush(); list = null; inline(head[2], h("h" + Math.min(4, head[1].length + 1), null, null, article)); continue; }
      if (item) { flush(); list = list || h(/^\s*\d/.test(line) ? "ol" : "ul", null, null, article); inline(item[1], h("li", null, null, list)); continue; }
      if (list && /^\s{2,}/.test(raw)) { list.lastChild.append(" " + line.trim()); continue; }
      list = null; para.push(line.trim());
    }
    flush();
  }

  function renderStudy() {
    const box = document.getElementById("study");
    box.replaceChildren();
    box.classList.toggle("two-col", state.section === "planets");
    if (state.section === "life") renderLife(box);
    else if (state.section === "planets") renderStudyPlanets(box);
    else if (state.section === "lots") renderStudyLots(box);
    else if (state.section === "places") renderStudyPlaces(box);
    else if (state.section === "time") renderStudyTime(box);
    else if (state.section === "reading") renderReading(box);
  }
  function showSection(name) {
    state.section = name;
    for (const b of document.querySelectorAll("#sections button")) b.setAttribute("aria-selected", String(b.dataset.section === name));
    document.getElementById("aspects-view").hidden = name !== "aspects";
    document.getElementById("study").hidden = name === "aspects";
    if (name !== "aspects") renderStudy();
    applyFocus();
  }

  // ── the life timeline: profections and releasing as lanes, peaks and loosings marked, a date cursor ──
  function drawTimeline() {
    const svg = document.getElementById("tl");
    svg.replaceChildren();
    const lanes = [];
    if (S.profections) lanes.push(["Profections", "prof"]);
    for (const lot of Object.keys(S.releasing || {})) lanes.push([`${lot.charAt(0).toUpperCase() + lot.slice(1)} L1`, lot + ":1"], [`${lot.charAt(0).toUpperCase() + lot.slice(1)} L2`, lot + ":2"]);
    const X0 = 104, X1 = 1188, top = 24, laneH = 36, H = top + lanes.length * laneH + 30;
    svg.setAttribute("viewBox", `0 0 1200 ${H}`);
    const x = iso => X0 + (Date.parse(iso) - T0) / (T1 - T0) * (X1 - X0);
    const y0 = new Date(T0).getUTCFullYear(), y1 = new Date(T1).getUTCFullYear();
    const step = y1 - y0 > 60 ? 10 : 5;
    for (let yr = Math.ceil(y0 / step) * step; yr <= y1; yr += step) {
      const xx = x(`${yr}-01-01`);
      el("line", { x1: xx, x2: xx, y1: top - 8, y2: H - 22, stroke: rgb(theme.ui.dim), "stroke-opacity": ".18" }, svg);
      const t = el("text", { x: xx, y: H - 6, "text-anchor": "middle" }, svg); t.textContent = String(yr);
    }
    const good = new Set(S.places.filter(p => p.good).map(p => p.place));
    lanes.forEach(([label, key], i) => {
      const yy = top + i * laneH;
      const t = el("text", { x: 0, y: yy + 15 }, svg); t.textContent = label;
      const segs = key === "prof"
        ? S.profections.filter(r => r.start === "asc")
        : S.releasing[key.split(":")[0]].periods.filter(r => r.level === Number(key.split(":")[1]));
      for (const r of segs) {
        const a = x(r.begins), b = x(r.ends < S.end ? r.ends : S.end), w = Math.max(1, b - a - 1);
        if (a >= X1) continue;
        let fill, op;
        if (key === "prof") { fill = good.has(r.place) ? rgb(theme.ui.frame) : rgb(theme.ui.dim); op = good.has(r.place) ? .38 : .16; }
        else { fill = rgb(theme.elements[ELEMENTS[SIGNS.indexOf(r.sign) % 4]].header_bg); op = r.peak ? .8 : .3; }
        const seg = el("rect", { x: a, y: yy, width: w, height: 22, rx: 3, fill, "fill-opacity": op, class: "seg" }, svg);
        if (r.note) el("circle", { cx: a + Math.min(w, 8) / 2 + 1, cy: yy + 27, r: 2.6, fill: rgb(theme.ui.text), "pointer-events": "none" }, svg);
        if (key === "prof") teach(seg, `Age ${r.age}: ${ORD(r.place)} place, ${r.sign}`, `Lord of the year ${PNAME(r.lord)}, in the ${ORD(r.lord_place)} place; ${niceDate(r.begins)} – ${niceDate(r.ends)}.`, "annual_profections", r.note);
        else {
          teach(seg, `${r.sign} · level ${r.level}`, periodWhy(r), termFor(r), r.note);
          if (r.level === 1 && w > 50) { const lab = el("text", { x: a + 6, y: yy + 15, "pointer-events": "none" }, svg); lab.textContent = r.sign; lab.style.fill = rgb(r.peak ? theme.ui.page : theme.ui.text); }
          if (r.peak) { const s2 = 3 + (5 - Math.min(4, r.peak)) * 1.6; el("polygon", { points: `${a + w / 2 - s2},${yy - 1} ${a + w / 2},${yy - 1 - s2 * 1.4} ${a + w / 2 + s2},${yy - 1}`, fill: rgb(theme.ui.title), "pointer-events": "none" }, svg); }
          if (r.loosing) el("line", { x1: a, x2: a, y1: yy - 5, y2: yy + 27, stroke: "var(--bad)", "stroke-width": 2.5, "pointer-events": "none" }, svg);
        }
      }
    });
    const cur = el("line", { y1: top - 10, y2: H - 22, stroke: rgb(theme.ui.title), "stroke-width": 2, "pointer-events": "none" }, svg);
    const move = () => {
      const xx = x(isoOf(Number(when.value)));
      cur.setAttribute("x1", xx); cur.setAttribute("x2", xx);
      document.getElementById("when-out").textContent = niceDate(isoOf(Number(when.value)));
    };
    when.addEventListener("input", () => { move(); if (state.section === "time" || state.section === "life") renderStudy(); });
    move();
  }

  if (S) {
    // study pages stack: a smaller wheel, the life timeline, then the reading and findings at full width
    const layout = document.querySelector(".layout");
    layout.classList.add("stacked");
    // the wheel shares its row with the aspect table
    const row = document.createElement("div");
    row.className = "wheel-row";
    const col = layout.querySelector(".wheel-col");
    layout.insertBefore(row, col);
    row.appendChild(col);
    const grid = document.createElement("aside");
    grid.id = "grid"; grid.className = "aspect-grid";
    row.appendChild(grid);
    layout.insertBefore(document.getElementById("timeline"), layout.querySelector(".panel"));
    state.section = S.topics && S.topics.length ? "life" : "planets";  // the interpretation first; the techniques are tabs behind it
    renderSect();
    const sections = document.getElementById("sections");
    sections.hidden = false;
    for (const [key, label] of [["life", "Life"], ["reading", "Reading"], ["planets", "Planets"], ["lots", "Lots"], ["places", "Places"], ["time", "Time lords"], ["aspects", "Aspects"]]) {
      if (key === "life" && !(S.topics && S.topics.length)) continue;
      if (key === "reading" && !D.reading) continue;
      if (key === "lots" && !S.lots.length) continue;
      if (key === "time" && !S.profections && !S.releasing) continue;
      const b = h("button", label, null, sections);
      b.type = "button"; b.dataset.section = key; b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(key === state.section));
      b.addEventListener("click", evt => { evt.stopPropagation(); showSection(key); });
    }
    if (S.profections || S.releasing) {
      document.getElementById("timeline").hidden = false;
      when.max = String(Math.round((T1 - T0) / 864e5));
      const start = D.reading_on ? Date.parse(D.reading_on) : Date.now();
      const today = Math.round((start - T0) / 864e5);
      when.value = String(Math.max(0, Math.min(Number(when.max), today)));
      drawTimeline();
    }
    showSection(state.section);
  }


  // ── the midpoint method switch above the lists, and the strongest harmonics under the slider ──
  function seg(parent, label, options, current, onPick) {
    const g = h("div", null, "seg", parent);
    g.setAttribute("role", "group");
    if (label) h("span", label, null, g);
    for (const [value, text] of options) {
      const b = h("button", text, null, g);
      b.type = "button"; b.setAttribute("aria-pressed", String(value === current));
      b.addEventListener("click", () => {
        g.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
        onPick(value);
      });
    }
    return g;
  }
  if (pack.midpoints && pack.midpoints.aspects.length) {
    const sw = seg(document.getElementById("aspects-view"), "Midpoints", [["new", "new"], ["old", "old"]], state.mid,
                   v => { state.mid = v; renderPanel(); });
    sw.classList.add("mp-seg"); sw.title = "new: the natal angle to the midpoint × H · old: the midpoint inside the harmonic chart";
    document.getElementById("tabs").before(sw);
  }
  const R = D.strongest;
  if (R && HARMONICS.length > 1) {
    const box = document.createElement("section");
    box.className = "strongest"; box.setAttribute("aria-label", "Strongest harmonics");
    document.getElementById("hwrap").after(box);
    const head = h("div", null, "st-head", box);
    h("h2", "Strongest harmonics", null, head);
    seg(head, null, [["new", "new method"], ["old", "old method"]], state.rankBy, v => { state.rankBy = v; drawStrongest(); });
    const bars = h("div", null, "bars", box);
    bars.setAttribute("role", "list");
    bars.style.gridTemplateColumns = `repeat(${R.harmonics.length}, 1fr)`;
    const now = h("p", null, "st-now", box);
    h("p", "Bar height: how much stronger your midpoint structures are than a typical chart's in that harmonic (σ). Click a bar to open it.", "st-note", box);
    const go = n => {
      const i = HARMONICS.indexOf(n);
      if (i < 0) return;
      const slider = document.getElementById("h");
      slider.value = String(i);
      state.h = n; update(450);
    };
    const nm = k => NAME[k] || k;
    drawStrongest = () => {
      const z = r => state.rankBy === "new" ? r.z_new : r.z_old;
      const top = [...R.harmonics].sort((a, b) => z(b) - z(a)).slice(0, 3).map(r => r.harmonic);
      const max = Math.max(1, ...R.harmonics.map(z));
      bars.replaceChildren();
      for (const r of R.harmonics) {
        const b = h("button", null, "bar", bars);
        b.type = "button"; b.setAttribute("role", "listitem");
        if (top.includes(r.harmonic)) b.classList.add("top");
        if (r.harmonic === state.h) b.classList.add("on");
        b.style.setProperty("--v", (Math.max(z(r), 0) / max).toFixed(3));
        b.setAttribute("aria-label", `H${r.harmonic}: ${z(r) >= 0 ? "+" : ""}${z(r).toFixed(1)} sigma`);
        h("i", null, null, b);
        h("span", String(r.harmonic), null, b);
        if (top.includes(r.harmonic)) h("em", `+${z(r).toFixed(1)}σ`, null, b);
        const list = state.rankBy === "new" ? r.new_structures : r.old_structures;
        b.addEventListener("mousemove", evt => showTip(evt, [`H${r.harmonic} · ${z(r) >= 0 ? "+" : ""}${z(r).toFixed(1)}σ above chance`,
          ...list.map(s => `${nm(s.focus)} = ${nm(s.a)}/${nm(s.b)} ${s.strength.toFixed(2)}`)]));
        b.addEventListener("mouseleave", hideTip);
        b.addEventListener("click", () => go(r.harmonic));
      }
      const r = R.harmonics.find(x => x.harmonic === state.h);
      now.replaceChildren();
      if (!r) return;
      h("b", `H${r.harmonic}`, null, now);
      const s = state.rankBy === "new"
        ? ` · ${z(r) >= 0 ? "+" : ""}${z(r).toFixed(1)}σ · midpoints ${r.new.toFixed(2)} (typical ${r.chance_new.toFixed(2)})`
        : ` · ${z(r) >= 0 ? "+" : ""}${z(r).toFixed(1)}σ · midpoints ${r.old.toFixed(2)} (typical ${r.chance_old.toFixed(2)})`;
      now.append(document.createTextNode(s));
      for (const st of (state.rankBy === "new" ? r.new_structures : r.old_structures)) {
        now.append(document.createTextNode(" · "));
        const chip = h("button", `${nm(st.focus)} = ${nm(st.a)}/${nm(st.b)} ${st.strength.toFixed(2)}`, "chip", now);
        chip.type = "button";
        chip.addEventListener("mouseenter", () => { Object.assign(focus, { pair: null, group: [st.focus, st.a, st.b], mid: null }); applyFocus(); });
        chip.addEventListener("mouseleave", () => { Object.assign(focus, { pair: null, group: null, mid: null }); applyFocus(); });
        chip.addEventListener("click", () => { state.tab = st.focus; renderPanel(); });
      }
    };
  }

  // ── title and (for several harmonics) the slider under the wheel ──
  document.getElementById("title").textContent = chart.name || "Chart";
  const m = chart.moment;
  const where = m.place || `${Math.abs(m.lat).toFixed(2)}${m.lat >= 0 ? "N" : "S"} ${Math.abs(m.lon).toFixed(2)}${m.lon >= 0 ? "E" : "W"}`;
  document.getElementById("birth").textContent = [`${m.date} ${m.time}`, m.tz, where].filter(Boolean).join(" · ");
  if (HARMONICS.length > 1) {
    const slider = document.getElementById("h");
    slider.max = String(HARMONICS.length - 1);
    slider.value = "0";
    slider.addEventListener("input", () => { state.h = HARMONICS[Number(slider.value)]; update(450); });
    document.getElementById("hwrap").hidden = false;
  }
  update(0);
})();
