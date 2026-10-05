---
name: forecast
description: Transits, transit timelines, harmonic transit charts and patterns, time lords and forecasting with astrolog-skills — what the current sky (or any date) activates in a natal chart, a timeline of every transit to natal planets and midpoints with the harmonic each aspect belongs to, when transits become exact, and traditional timing (annual profections, lords of the year, the sect light's triplicity lords, zodiacal releasing with peaks and loosing of the bond). Use when the user asks what's happening now, about a date or period, upcoming transits, "when will Saturn…", their profection year, releasing periods, timing, or a forecast.
---

# Forecasts (transits)

`astro --json transits --chart NAME [--on YYYY-MM-DD|now] [--on-time HH:MM] [--days N] [--pack P]`
`  [--transiting saturn,ceres] [--natal sun,moon,asc] [--aspects septile,h9] [--no-midpoints] [--harmonics 1-32]`

- `transits`: every transiting body to every natal point and angle on the date, within the pack's **transit orbs**
  (a pack sets them under `[transits]`), with `applying` (building) or separating. Tightest first.
- `timeline` (with `--days N`, up to 730) — a transit timeline, Sirius style:
  - `passages`: each stretch a transit is in orb — to natal planets and angles (the pack's transit aspects and orbs)
    and to natal midpoints (the pack's midpoint aspects and orbs) — with `enters`, `leaves`, **every** `exact` date
    (a retrograde transit has several) and the aspect's `harmonic` (septile 7, novile 9, square 4…). Slowest
    transiting body first, then planets before midpoints, then by date. `passages_total` counts them all; `--limit`
    (default 400, 0 = all) caps the list.
  - `active`: how many transits each harmonic has in orb on the first day — the harmonics being activated.
  - `patterns`: harmonic transit patterns — a transiting body joining two or more natal bodies all within the pack's
    pattern orb in harmonic chart H (e.g. transiting Saturn on a natal Venus–Mars septile: an H7 pattern), with dates
    and the tightest day; strongest (most bodies, tightest) first. Searched over the pack's harmonic range unless
    `--harmonics` names others.
  - Defaults are the chart's and the pack's: its bodies (add asteroids with `--points +ceres,+pallas,+juno,+vesta`),
    transit aspects, midpoint rules and pattern rules. The Moon doesn't transit in the timeline (daily steps).
- Transits are cast for your usual location (`astro config set location …`) or the birthplace.
- Show the user: `! astro transits --chart NAME --days 90` (the timeline: a bar per transit, ◆ on each exact day,
  under a header per transiting planet, then the harmonic patterns with their strength), and a harmonic transit chart on a pattern's day:
  `! astro view --chart NAME --harmonic 7 --transits DATE` (natal and transiting planets both × 7, transits in blue,
  with that chart's transits below). An HTML page with both: the export skill (`--transits DATE --days N`).

## Reading a forecast

1. Lead with slow planets (Jupiter → Pluto, Chiron, nodes) to natal personal points and angles: they set the season.
   Then the faster ones as triggers (Sun, Mars, Mercury, Venus) near their exact dates.
2. Interpret with the pack's `meanings.md` (transiting planet's drive × natal point × aspect), following its
   `process.md`. For the vibrational pack, its two steps: find the natal harmonic patterns that fit the question,
   then the transits touching them: the timeline's rows in those harmonics (`--aspects h7`) and its harmonic
   patterns, each looked at in its harmonic transit chart.
3. Give dates and orbs; applying = building, separating = integrating.
4. Tendencies and timing windows, never certainties; no medical, legal, financial or death predictions.

## Time lords (a pack with [timing] rules, e.g. --pack hellenistic)

- `astro --json timing profections --chart NAME [--on DATE | --age N] [--years K]` — the year's sign, place, lord,
  the lord's place, and natal planets in the sign, from each starting point the pack lists.
- `astro --json timing lords --chart NAME` — the sect light's triplicity lords (first, second, cooperating) with their
  place and the pack's verdict, and the candidate years when the second takes over.
- `astro --json timing transits --chart NAME [--from DATE] [--days N≤730]` — only transits that involve the time
  lords: their sign ingresses (with the natal points the new sign sees), ingresses into the profected sign, and exact
  hits by the lords.
- `astro --json timing releasing --chart NAME [--lot spirit|fortune] [--on DATE | --from DATE --to DATE] [--level 1–4]`
  — periods with their sign, lord, place from Fortune, peak rank, triad position, loosing of the bond, completion,
  planets in the sign or squaring/opposing it, and the benefic/malefic angles.
- `astro --json timing search --chart NAME --what peak|loosing|completion|place:N [--from --to]`.

Read them as the pack's `process.md` says (profections first, then releasing; transits only through the time lords),
keep every date exactly as the tool gives it, and cite the pack's pages only when citations are on (see the report
skill).

### A traditional forecast (time lords), step by step

1. `astro --json report-data --chart NAME --pack P --on DATE --transits-days 365` — the year's profections (from the
   Ascendant and the lights), the releasing periods on the date, the next peaks and loosings, and the time lords'
   transits, with `study` for each lord's natal condition.
2. Write it for the person, in plain language (the report skill's **Voice** rules): what each period is likely to
   bring in work, money, relationships, health and energy, with dates, and what to do with it; techniques only in a
   short "How the chart shows this" line. Read it as `process.md` says: the profected place and its topics, the lord of the year and its natal condition
   (what it promised is what the year delivers), planets in the profected sign, then releasing (Spirit for direction
   and career, Fortune for body and health: peaks, loosing of the bond, the period's sign and the planets in or
   squaring it), then the lords' transits by date. Search the pack's books for depth (pages only when citations are on).
3. Write notes for the year and the running periods (`profection:…`, `releasing:…` keys from
   `astro --json notes keys … --on DATE`) so the chart's timeline shows them, and save the forecast next to the
   reading (`export_path` with "forecast" in the name).

