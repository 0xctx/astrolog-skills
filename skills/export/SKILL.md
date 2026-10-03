---
name: export
description: Export astrology charts from astrolog-skills as beautiful, self-contained interactive HTML — a minimal page with a circular wheel (one chart, or a slider through a chosen range or series of harmonics) and per-planet aspect & midpoint trees — that works offline and can be emailed or shared. Use when the user wants a chart to save, share, print, send to a client, open in a browser, or see as a proper round wheel.
---

# HTML charts

`astro --json export html --chart NAME [--harmonic H | --harmonics SPEC] [--pack P] [--profile P] [--theme T] [--out PATH]`

- **Which harmonics:** `--harmonic 7` → a single H7 chart (no slider). `--harmonics 1-12` → a slider through that range;
  `--harmonics 1,5,7,11` or `1-12,16,20` → a slider through exactly that series. Neither → the pack's harmonic range
  (psychological H1–12, vibrational H1–32). Use `--harmonic 1` for just the natal chart.

- Writes one `.html` file (default `~/.astrolog-skills/exports/<name>.html`; `-h7`, `-h1-12` or `-h1_5_7` when harmonics are chosen). Everything is
  inside the file — no internet needed, safe to email. Give the user the path and how to open it
  (`xdg-open`, `open` on macOS, `start` on Windows); don't open it for them unless asked.
- The page is deliberately minimal: the chart's name, the circular wheel (rising sign at the left, house cusps, aspect
  lines coloured by family, brighter/thicker when tighter), a harmonic slider under the wheel only when several
  harmonics were chosen, and, beside it, a panel with a tab per planet (plus AC/MC) listing its aspects then midpoints; picking a tab or clicking a planet lights its aspect lines. Hover planets and aspect
  lines for details; it prints cleanly.
- **Hover text:** by default hovering a row shows just the contact ("Mercury conjunction Saturn"). With `--interp`,
  it adds a snippet of the person's written reading when one exists (`~/.astrolog-skills/notes/<name>-<pack>.json`,
  written by the `report` skill; `--notes FILE` for another); contacts without a note still show only the title.
  Offer to write a reading first if the user wants interpretations.
- **Study panels (packs with doctrine rules):** the page opens on *Planets*, with tabs for *Aspects*, *Lots* and *Time
  lords*, a sect line under the title and a life timeline (profections, releasing, peaks, loosings) with a date slider.
  Every finding teaches on hover, focus or tap: why it holds in this chart (with the real degrees), the pack's own
  glossary entry (`## Glossary` in its `meanings.md`) and the pages to read. Pointing at a planet dims the signs in
  aversion to it and draws who bonifies (green) or maltreats (red) it.
- Everything uses the chart's profile (zodiac, houses, points) and the tradition pack's rules (`--pack vibrational`
  for vibrational harmonics), with the terminal theme's colours.
- For a client: pair it with a written reading from the `report` skill.
- Custom designs: copy the plugin's `presets/default` (`${CLAUDE_PLUGIN_ROOT}/presets/default` in Claude Code) to
  `~/.astrolog-skills/presets/<name>/`, edit `style.css` (colours, fonts, layout) or the others, then
  `--preset <name>`. Keep all resources inline — no links to
  web fonts or scripts.
