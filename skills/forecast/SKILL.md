---
name: forecast
description: Transits, time lords and forecasting with astrolog-skills — what the current sky (or any date) activates in a natal chart, when transits become exact, and traditional timing (annual profections, lords of the year, the sect light's triplicity lords, zodiacal releasing with peaks and loosing of the bond). Use when the user asks what's happening now, about a date or period, upcoming transits, "when will Saturn…", their profection year, releasing periods, timing, or a forecast.
---

# Forecasts (transits)

`astro --json transits --chart NAME [--on YYYY-MM-DD|now] [--on-time HH:MM] [--days N] [--pack P]`

- `transits`: every transiting body to every natal point and angle within the pack's **transit orbs** (default 2° for
  conjunction/opposition/trine/square, 1° for the rest; a pack can set its own under `[transits]`), with `applying`
  (building) or separating (fading). Tightest first.
- `window` (with `--days N`, up to 730): for each transit, the **exact date** in the window — or, if it perfected just
  before or after, the dates it is in orb. One fast Astrolog run covers all days. The Moon is left out of the window
  (it moves ~13° a day); it appears in the single-date list.
- Transits are cast for your usual location (`astro config set location …`) or the birthplace; they barely change with
  place except the Moon and angles.
- Show the user: `! astro view --chart NAME --transits 2027-03-01` (transiting planets appear in blue in the sign
  boxes, with the transits table below) or `--transits now`.

## Reading a forecast

1. Lead with slow planets (Jupiter → Pluto, Chiron, nodes) to natal personal points and angles: they set the season.
   Then the faster ones as triggers (Sun, Mars, Mercury, Venus) near their exact dates.
2. Interpret with the pack's `meanings.md` (transiting planet's drive × natal point × aspect), following its
   `process.md`. For the vibrational pack, its two steps: find the natal harmonic patterns that fit the question,
   then the transits touching them (full harmonic-transit timelines are a later feature).
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

