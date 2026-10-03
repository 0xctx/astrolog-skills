# Hellenistic — reading process

The order a natal reading follows. Every number comes from `astro --json doctrine --chart NAME --pack hellenistic`
(and `astro --json report-data` for positions). Nothing outside the pack's rules is asserted as Hellenistic
doctrine.

## Natal reading

1. **Sect.** Day or night chart (the Sun above or below the exact horizon); the sect light; the benefic and malefic
   of the sect and the two contrary to it. Name the most helpful and the most difficult planet. Rejoicing only as a
   secondary note.
2. **The rising sign and its lord.** The lord of the Hour-Marker steers the life: which place it sits in (where the
   life is directed), whether it is configured to the rising sign, which planets witness it, whether it is under the
   beams, and its sect.
3. **Each planet's condition.** Place (angular, succedent, declining; good or bad), dignities, solar phase, then
   every bonification and maltreatment with who does it, how, and the actor's sect; note reception. Summarise with
   the pack's good and bad testimonies — never as a single score. Note proper face, assembly,
   containment, a declining planet made busy by an angle's degree, the Moon running in the void (an unfavourable
   sign), and Mercury's role by association.
4. **Topics by place.** For each topic the native asks about: the place, the planets in it, then its ruler —
   and where the Midheaven or IC degree falls outside the 10th or 4th, that place too for work or home —
   the ruler's place joined with the place it rules, good or bad place, and its condition.
5. **Lots.** Fortune and Spirit first, then the lot for the topic: its sign, its place, planets configured to it or
   in aversion, and its lord through the checklist. Configurations to the lot describe how a matter begins, the
   lord's condition how it turns out; a lord under the beams hides or withers the topic.
6. **Foundation of the life.** The triplicity lords of the sect light by angularity: the first lord for the first
   part of life, the second for the second, the third throughout.
7. **Write it up** in plain language; open questions from REVIEW.md marked as such.

## Timing (when asked)

1. **Annual profections** — `astro --json timing profections --chart NAME --pack hellenistic`: the year's place and
   its topics, the lord of the year (its natal condition decides how the year goes), the place the lord sits in, and
   planets in the profected sign; also from the sect light and the other light.
2. **Time-lord transits** — `astro --json timing transits …`: only the lords' ingresses, sign-based configurations and
   exact hits, and planets entering the profected sign. A transit counts from its ingress and peaks near exact.
3. **The sect light's lords** — `astro --json timing lords …`: which lord supports which part of life, and the candidate
   years when the second takes over.
4. **Zodiacal releasing** — `astro --json timing releasing … --lot spirit` for career and direction, `--lot fortune`
   for body and health: the current periods, peaks (angles from Fortune), the loosing of the bond, and each period's
   quality from planets in or squaring the sign, its ruler, and the sect benefic's and contrary malefic's angles.
   `astro --json timing search … --what peak|loosing` for dates. A subperiod in the sign holding the general period's
   ruler (`holds_ruler`) often marks the period's focal events.

