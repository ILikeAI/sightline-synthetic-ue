"""Register project-specific tools with UE 5.8's native Toolset Registry."""

import unreal
import toolset_registry
from toolset_registry.registration import Registration

import sightline


@unreal.uclass()
class SightlineDatasetTools(unreal.ToolsetDefinition):
    """Builds and operates the lightweight Sightline synthetic gaze-data scene."""

    @toolset_registry.tool_call
    @staticmethod
    def get_project_status() -> str:
        """Returns the current Sightline generator status without changing content."""
        return sightline.get_project_status()

    @toolset_registry.tool_call
    @staticmethod
    def build_demo_scene(seed: int = 7) -> str:
        """Builds the primitive-head, calibrated-screen and procedural-backdrop preview.

        Args:
            seed: Deterministic seed for target and backdrop randomization.

        Returns:
            A short summary of the generated map.
        """
        return sightline.build_demo_scene(seed)

    @toolset_registry.tool_call
    @staticmethod
    def randomize_preview(seed: int = 7) -> str:
        """Changes the preview target and procedural backdrop deterministically.

        Args:
            seed: Deterministic scenario seed.

        Returns:
            The resulting target coordinates.
        """
        return sightline.randomize_preview(seed)

    @toolset_registry.tool_call
    @staticmethod
    def validate_demo_scene() -> str:
        """Checks that required preview actors and MCP settings are present."""
        return sightline.validate_demo_scene()

    @toolset_registry.tool_call
    @staticmethod
    def write_preview_label(seed: int = 7) -> str:
        """Writes a representative JSON gaze-label record.

        Args:
            seed: Deterministic scenario seed.

        Returns:
            Absolute path to the generated label file.
        """
        return sightline.write_preview_label(seed)


_registration = Registration([SightlineDatasetTools])


def register() -> bool:
    """Register this project's toolset with Unreal's live registry."""
    return _registration.register()
