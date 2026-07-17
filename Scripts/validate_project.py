#!/usr/bin/env python3
"""Static validation for the repository-side Unreal project configuration."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPROJECT = ROOT / "SightlineSyntheticUE.uproject"
REQUIRED_PLUGINS = {
    "SightlineGenerator",
    "ModelContextProtocol",
    "AllToolsets",
    "PythonScriptPlugin",
    "EditorScriptingUtilities",
    "MovieRenderPipeline",
    "ControlRig",
    "CameraCalibration",
    "MetaHuman",
    "MetaHumanCharacter",
}
REQUIRED_PATHS = [
    ROOT / ".gitignore",
    ROOT / ".gitattributes",
    ROOT / ".mcp.json",
    ROOT / ".codex/config.toml",
    ROOT / "Config/DefaultEngine.ini",
    ROOT / "Config/DefaultEditorPerProjectUserSettings.ini",
    ROOT / "Plugins/SightlineGenerator/SightlineGenerator.uplugin",
    ROOT / "Plugins/SightlineGenerator/Content/Python/sightline/scene.py",
    ROOT / "Plugins/SightlineGenerator/Content/Python/sightline_toolset/__init__.py",
    ROOT / "Docs/UNREAL_5_8_LEARNINGS.md",
    ROOT / "Docs/Images/sightline-preview.png",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> None:
    if not UPROJECT.exists():
        fail(f"missing {UPROJECT.name}")

    data = json.loads(UPROJECT.read_text(encoding="utf-8"))
    if data.get("EngineAssociation") != "5.8":
        fail("project is not pinned to Unreal Engine 5.8")

    enabled = {
        entry["Name"]
        for entry in data.get("Plugins", [])
        if entry.get("Enabled") is True
    }
    missing_plugins = sorted(REQUIRED_PLUGINS - enabled)
    if missing_plugins:
        fail(f"required plugins are not enabled: {', '.join(missing_plugins)}")

    missing_paths = [str(path.relative_to(ROOT)) for path in REQUIRED_PATHS if not path.exists()]
    if missing_paths:
        fail(f"missing project files: {', '.join(missing_paths)}")

    mcp_settings = (ROOT / "Config/DefaultEditorPerProjectUserSettings.ini").read_text(
        encoding="utf-8"
    )
    for expected in ("bAutoStartServer=True", "ServerPortNumber=8000", "bEnableToolSearch=True"):
        if expected not in mcp_settings:
            fail(f"MCP setting missing: {expected}")

    codex_config = (ROOT / ".codex/config.toml").read_text(encoding="utf-8")
    if 'url = "http://127.0.0.1:8000/mcp"' not in codex_config:
        fail("Codex MCP URL is incorrect")

    tracked_python = list(
        (ROOT / "Plugins/SightlineGenerator/Content/Python").rglob("*.py")
    )
    for path in tracked_python:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    toolset_source = (
        ROOT / "Plugins/SightlineGenerator/Content/Python/sightline_toolset/__init__.py"
    ).read_text(encoding="utf-8")
    if "_registration.register()" not in toolset_source:
        fail("custom toolset is constructed but not explicitly registered")

    print(
        "PASS: UE 5.8 project config, native MCP, custom toolset, Git/LFS, "
        f"and {len(tracked_python)} Python files validated."
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError, SyntaxError) as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
