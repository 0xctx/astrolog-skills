# Contributing

Issues and pull requests are welcome.

```
uv sync
scripts/validate.sh                           # every check, one verdict (--full adds network + the official build)
uv run pytest                                 # unit tests: no network, no Astrolog needed (a fake binary)
uv run pytest -m "astrolog and not network"   # against your real Astrolog, including the end-to-end journey
```

Run `scripts/validate.sh` before sending a change. To script against the package, use the project's environment:
`uv run python -c "import astrolog_skills"` (the system `python3` doesn't have its dependencies).

- **A new tradition, profile, theme or HTML design is data, not code:** copy one from `traditions/`, `profiles/`,
  `themes/` or `presets/` and edit it.
- **Astrolog does every calculation:** positions come from Astrolog through the active profile's pinned settings;
  the toolkit computes only on top of them (harmonics, midpoints, doctrine, timing).
- **The browser page mirrors the Python:** anything recomputed in `presets/default/core.js` keeps the parity tests in
  `tests/test_export.py` passing.
- **No author or software names** outside the packs' `sources.toml` files.
