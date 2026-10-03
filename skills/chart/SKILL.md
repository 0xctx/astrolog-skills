---
name: chart
description: Calculate and show astrology charts with astrolog-skills — natal or event charts from saved charts, birth data or places; harmonic charts; aspects and midpoint trees, aspect grids, element/mode balance, planet patterns and positions; zodiac, ayanamsa, house system and theme choices. Use when the user asks for a chart, horoscope, birth chart, natal chart, "my chart", a harmonic chart, aspects, where planets are, or to save someone's birth data.
---

# Charts

The toolkit command is `astro` (if not found: the plugin's `bin/astro`, `${CLAUDE_PLUGIN_ROOT}/bin/astro` in Claude
Code). Read `--json` yourself; give the user a `! astro view …` command to see the colour view (in agents without
the `!` prefix, they run it without the `!` in their own terminal). Never paste ANSI output into the chat.

## Getting the birth data right

- Saved charts: `astro --json chart list`. Use `--chart NAME` everywhere once saved.
- New person: ask for **date, time (with am/pm or 24h) and birthplace**, and how reliable the time is (birth
  certificate ≈ Rodden AA, memory ≈ A/B). Then save it:
  `astro --json chart add "Name" --date YYYY-MM-DD --time HH:MM --place "City, Country" [--rating AA] [--tag client]
  [--sex male|female]` (sex only matters for a few traditional lots, e.g. Marriage)
  - The place supplies coordinates and the historically correct time zone (daylight saving, and local mean time
    before standard time). Relay any `notes` it returns.
  - Ambiguous place → the error lists candidates; ask the user which one (don't guess).
  - "Time didn't exist" (daylight-saving gap) → ask them to double-check the time; don't silently shift it.
  - Dates before 15 Oct 1582 are read as Julian calendar (as historical records are).
- One-off chart without saving: `astro --json cast --date … --time … --place "…"`; the sky now: `--now`.

## Showing it

`! astro view --chart NAME` — the chart: twelve sign boxes around a centre panel (rising sign at the left, then
counter-clockwise; box headers show which house cusps begin in each sign). Add views as asked:

| Ask | Add |
|---|---|
| aspects & midpoints | `--show chart,aspects` — a tree per planet, midpoint-tree style: its aspects to other planets, then the midpoints it sits on or aspects (☌ ☍ □ by default; the pack's `[midpoints]`), each tightest first. In harmonic charts orbs show as measured in that chart; `astro config set display.orbs natal` shows them ÷ H instead. Under `!` a long list comes in pages: the output ends with the exact `--show aspects:2` to run next (a real terminal gets everything at once) |
| aspect grid | `--show grid` (the triangular table; brighter = tighter orb) |
| doctrine (packs with doctrine rules, e.g. hellenistic) | `--show doctrine` — the sect line (most helpful → most difficult planet), then each planet: position and place, its findings (good in green, bad in red), and every bonification or maltreatment with who, how, orb and reception; `--show lots` — each lot with its lord and the checklist balance; `--show timelords` — profection years, current releasing periods, next peaks and loosings, the sect light's lords (on the `--transits` date, else today) |
| elements / modes / balance | `--show balance` |
| patterns, stelliums, vibrational groups | `--show patterns` (use `--pack vibrational` for the vibrational tradition's rules) |
| a table of positions | `--show positions` |
| everything | `--show all` (if it doesn't fit, the output says which views to show separately) |
| harmonic chart (e.g. 7th) | `--harmonic 7` (with `--pack vibrational` for vibrational astrology) |

Other options: `--profile vedic-lahiri` (sidereal Lahiri, whole-sign), `--theme NAME`, `--letters` (if their font
shows boxes for ⚺⚻⚼), global `--width 120` for wide terminals.

## Reading the data yourself

- `astro --json view --chart NAME --show chart,aspects` → the chart model plus the aspects, midpoint contacts and patterns behind the
  views. Positions are exact (arc-seconds); speeds < 0 are retrograde.
- `astro --json aspects --chart NAME` and `astro --json patterns --chart NAME --range 1-32` for analysis.
- For interpretation, use the `report` skill (it follows the pack's `process.md` and `meanings.md`).

## Settings the user may ask to change

- Zodiac / ayanamsa / house system / points come in layers: the active profile → the pack's `[chart]` (a tradition's
  own settings, used whenever that pack is) → the user's saved adjustments for that pack → this command's flags.
  - **Try once:** global flags before the command: `astro --houses placidus --zodiac lahiri --points +ceres,-pluto
    view --chart NAME --pack P` (`--points a,b,c` replaces the list; `+x` adds, `-x` drops; `--node true|mean`).
  - **Keep for a tradition:** `astro packs settings P --houses placidus` (also `--zodiac`, `--node`, `--points`);
    `astro --json packs settings P` shows the pack's settings, the user's and the result; `--reset` undoes.
  - **Everywhere:** profiles — `astro --json profile list`, `astro profile use NAME`, or
    `astro profile new NAME --from default` and edit the TOML. `--profile NAME` on a command means exactly that
    profile (the pack's and saved settings are skipped; flags still apply).
  - Ayanamsas: lahiri, krishnamurti, raman, fagan-bradley, yukteshwar, deluce, djwhal-khul, usha-shasi,
    galactic-center, or a number. A pack with doctrine always needs the seven planets.
  - Traditional doctrine (e.g. Hellenistic places) follows the pack's own rules — whole-sign places stay whole-sign
    whatever house system the wheel shows; the zodiac and ayanamsa change every position.
- Colours → `astro theme copy default --as mine`, edit, `astro theme use mine`.
- Anything Astrolog can do that isn't covered: `astro raw --chart NAME -- <astrolog switches>` (the profile's
  settings are applied first; the user's switches win).
