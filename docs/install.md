# Installing astrolog-skills

## 1. uv

The toolkit is Python, run by [uv](https://docs.astral.sh/uv/) (it fetches Python and dependencies itself):

```
curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS / Linux
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

Restart your agent (and terminal) afterwards so `uv` is on its PATH.

## 2. The skills

### Claude Code

```
/plugin marketplace add 0xctx/astrolog-skills
/plugin install astrolog-skills@astrolog-skills
```

Start a new session. The `astro` command is now on Claude's PATH (from the plugin's `bin/`). If another program called
`astro` shadows it (e.g. the Astro web framework), `astro doctor` warns you. A local clone works too:
`/plugin marketplace add /path/to/astrolog-skills`.

### Google Antigravity CLI (`agy`)

macOS and Linux:

```
git clone https://github.com/0xctx/astrolog-skills.git ~/astrolog-skills
mkdir -p ~/.local/bin && ln -s ~/astrolog-skills/bin/astro ~/.local/bin/astro
agy plugin install ~/astrolog-skills
```

The link puts `astro` on your PATH (make sure `~/.local/bin` is on it: `echo $PATH`); the plugin gives Antigravity
the skills (`skills/<name>/SKILL.md`).

Windows (PowerShell, untested):

```
git clone https://github.com/0xctx/astrolog-skills.git $HOME\astrolog-skills
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";$HOME\astrolog-skills\bin", "User")
agy plugin install $HOME\astrolog-skills
```

The second line adds the repository's `bin` folder to your user PATH: it holds `astro.cmd`, which PowerShell and
cmd run as `astro`. Open a new terminal afterwards. Without the plugin, copy them instead, for all projects
(`~/.gemini/antigravity-cli/skills/`) or one (`<project>/.agents/skills/`). Commands the skills show as
`! astro …` are run without the `!` in your own terminal. To update: `git -C ~/astrolog-skills pull`, then
`agy plugin install ~/astrolog-skills` again.

## 3. Astrolog

Say **"set up astrolog skills"**, or run `astro doctor` in a terminal (`! astro doctor` in Claude Code). You can:

- **Use an Astrolog you have** (7.80 or newer): it's found automatically in the usual places (`~/astrolog/`, your PATH),
  or set it: `astro config set astrolog.path /path/to/astrolog`.
- **Let the toolkit build the official one:** `astro astrolog install` shows the plan (source URL, checksum, target
  folder) and downloads nothing; `astro astrolog install --yes` downloads the pinned v8.00 release from
  github.com/CruiserOne/Astrolog, verifies its SHA-256, builds it without X11 (~10 s) and installs it into
  `~/.astrolog-skills/astrolog`, then verifies a test chart. It never touches another install.

Building needs `make`, `cc` and a C++ compiler:

| System | Command |
|---|---|
| Fedora / RHEL | `sudo dnf install gcc-c++ make` |
| Debian / Ubuntu / Mint | `sudo apt install build-essential` |
| Arch | `sudo pacman -S base-devel` |
| openSUSE | `sudo zypper install gcc-c++ make` |
| Alpine | `sudo apk add build-base` |
| macOS | `xcode-select --install` |
| Windows (Git Bash) | nothing — the official prebuilt `astrolog.exe` is unpacked instead |

**Keep the install path short** — Astrolog's Swiss Ephemeris stops working (silently printing nothing) when its folder
path is very long; `astro doctor` checks for this.

## 4. First steps

```
! astro doctor                                   # all green + "first light": the sky right now
! astro config set location "48N24 10E00" --name Ulm   # your usual place (rising sign, transits)
```

Then just talk to your agent: "save my chart…", "show my chart", "what are my strongest harmonics?".

## Optional: tools for book sources

Only needed to add books to a tradition (`astro sources add`); `astro doctor` checks them and prints the install line.

| Tool | For | Fedora | Debian/Ubuntu | macOS |
|---|---|---|---|---|
| poppler (`pdftotext`, `pdftoppm`) | PDF books, page images of tables | `sudo dnf install poppler-utils` | `sudo apt install poppler-utils` | `brew install poppler` |
| `ocrmypdf` (with tesseract) | scanned PDFs without a text layer | `sudo dnf install ocrmypdf` | `sudo apt install ocrmypdf` | `brew install ocrmypdf` |

Text files, notes, transcripts and web pages need neither.

## Platform status

| Platform | Status |
|---|---|
| Linux (Fedora 42) | tested: Astrolog 7.80 (existing) and 8.00 (built by the installer) |
| macOS | untested — build path uses `LIBS=-lm` and the system clang |
| Windows | untested — Claude Code runs `bin/astro` through Git Bash; PowerShell and cmd run `bin/astro.cmd`; Astrolog comes from the official prebuilt Windows program (no compiler needed) |
| Google Antigravity CLI | the plugin passes `agy plugin validate` (Linux); `astro` goes on the PATH (above) |

If something fails, `astro --plain doctor` shows each check with a fix. Please include its output in any report.
