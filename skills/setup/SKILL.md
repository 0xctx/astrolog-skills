---
name: setup
description: Set up and health-check astrolog-skills — find Astrolog or build it from its official source, create the ~/.astrolog-skills data folder, verify calculations, and show the current sky. Use when the user has just installed the plugin, says set up / get started / is it working / install astrolog, or any `astro` command reports Astrolog missing or broken.
---

# Setup — from installed to "seeing the sky"

The toolkit command is `astro`. In Claude Code it is on your PATH while this plugin is enabled; if it is not found,
use `${CLAUDE_PLUGIN_ROOT}/bin/astro`. In other agents (e.g. Antigravity) the user puts the repository's `bin`
onto their PATH once: `ln -s <repo>/bin/astro ~/.local/bin/astro` on macOS/Linux; on Windows, add `<repo>\bin` to
the user PATH (it holds `astro.cmd` for PowerShell and cmd). If it says **uv** is missing, tell the user to install
it (`curl -LsSf https://astral.sh/uv/install.sh | sh`, or on Windows
`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`) and restart their agent.

Commands written `! astro …` are for the user to run: in Claude Code, typed at the prompt with the `!`; in other
agents, without the `!` in their own terminal (colour views need a real terminal).

## 1. Check

Run `astro --json doctor` yourself and read `checks[]` (each has `status` ok/warn/fail/info/skip, `detail`, `fix`).

- **All ok** → tell the user it works in one line, and hand them the colour view:
  `! astro doctor` — it ends with a "first light" card of the current sky.
- **Any fail** → handle it below, then run `astro --json doctor` again until it passes.

## 2. Astrolog missing, too old, or on a too-long path

Ask the user which they prefer — never install without a clear yes:

1. **Build the official Astrolog 8.00 for them** — downloads the release from github.com/CruiserOne/Astrolog,
   verifies its checksum, compiles it headless in ~10 seconds, and installs it into
   `~/.astrolog-skills/astrolog`. Nothing else on their computer is touched.
   - Run `astro astrolog install` (preview only — downloads nothing) and summarise the plan.
   - Only after they agree: `astro astrolog install --yes` (add `--force` if replacing that folder).
   - If it reports a missing compiler or `make`, give them the exact command from the `fix` (it's OS-specific,
     e.g. `sudo dnf install gcc-c++ make`). Don't run `sudo` yourself.
2. **Use an Astrolog they already have** — `astro config set astrolog.path /path/to/astrolog`.

## 3. Other problems

Relay each failing check's `fix` in plain words. A warning about the `astro` command means another program
named `astro` (e.g. the Astro web framework) shadows ours — use the plugin's `bin/astro` by its full path
(`${CLAUDE_PLUGIN_ROOT}/bin/astro` in Claude Code), or link it under another name.

## 4. Location (for the rising sign)

Offer to set their usual location. Ask for the place, look up its coordinates, then:
`astro config set location "<lat> <lon>" --name "<place>"` — e.g. `"48N24 10E00"` or `"48.4, 10.0"`.

## Rules

- Read `--json` (or `--plain`) output yourself; give the user `! astro …` commands to see colour views.
- Never download or install anything without the user's explicit consent.
- Other settings: `astro config show`, `astro config set KEY VALUE` (keys listed in the error if one is wrong).
