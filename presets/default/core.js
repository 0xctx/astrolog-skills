/* astrolog-skills chart maths for the browser — mirrors the Python engine (tested for parity in Node). Pure. */
(function (root) {
  "use strict";
  const ANGLES = ["asc", "mc"];

  function norm(x) { return ((x % 360) + 360) % 360; }
  function sep(a, b) { const d = Math.abs(a - b) % 360; return Math.min(d, 360 - d); }
  function harmonicLon(lon, h) { return norm(lon * h); }

  /** Bodies of a chart (optionally in harmonic h): [{key, lon, speed}] including the angles (speed null). */
  function bodies(chart, h) {
    const out = chart.points.map(p => ({ key: p.key, lon: harmonicLon(p.lon, h), speed: p.speed * h }));
    for (const k of ANGLES) if (k in chart.angles) out.push({ key: k, lon: harmonicLon(chart.angles[k], h), speed: null });
    return out;
  }

  function applying(a, b, angle) {
    const step = 0.01;
    const now = Math.abs(sep(a.lon, b.lon) - angle);
    const later = Math.abs(sep(a.lon + a.speed * step, b.lon + b.speed * step) - angle);
    return later < now;
  }

  /** Aspects by the pack's rules: natal aspect set at h = 1, overtone orbs inside a harmonic chart. */
  function aspects(chart, pack, h) {
    const types = h > 1 ? pack.harmonic_chart : pack.aspects;
    const list = bodies(chart, h);
    const found = [];
    for (let i = 0; i < list.length; i++) {
      for (let j = i + 1; j < list.length; j++) {
        const a = list[i], b = list[j];
        const pair = new Set([a.key, b.key]);
        if (pair.has("north_node") && pair.has("south_node")) continue;
        if (ANGLES.includes(a.key) && ANGLES.includes(b.key)) continue;
        const s = sep(a.lon, b.lon);
        let best = null;
        for (const t of types) {
          const orb = Math.abs(s - t.angle);
          if (orb <= t.orb && (best === null || orb / t.orb < best.orb / best.limit)) {
            best = {
              a: a.key, b: b.key, aspect: t.key, name: t.name, family: t.family, glyph: t.glyph, angle: t.angle,
              orb, limit: t.orb, strength: t.orb ? 1 - orb / t.orb : 1,
              applying: a.speed === null || b.speed === null ? null : applying(a, b, t.angle),
            };
          }
        }
        if (best) found.push(best);
      }
    }
    return found.sort((x, y) => y.strength - x.strength);
  }

  /** Maximal cliques (Bron–Kerbosch with pivoting) of bodies all within `orb`; groups of at least minSize. */
  function patterns(lons, orb, minSize) {
    const keys = Object.keys(lons);
    const adj = {};
    for (const k of keys) adj[k] = new Set(keys.filter(j => j !== k && sep(lons[k], lons[j]) <= orb));
    const cliques = [];
    (function expand(r, p, x) {
      if (p.size === 0 && x.size === 0) { cliques.push(r); return; }
      let pivot = null, best = -1;
      for (const v of [...p, ...x]) { const n = [...adj[v]].filter(u => p.has(u)).length; if (n > best) { best = n; pivot = v; } }
      for (const v of [...p].filter(u => !adj[pivot].has(u))) {
        expand(new Set([...r, v]), new Set([...p].filter(u => adj[v].has(u))), new Set([...x].filter(u => adj[v].has(u))));
        p.delete(v); x.add(v);
      }
    })(new Set(), new Set(keys), new Set());
    return cliques.filter(c => c.size >= minSize).map(c => {
      const members = keys.filter(k => c.has(k));
      let span = 0;
      for (let i = 0; i < members.length; i++) for (let j = i + 1; j < members.length; j++) span = Math.max(span, sep(lons[members[i]], lons[members[j]]));
      return { bodies: members, span, strength: 1 - span / orb };
    }).sort((a, b) => b.bodies.length - a.bodies.length || a.span - b.span);
  }

  function combos(arr, k) {
    const out = [];
    (function go(start, acc) {
      if (acc.length === k) { out.push(acc.slice()); return; }
      for (let i = start; i < arr.length; i++) { acc.push(arr[i]); go(i + 1, acc); acc.pop(); }
    })(0, []);
    return out;
  }

  /** The pack's pattern scores for harmonic h: patterns, score1 (4-body patterns), score2 (weights × tightness). */
  function score(chart, pack, h) {
    const rule = pack.patterns;
    const lons = {};
    for (const p of chart.points) if (rule.bodies.includes(p.key)) lons[p.key] = harmonicLon(p.lon, h);
    const pats = patterns(lons, rule.orb, rule.min_size);
    const quads = new Set();
    for (const pat of pats) if (pat.bodies.length >= rule.strong_size) for (const q of combos(pat.bodies, rule.strong_size)) quads.add(q.join("|"));
    let score2 = 0;
    const keys = Object.keys(lons);
    for (let i = 0; i < keys.length; i++) {
      for (let j = i + 1; j < keys.length; j++) {
        const s = sep(lons[keys[i]], lons[keys[j]]);
        if (s <= rule.orb) score2 += (rule.weights[keys[i] + "|" + keys[j]] ?? rule.weights[keys[j] + "|" + keys[i]] ?? 1) * (1 - s / rule.orb);
      }
    }
    return { harmonic: h, patterns: pats, score1: quads.size, score2 };
  }

  /** The midpoint on the shorter arc between two longitudes. */
  function midpoint(a, b) {
    const diff = norm(b - a + 180) - 180;
    return norm(a + diff / 2);
  }

  /** The orb a midpoint aspect is allowed in the harmonic chart: old — `orb` for conjunction/opposition, the others
   *  in proportion (orb × 2 ÷ the aspect's harmonic); new — `new_orb` ÷ the aspect's harmonic. */
  function midpointLimit(t, how, mp) {
    if (how === "new") return mp.new_orb / t.harmonic;
    return t.harmonic <= 2 ? mp.orb : mp.orb * 2 / t.harmonic;
  }

  /** The lowest harmonic (up to `highest`) in which a natal angle is a conjunction within `orb`. */
  function vibration(x, orb, highest) {
    for (let n = 1; n <= highest; n++) { const y = norm(x * n); if (Math.min(y, 360 - y) <= orb) return n; }
    return null;
  }

  /** For every body (South Node left out — it repeats the North Node), the midpoints it contacts in harmonic h,
   *  strongest first. old: the midpoint inside the harmonic chart, read as an axis; new: the natal angle from the body
   *  to the midpoint × h, read as any aspect, with the structure's own vibration. Mirrors analysis/midpoints.py. */
  function midpointContacts(chart, pack, h, how) {
    const mp = pack.midpoints;
    how = how || (h === 1 ? "old" : mp.method || "old");  // at H1 both measure the same angle
    const natal = bodies(chart, 1).filter(b => b.key !== "south_node");
    const pos = Object.fromEntries((how === "old" ? bodies(chart, h) : natal).map(b => [b.key, b.lon]));
    const keys = natal.map(b => b.key), has = new Set(mp.aspects.map(t => t.key));
    const found = {};
    for (const f of keys) {
      const hits = [];
      const others = keys.filter(k => k !== f);
      for (let i = 0; i < others.length; i++) for (let j = i + 1; j < others.length; j++) {
        const a = others[i], b = others[j];
        const mid = midpoint(pos[a], pos[b]);
        let d, x = null;
        if (how === "old") d = sep(pos[f], mid);
        else { x = sep(pos[f], mid); const y = norm(x * h); d = Math.min(y, 360 - y); }
        let best = null;
        for (const t of mp.aspects) {
          let orb, key = t.key;
          if (how === "old" && t.harmonic <= 2) {
            orb = Math.min(d, 180 - d);
            key = d < 90 ? "conjunction" : "opposition";
            if (!has.has(key)) key = t.key;
          } else orb = Math.abs(d - t.angle);
          const limit = midpointLimit(t, how, mp);
          if (orb <= limit && (best === null || 1 - orb / limit > best.strength ||
                               (1 - orb / limit === best.strength && orb < best.orb))) {
            const tt = mp.aspects.find(z => z.key === key) || t;
            best = { focus: f, a, b, aspect: key, glyph: tt.glyph, family: tt.family, name: tt.name, midpoint: mid,
                     orb, limit, strength: 1 - orb / limit, method: how, natal_angle: x,
                     vibration: x === null ? null : vibration(x, mp.new_orb, mp.highest || 180) };
          }
        }
        if (best) hits.push(best);
      }
      found[f] = hits.sort((p, q) => q.strength - p.strength || p.orb - q.orb);
    }
    return found;
  }

  const api = { norm, sep, harmonicLon, bodies, aspects, patterns, score, midpoint, midpointContacts, vibration };
  root.AstroCore = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
