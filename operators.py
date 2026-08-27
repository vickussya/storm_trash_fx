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

        # Spin needs to know when the storm passes each object, which means
        # sampling its path.  That steps the scene, so it happens after every
        # measurement above is taken, and only when spin is actually on.
        windows = {}
        if props.do_shake and props.do_spin:
            track = measure.storm_track(
                scene, storm, context.evaluated_depsgraph_get)
            reach = max(0.0001, props.radius) * max(0.01, props.shake_reach)
            for o in targets:
                windows[o] = measure.pass_window(
                    track, stats[o][0], stats[o][1], reach)

        done = 0
        capped = 0
        for o in targets:
            cx, cy, top_z, size = stats[o]
            lightness = measure.lightness(size, size_min, size_max)
            ceiling = (bottom - props.ceiling_margin) - top_z
            if ceiling <= 0.0:
                # already at or above the ceiling: shake only, no lift
                ceiling = 0.0
                if props.do_lift:
                    capped += 1
            rig.apply_to_object(o, storm, props, lightness, (cx, cy), ceiling,
                                fps, windows.get(o))
            o.update_tag()
            done += 1

        # force a depsgraph relations rebuild so the new drivers evaluate now
        scene.frame_set(scene.frame_current)

        msg = "Storm FX applied to {} object(s)".format(done)
        if capped:
            msg += " ({} too tall to lift - shake only)".format(capped)
        if windows and not any(w for w in windows.values()):
            msg += "; no spin - the storm never passes within reach"
            self.report({'WARNING'}, msg)
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
    STORMFX_OT_pick_default_storm,
)
