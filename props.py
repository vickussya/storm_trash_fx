# -*- coding: utf-8 -*-
"""Panel settings, stored on the scene as ``scene.storm_fx``.

Every property needs a ``name`` and a plain-language ``description`` - the
description is the tooltip the artist reads.
"""

import bpy


class StormFXProps(bpy.types.PropertyGroup):
    # ---- storm -------------------------------------------------------------
    storm_object: bpy.props.PointerProperty(
        name="Storm Object",
        description="Object the trash reacts to (the storm center that moves over the scene)",
        type=bpy.types.Object,
    )
    radius: bpy.props.FloatProperty(
        name="Influence Radius",
        description="Horizontal distance at which the storm starts to affect an object",
        default=21.0, min=0.001, soft_max=100.0,
    )

    # ---- ceiling -----------------------------------------------------------
    storm_bottom_object: bpy.props.PointerProperty(
        name="Ceiling From",
        description="Optional: object whose bounding-box bottom defines the storm underside. Defaults to the Storm Object",
        type=bpy.types.Object,
    )
    use_manual_bottom: bpy.props.BoolProperty(
        name="Manual Ceiling Height",
        description="Type the storm underside Z directly instead of reading it from an object",
        default=False,
    )
    storm_bottom_z: bpy.props.FloatProperty(
        name="Storm Bottom Z",
        description="World Z of the storm underside (objects are kept below this)",
        default=5.18,
    )
    ceiling_margin: bpy.props.FloatProperty(
        name="Ceiling Margin",
        description="Safety gap kept between an object's top and the storm underside",
        default=0.5, min=0.0, soft_max=5.0,
    )

    # ---- weight response ---------------------------------------------------
    min_factor: bpy.props.FloatProperty(
        name="Heaviest Effect",
        description="Fraction of the effect the heaviest object still gets (0 = it never moves)",
        default=0.15, min=0.0, max=1.0,
    )

    # ---- effect ------------------------------------------------------------
    do_lift: bpy.props.BoolProperty(name="Lift", default=True)
    do_shake: bpy.props.BoolProperty(name="Shake", default=True)
    shake_degrees: bpy.props.FloatProperty(
        name="Shake Amount",
        description="Peak wobble in degrees for the lightest object",
        default=12.0, min=0.0, soft_max=90.0,
    )
    shake_speed: bpy.props.FloatProperty(
        name="Shake Speed",
        description="How fast the trembling is (higher = faster)",
        default=0.9, min=0.0, soft_max=10.0,
    )
    shake_x: bpy.props.BoolProperty(name="X", default=True)
    shake_y: bpy.props.BoolProperty(name="Y", default=True)
    shake_z: bpy.props.BoolProperty(name="Z", default=False)
    seed: bpy.props.IntProperty(
        name="Random Seed",
        description="Change to get a different set of per-object shake phases",
        default=1,
    )

    # ---- bake --------------------------------------------------------------
    bake_use_scene_range: bpy.props.BoolProperty(
        name="Use Scene Frame Range",
        description="Bake over the scene's start..end frames",
        default=True,
    )
    bake_start: bpy.props.IntProperty(name="Bake Start", default=1)
    bake_end: bpy.props.IntProperty(name="Bake End", default=250)


CLASSES = (StormFXProps,)
