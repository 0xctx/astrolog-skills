# Hellenistic — open questions

Where the tradition's texts disagree or leave a rule open: the default this pack uses, and the alternatives. Decide
any of them and the pack changes in one line (copy the pack first: `astro packs copy hellenistic`). Nothing here is
presented as settled.

## Chart settings
- **Zodiac, houses, planets** — tropical zodiac, whole-sign houses, the seven visible planets and the nodes. Change
  them per command (`astro --houses … --zodiac …`) or for good (`astro packs settings hellenistic`).
- **Node** — the mean node; the tradition doesn't settle true or mean.

## Sect and planets
- **Mercury's sect** — default: morning star diurnal, evening star nocturnal. Alternatives: the sect of the ruler of
  its bounds; with the Sun by day and the Moon by night; neutral.
- **Mercury as benefic or malefic** — it takes on the role of what it is closely joined to; not computed.
- **The luminaries** — neutral here; some texts count them as benefic.
- **Twilight** — the chart turns diurnal exactly at the horizon; a span below it is debated.
- **Rejoicing by sign** — default by gender; alternatives by the Leo–Capricorn half, or by the sign's ruler.
- **Planetary gender** — not used in calculations; Saturn is feminine in one lineage.

## Signs and dignities
- **Exaltation degrees** — Saturn 21° (also given as 20°), Venus 27° (also 26°); whole signs are what counts here.
- **Adversity** — counted as bad testimony; only later texts define it as harmful.
- **Triplicity rulers** — the common scheme; another ancient scheme differs; Mercury's possible share in earth is
  unused.
- **Triplicity as testimony** — not counted good or bad: treated as rulership, not as a dignity score.
- **Bounds** — the Egyptian set; another ancient set is an alternative.
- **Twelfth-parts** — multiplier 12; 13 is a variant.
- **Proper face** — computed (same sign relation to the Sun or Moon as in the domiciles) and counted as good
  testimony; texts sometimes confuse it with a planet's own decan.

## Solar phase
- **In the heart** — within 1°, a minority view; a later 16′ variant exists.
- **Additive and subtractive** — read as speed against average motion; some texts mean direct and retrograde.
- **Stations** — no numeric threshold is agreed, so not flagged (`[phase] stationary_ratio` turns it on with a value
  you choose).

## Configurations and conditions
- **Orbs** — the aspect lists use 3° (the applying range); the doctrine works by sign and by its own ranges.
- **Assembly** (an applying conjunction beyond 3° and within 15°, in the same sign here) — shown, not scored.
- **Running in the void** — the Moon completes no exact aspect within its next 30° (speeds as at birth); counted as
  bad testimony for the Moon. Only the Moon, as in the texts.
- **Mercury's role** — by association: planets in its sign, aspects within 3° (the range of the closest
  configurations), and its sign's ruler; "mixed" when benefics and malefics both apply. Shown, not used to change
  which conditions Mercury causes.
- **Overcoming by sextile** — whether a benefic's superior sextile bonifies is uncertain; left out.
- **Bonifying trine** — taken as a superior trine; an inferior one would also count by the looser reading.
- **Counteraction places** — 6 and 12 here; a later view counts all bad places (2, 6, 8, 12).
- **Enclosure** — rays within 7° each side, and 7° for bodies; sign boundaries uncertain.
- **Containment** (by sign) — computed: one planet's sextile, square, trine or opposition rays on both neighbouring
  signs, and no other planet configured to the contained one (copresence counts as interposing here). A benefic
  containment helping is by analogy; the texts give only the harmful example.
- **Adherence direction** — the planet applies to the malefic or benefic; the other reading has the malefic applying.
- **Striking with a ray** — the benefic's sextile counted (the texts are tentative); within 3° either side.
- **Engagement by opposition with a benefic** — not counted as bonification.

## Places
- **Busy places** — angles and succedents; another approach counts 1, 4, 5, 7, 9, 10, 11 as advantageous.
- **The third place** — good here; some texts rank it below the second.
- **Joys** — the common scheme; one early text puts Venus in the 10th and Saturn in the 4th.

## Lots
- **Fortune** — reversed by night; alternatives: never reversed, or reversed only with the Moon above the horizon.
- **Eros and Necessity** — default between Fortune and Spirit (`from_lots`); another version uses Venus and Mercury
  (`from_planets`).
- **Father** — reversed by night, with the Mars–Jupiter fallback when Saturn is under the beams; some don't reverse.
- **Siblings** — not reversed (one lineage); the other reverses by night.
- **Marriage** — Saturn to Venus for men, Venus to Saturn for women (charts record sex with `--sex`); left out
  when it isn't recorded. Other versions (by day and night; the Lot of the Husband) are listed as variants.
- **Children** — the version not reversed by night; other gendered versions exist.
- **Exaltation** — measured to the start of the exaltation sign; whether to the exaltation degree is open.

## Timing
- **Profections: planet or ruler** — planets in the profected sign and the sign's ruler are both activated; some texts
  let the planet in the sign take over, others the ruler alone.
- **Profection starting points** — the Hour-Marker, the sect light and the other light; any planet, place or lot can
  be profected for a topic.
- **The second triplicity lord's changeover** — two candidates are shown, not chosen: the second lord's minor years,
  or the ascensional time of its sign at the birth latitude.
- **Transits** — ingresses and sign-based configurations of the time lords, ingresses into the profected sign, and
  exact hits by the lords (the Moon left out).
- **Releasing levels 3-4** — computed (each one twelfth of the level above); levels 1-2 carry most of the weight.
- **Peak ranking** — the 1st and 10th from Fortune strongest, then the 7th, then the 4th.
- **Good and difficult periods** — the angles of the benefic of the sect and the malefic contrary to it, and the
  ranking of planets' power over a sign, are modern practice rather than ancient rule.
- **Releasing from other lots** — only Spirit and Fortune.
- **The general period's ruler** — subperiods in the sign holding it are flagged (`holds_ruler`): modern practice,
  not ancient rule.
- **Monthly and daily profections** — the texts mention them, but no counting rule is given here; not computed.
- **Quadrant houses** — each planet's Porphyry quadrant house is shown for information; how quadrant positions
  energise planets varies between texts, so they don't count as testimony.
