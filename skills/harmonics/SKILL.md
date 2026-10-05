---
name: harmonics
description: Harmonic charts and vibrational astrology for one person — which harmonics are strongest (a scan of one chart's harmonics, ranked by its midpoint structures by the new natal-referenced or the classic method, with two-planet aspects), harmonic chart views, and what each harmonic means. Use when the user asks about harmonics, harmonic charts (5th, 7th, 9th…), vibrational astrology, quintiles/septiles/noviles, or "what are my strongest harmonics".
---

# Harmonics (vibrational astrology)

The method, as encoded in the `vibrational` pack (`astro --json packs show vibrational`):
- A harmonic chart multiplies every position by H. Planets **conjunct within 16° in the H chart** (= 16°/H natal) are
  in aspect in that harmonic; oppositions/squares/trines/sextiles inside the H chart are "overtones".
- **Midpoint structures** (a planet on the midpoint of two others) are read two ways — both always available:
  - **new** (the pack's default): the angle from the planet to the midpoint *in the natal chart* × H, read like any
    aspect (3° conjunction, 1.5° opposition, 45′ square…). Each structure has **one strength and its own vibration**
    (the lowest harmonic where it is a conjunction): Moon 20°02′ from Sun/Saturn = 1/18 → "H18, 0.80".
  - **old**: the midpoint inside the harmonic chart, as an axis (conjunction = opposition, 1.5°; others in
    proportion). It can call a conjunction what is really an opposition, and loses structures in higher harmonics.
  - The new method is newly proposed and awaits controlled research: present it as such, with the old alongside.
- **Strongest harmonics**: midpoint strength per harmonic, each structure counted once at its own vibration, measured
  in σ: how much stronger than a typical chart in that same harmonic (2σ or more is rare). It scans the user's chart
  only — "typical" is a fixed per-harmonic yardstick, not other people; comparing groups is the research skill.
  Ranking: `--by new`, `--by old`, `--by groups` or `--by aspects` — use what the user asks for, and say which one
  ranked the list (`by`). Two-planet aspects (the pack's pair score) alongside.
- **Planet groups** (`--by groups`, `z_groups`, `group_list`): 3+ planets all within the pack's pattern orb in the
  harmonic chart, each group's strength × its planet pairs, against random charts (the same yardstick in every
  harmonic). This is how high harmonics are scored: the rare 4-planet groups in H100–H360.
  - Above 360 ÷ the new method's orb (H120 at 3°) the new method finds nothing, by arithmetic: every angle is within
    the orb of a conjunction in some lower harmonic, so every structure already has its own harmonic. A range beyond
    that ranks by groups by default (`default_by`); say why if asked.
  - Read each group's flags: `exact_time` (it holds the Moon, and the birth time must be right within
    `moon_minutes` — say so; a rounded time can't support it) and `generational` (mostly Uranus–Pluto: shared by
    everyone born that year or decade — what's personal is the faster planets that join it).
- Harmonics 1–32 are well understood; up to 180 are supported. Meanings are in the pack's `meanings.md`.
- Open questions and assumptions: the pack's `REVIEW.md` — mention them when they affect an answer.

## Commands (read `--json` yourself)

- Strongest harmonics: `astro --json harmonics --chart NAME [--harmonics 1-32|1,5,7,18] [--by new|old|groups|aspects]
  [--orb-base 4]` → `harmonics` (each with `z_new`, `z_old`, `new`, `old`, chance, `aspects`, top structures),
  `ranked`, and `structures` (the strongest, each at its own vibration with the old method's strength alongside).
- One harmonic in detail: `astro --json harmonics --chart NAME --harmonic 17` → its aspects and its midpoints by
  both methods (a structure shown in another harmonic names its own `vibration`).
- Planet groups in one harmonic (3+ planets together): `astro --json patterns --chart NAME --pack vibrational -H 7`
- Aspects inside a harmonic chart: `astro --json aspects --chart NAME --pack vibrational -H 7`
- Show the user: `! astro harmonics --chart NAME` (bars + ranking), `! astro view --chart NAME --harmonic 17
  --pack vibrational --show chart,aspects [--midpoints old]`, or the HTML page (`astro export html --chart NAME
  --pack vibrational --harmonics 1-32`): the strongest harmonics as bars under the slider, a midpoint method switch (hidden at H1, where both methods measure the same angle and the classic one is used).

## Reading it

1. Lead with the harmonics well above chance (2σ+), then 1–2σ; say plainly when nothing stands out — a real answer.
2. For each, its strongest midpoint structures in plain words ("the Sun sits at the balance point of Venus and Pluto,
   in the 17th harmonic"), with the harmonic's quality from `meanings.md` and the planets' meanings; then its
   tightest two-planet aspects. Where the old and new methods disagree, say so.
3. Name the structure's natal angle when it helps ("Venus is 3/23 of the circle from the Mercury/Mars midpoint").
4. Birth-time precision matters more in high harmonics (the Ascendant moves ~1° per 4 minutes; in H32 that's 32°);
   check the chart's Rodden rating (`astro --json chart show NAME` → `record.rating`) before leaning on H > 16.
