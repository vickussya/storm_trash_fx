# -*- coding: utf-8 -*-
"""Storm Trash FX - proximity-driven lift + shake rig for Blender.

As a storm object moves over the scene, each rigged object rises on Delta
Location Z and trembles on Delta Rotation, scaled by the object's size and
capped so its top never reaches the storm underside.

Nothing in the scene changes until the user presses a button in the panel.

Module map (this package IS the repository root, so that GitHub's
"Download ZIP" produces an archive Blender can install directly)
    channels    the four delta channels this add-on owns, and the only code
                that writes them
    measure     reading the scene: object size, resting position, storm
                underside, weight curve
    rig         building the driver expressions and the drivers themselves
    props       the panel settings, stored on the scene
    operators   Apply / Clear / Bake / Auto-detect - all scene mutation
    ui          the N-panel

Install, usage, settings reference and implementation notes: see README.md.
"""

bl_info = {
    "name": "Storm Trash FX",
    "author": "vickussya",
    "version": (1, 3, 0),
    "blender": (4, 2, 0),
    "location": "3D View > N-panel > Storm FX",
    "description": "Proximity-driven lift + shake for trash reacting to a moving storm, weighted by object size, capped below the storm.",
    "category": "Animation",
}

import bpy

# Reload submodules when the add-on is re-enabled during development, so
# edits actually take effect without restarting Blender.  Dependencies first.
if "channels" in locals():
    import importlib
    for _name in ("channels", "measure", "rig", "props", "operators", "ui"):
        if _name in locals():
            importlib.reload(locals()[_name])

from . import channels, measure, rig, props, operators, ui  # noqa: E402

_CLASSES = props.CLASSES + operators.CLASSES + ui.CLASSES


def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.storm_fx = bpy.props.PointerProperty(type=props.StormFXProps)


def unregister():
    if hasattr(bpy.types.Scene, "storm_fx"):
        del bpy.types.Scene.storm_fx
    for c in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
