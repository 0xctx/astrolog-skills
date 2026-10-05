# Open questions — vibrational pack

Items to check against the sources before relying on them. Edit or delete lines as you resolve them.

- **Typo in the source, formula used instead.** *The First 32 Harmonics* says "the orb for the 5th harmonic aspects is
  5 1/3 degrees", but its own rule (16° ÷ harmonic) gives 3.2°; 5⅓° is H3. `method.toml` uses the formula.
- **Saturn–Pluto weight not stated.** Analysis 2 lists Jupiter–Saturn and Jupiter/Saturn–Uranus/Neptune as 3 and
  Jupiter–Pluto as 2, but not Saturn–Pluto. Assumed **3** (same family as Saturn's other outer pairs).
- **Midpoint structures are scored separately from the pattern scores.** `astro harmonics` ranks harmonics by
  midpoint strength (see the last section); score 1 and score 2, which the research sweeps use, still count planets
  only.
- **Midpoint orbs are in the harmonic chart.** Old method: 1.5° for conjunction and opposition, the others in
  proportion; new method: 3° conjunction, the others in proportion (the 2026 source). At H7 the old 1.5° is 0°13′
  natal.
- **Lower-harmonic exclusion is off.** An option some harmonic software offers: excluding pairs that are conjunct in a harmonic only because they
  are already conjunct in a lower harmonic that divides it (e.g. quintiles when looking at H10). Set
  `harmonics.exclude_lower = true` to use it; the study's first analysis didn't exclude them.
- **Derived harmonic meanings need your confirmation.** `meanings.md` marks H1–H4 as standard harmonic theory and
  H6, H10, H12, H14–H16, H18, H20–H22, H24–H28, H30, H32 as *derived* from prime factors. The cited sources name
  H5, H7, H8, H9, H11, H13, H17, H19, H23, H29 and H31. Replace derived lines with wording from your own source
  material when you have it (copy the pack first: `astro packs copy vibrational`).

## Midpoint structures: old or new method
- **Default: the new method** (the angle to the midpoint measured in the natal chart, × H), as its proposer expects
  it to replace the old one; the old method (the midpoint inside the harmonic chart, as an axis) stays one switch
  away everywhere. Both need controlled research before either is preferred on evidence.
- **Conjunction orb 3°** for the new method; 4° (the square root of the 16° planet orb) picks up the weakest
  structures (`astro harmonics --orb-base 4`).
- **Strongest harmonics** are ranked by midpoint strength above random charts (400, fixed seed) — the toolkit's
  construction, so that harmonics with many possible structures don't win by numbers alone. **Planet groups** (3+
  planets within the pattern orb in a harmonic chart) are scored the same way, each group weighted by its planet
  pairs: the toolkit's construction for the high harmonics, where the new midpoint method has nothing left to count.
