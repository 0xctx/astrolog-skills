@echo off
rem astrolog-skills on Windows (PowerShell, cmd): run the toolkit from this plugin's root with uv.
rem Same as bin/astro (used by Git Bash, macOS and Linux). The venv lives outside the plugin folder.
setlocal
set "ROOT=%~dp0.."
where uv >nul 2>nul
if errorlevel 1 (
  echo x astrolog-skills needs uv ^(the Python runner^). 1>&2
  echo   - install it: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   ^(then restart your agent or terminal^) 1>&2
  exit /b 127
)
set "ASTROLOG_SKILLS_PLUGIN_ROOT=%ROOT%"
set "ASTROLOG_SKILLS_CALLER_PATH=%PATH%"
if not defined ASTROLOG_SKILLS_VENV set "ASTROLOG_SKILLS_VENV=%LOCALAPPDATA%\astrolog-skills\venv"
set "UV_PROJECT_ENVIRONMENT=%ASTROLOG_SKILLS_VENV%"
uv run --quiet --frozen --no-dev --project "%ROOT%" python -m astrolog_skills %*
exit /b %ERRORLEVEL%
