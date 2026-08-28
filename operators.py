# -*- coding: utf-8 -*-
"""The four buttons: Apply, Clear, Bake, Auto-detect Storm.

All scene mutation lives here, inside operators carrying
``{'REGISTER', 'UNDO'}`` so the user can Ctrl+Z out of it.  Nothing in this
add-on changes the scene until one of these runs.
"""

import bpy

from . import channels, measure, rig


class STORMFX_OT_apply(bpy.types.Operator):
    bl_idname = "stormfx.apply"
    bl_label = "Apply to Selected"
    bl_description = "Build the lift + shake rig on all selected mesh objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.storm_fx
        storm = props.storm_object
        if storm is None:
            self.report({'ERROR'}, "Set a Storm Object first.")
            return {'CANCELLED'}

        targets = [o for o in context.selected_objects
                   if o.type == 'MESH' and o is not storm]
        if not targets:
            self.report({'ERROR'}, "Select at least one mesh object (other than the storm).")
            return {'CANCELLED'}
        targets.sort(key=lambda o: o.name)

        # Put everything back to rest BEFORE measuring, so re-applying with the
        # storm parked over the piles still reads true resting heights.
        for o in targets:
            channels.reset_all(o)
        context.view_layer.update()

        depsgraph = context.evaluated_depsgraph_get()
        stats = {o: measure.bbox_stats(o, depsgraph) for o in targets}
        sizes = [s[3] for s in stats.values()]
        size_min, size_max = min(sizes), max(sizes)
        bottom = measure.storm_bottom_z(props, depsgraph)

        # the shake speed is in cycles per second, but a driver only knows
        # `frame`, so the scene frame rate is folded in here
        render = scene.render
        fps = render.fps / max(1e-6, render.fps_base)

        done = 0
        capped = 0
        swinging = 0
        worst_swing = 0.0
        for o in targets:
            cx, cy, top_z, size = stats[o]
            lightness = measure.lightness(size, size_min, size_max)

            # Delta rotation pivots on the origin, so an off-centre origin
            # turns a spin into an arc.  Pick the axis that swings least, and
            # keep the worst residual to report.
            offset = measure.origin_offset(o, depsgraph)
            auto_axis = measure.best_spin_axis(offset)
            if props.do_shake and props.do_spin:
                swing = measure.spin_swing(offset, auto_axis)
                if swing > size * 0.1:
                    swinging += 1
                    worst_swing = max(worst_swing, swing)
            ceiling = (bottom - props.ceiling_margin) - top_z
            if ceiling <= 0.0:
                # already at or above the ceiling: shake only, no lift
                ceiling = 0.0
                if props.do_lift:
                    capped += 1
            rig.apply_to_object(o, storm, props, lightness, (cx, cy), ceiling,
                                fps, auto_axis)
            o.update_tag()
            done += 1

        # force a depsgraph relations rebuild so the new drivers evaluate now
        scene.frame_set(scene.frame_current)

        msg = "Storm FX applied to {} object(s)".format(done)
        if capped:
            msg += " ({} too tall to lift - shake only)".format(capped)

        rigid = sum(1 for o in targets if getattr(o, "rigid_body", None) is not None)
        if rigid:
            self.report({'WARNING'}, msg + "; {} have rigid body physics - the "
                        "delta channels stack on top of the simulation, which "
                        "does not know about them".format(rigid))
            return {'FINISHED'}
        if swinging:
            self.report({'WARNING'}, msg + "; {} have off-centre origins and "
                        "will swing up to {:.2f} units when they spin - use "
                        "Centre Origins, or lower Spin Turns".format(
                            swinging, worst_swing))
            return {'FINISHED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class STORMFX_OT_clear(bpy.types.Operator):
    bl_idname = "stormfx.clear"
    bl_label = "Clear on Selected"
    bl_description = ("Remove Storm FX drivers and baked keyframes from the delta "
                      "channels on selected objects and return them to rest")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = 0
        for o in context.selected_objects:
            if o.type != 'MESH':
                continue
            channels.reset_all(o)
            o.update_tag()
            n += 1
        context.scene.frame_set(context.scene.frame_current)
        self.report({'INFO'}, "Cleared Storm FX on {} object(s)".format(n))
        return {'FINISHED'}


class STORMFX_OT_bake(bpy.types.Operator):
    bl_idname = "stormfx.bake"
    bl_label = "Bake to Keyframes"
    bl_description = ("Sample the drivers to keyframes over the frame range and remove "
                      "the live drivers (faster playback / render)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.storm_fx
        selected = [o for o in context.selected_objects if o.type == 'MESH']
        if not selected:
            self.report({'ERROR'}, "Select the objects to bake.")
            return {'CANCELLED'}

        if props.bake_use_scene_range:
            f0, f1 = scene.frame_start, scene.frame_end
        else:
            f0, f1 = props.bake_start, props.bake_end
        if f1 < f0:
            f0, f1 = f1, f0

        # which of our channels are actually driven, per object.  Object
        # references, not names: name lookups break on renames and on
        # collisions between linked libraries.
        plan = [(o, chans) for o, chans in
                ((o, channels.owned_driver_channels(o)) for o in selected) if chans]
        if not plan:
            self.report({'WARNING'}, "No Storm FX drivers found on the selection.")
            return {'CANCELLED'}

        # 1) sample the evaluated values per frame (drivers are evaluated on
        #    the depsgraph copy, so read that rather than the original)
        samples = {o: {ch: [] for ch in chans} for o, chans in plan}
        original_frame = scene.frame_current
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            depsgraph = context.evaluated_depsgraph_get()
            for o, chans in plan:
                try:
                    src = o.evaluated_get(depsgraph)
                except Exception:
                    src = o
                for dp, idx in chans:
                    samples[o][(dp, idx)].append(getattr(src, dp)[idx])

        # 2) drop the drivers, then write the samples back as keyframes
        for o, chans in plan:
            for ch in chans:
                dp, idx = ch
                channels.remove_driver(o, dp, idx)
                channels.remove_keyframes(o, dp, idx)
                for offset, val in enumerate(samples[o][ch]):
                    getattr(o, dp)[idx] = val
                    o.keyframe_insert(dp, index=idx, frame=f0 + offset)
            o.update_tag()

        scene.frame_set(original_frame)
        self.report({'INFO'}, "Baked {} object(s) over frames {}-{}".format(
            len(plan), f0, f1))
        return {'FINISHED'}


class STORMFX_OT_center_origins(bpy.types.Operator):
    bl_idname = "stormfx.center_origins"
    bl_label = "Centre Origins on Selected"
    bl_description = ("Move each selected object's origin to the centre of its geometry "
                      "so rotation spins it in place. Nothing moves on screen, and it is "
                      "undoable. Skips linked and shared-mesh objects")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        targets = [o for o in context.selected_objects if o.type == 'MESH']
        if not targets:
            self.report({'ERROR'}, "Select the objects to centre.")
            return {'CANCELLED'}

        # Blender refuses to move the origin of linked or multi-user data, and
        # duplicated library assets very often share one mesh - so filter those
        # out rather than letting the operator fail on the whole selection.
        skipped_linked = 0
        skipped_shared = 0
        movable = []
        for o in targets:
            data = o.data
            if o.library is not None or (data is not None and data.library is not None):
                skipped_linked += 1
            elif data is not None and data.users > 1:
                skipped_shared += 1
            else:
                movable.append(o)

        if not movable:
            self.report({'WARNING'}, "Nothing to centre: {} linked, {} share mesh "
                        "data. Make them single-user (Object > Relations > Make "
                        "Single User > Object & Data) first.".format(
                            skipped_linked, skipped_shared))
            return {'CANCELLED'}

        previous = list(context.selected_objects)
        active = context.view_layer.objects.active
        try:
            for o in previous:
                o.select_set(False)
            for o in movable:
                o.select_set(True)
            context.view_layer.objects.active = movable[0]
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        finally:
            for o in context.selected_objects:
                o.select_set(False)
            for o in previous:
                try:
                    o.select_set(True)
                except Exception:
                    pass
            context.view_layer.objects.active = active

        msg = "Centred {} origin(s)".format(len(movable))
        if skipped_linked or skipped_shared:
            msg += " ({} linked, {} sharing mesh data skipped)".format(
                skipped_linked, skipped_shared)
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


class STORMFX_OT_pick_default_storm(bpy.types.Operator):
    bl_idname = "stormfx.pick_default_storm"
    bl_label = "Auto-detect Storm"
    bl_description = "Try to find the storm object by common names"
    bl_options = {'REGISTER', 'UNDO'}

    #: Tried in order before falling back to a fuzzy name match.
    CANDIDATES = ("palachinka_mask_toroid_line_0", "Empty_storm")

    def execute(self, context):
        props = context.scene.storm_fx
        for cand in self.CANDIDATES:
            o = bpy.data.objects.get(cand)
            if o:
                props.storm_object = o
                self.report({'INFO'}, "Storm Object set to '{}'".format(cand))
                return {'FINISHED'}
        for o in bpy.data.objects:
            if "storm" in o.name.lower():
                props.storm_object = o
                self.report({'INFO'}, "Storm Object set to '{}'".format(o.name))
                return {'FINISHED'}
        self.report({'WARNING'}, "Could not auto-detect. Pick the storm object manually.")
        return {'CANCELLED'}


CLASSES = (
    STORMFX_OT_apply,
    STORMFX_OT_clear,
    STORMFX_OT_bake,
    STORMFX_OT_center_origins,
    STORMFX_OT_pick_default_storm,
)
