"""Load Sightline's project-specific Unreal MCP tools.

Unreal imports ``init_unreal.py`` from enabled plugins at editor startup.
Scene creation stays explicit so opening the project never overwrites content.
"""

import unreal


def _load_toolset() -> None:
    try:
        import sightline_toolset

        if sightline_toolset.register():
            unreal.log("[Sightline] MCP toolset registered.")
        else:
            unreal.log_warning("[Sightline] MCP toolset registry is not available yet.")
    except Exception as exc:  # Editor startup should remain usable on partial plugin loads.
        unreal.log_warning(f"[Sightline] MCP toolset registration deferred: {exc}")


_load_toolset()
unreal.log("[Sightline] Python tools loaded. Run: import sightline; sightline.build_demo_scene()")
