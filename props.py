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
    falloff: bpy.props.FloatProperty(
        name="Falloff",
        description="Shape of the ramp from the influence radius in to the storm. 1 = straight line, higher = the effect stays weak until the storm is close",
        default=2.0, min=0.25, soft_max=4.0,
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

    # ---- shake: how far it throws -----------------------------------------
    tilt_degrees: bpy.props.FloatProperty(
        name="Tilt Amount",
        description="Peak tilt in degrees for the lightest object, on the X and Y axes",
        default=12.0, min=0.0, soft_max=90.0,
    )
    twist_degrees: bpy.props.FloatProperty(
        name="Twist Amount",
        description="Peak twist in degrees for the lightest object, on the Z axis",
        default=6.0, min=0.0, soft_max=90.0,
    )
    shake_x: bpy.props.BoolProperty(name="X", default=True)
    shake_y: bpy.props.BoolProperty(name="Y", default=True)
    shake_z: bpy.props.BoolProperty(name="Z", default=False)

    # ---- shake: how it moves ----------------------------------------------
    shake_speed: bpy.props.FloatProperty(
        name="Speed",
        description="Base wobble rate in cycles per second. Converted using the scene frame rate when you Apply, so re-apply if you change the fps",
        default=1.5, min=0.0, soft_max=12.0,
    )
    shake_roughness: bpy.props.FloatProperty(
        name="Roughness",
        description="How much fast detail rides on the base wobble. 0 = a clean sway, 1 = a busy rattle",
        default=0.35, min=0.0, max=1.0,
    )
    shake_speed_variation: bpy.props.FloatProperty(
        name="Speed Variation",
        description="Random spread of wobble rate between objects, so a pile does not move in lockstep",
        default=0.3, min=0.0, max=1.0,
    )
    shake_speed_by_weight: bpy.props.FloatProperty(
        name="Speed by Weight",
        description="How much lighter objects wobble faster than heavy ones. 0 = everything at the same rate",
        default=0.5, min=0.0, max=1.0,
    )
    shake_reach: bpy.props.FloatProperty(
        name="Shake Reach",
        description="Shake radius as a multiple of the Influence Radius. Above 1 the trash starts trembling before it starts to rise",
        default=1.4, min=0.01, soft_max=3.0,
    )

    # ---- shake: positional rattle ------------------------------------------
    do_rattle: bpy.props.BoolProperty(
        name="Rattle",
        description="Also jitter objects horizontally, not just rotate them",
        default=True,
    )
    rattle_distance: bpy.props.FloatProperty(
        name="Rattle Amount",
        description="Peak horizontal jitter for the lightest object, in scene units",
        default=0.05, min=0.0, soft_max=1.0, subtype='DISTANCE',
    )

    seed: bpy.props.IntProperty(
        name="Random Seed",
        description="Change to get a different set of per-object shake phases and speeds",
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
