# -*- coding: utf-8 -*-
"""The N-panel, under the "Storm FX" tab in the 3D View."""

import bpy


class STORMFX_PT_panel(bpy.types.Panel):
    bl_label = "Storm Trash FX"
    bl_idname = "STORMFX_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Storm FX"

    def draw(self, context):
        layout = self.layout
        props = context.scene.storm_fx

        self._draw_storm(layout, props)
        self._draw_ceiling(layout, props)
        self._draw_weight(layout, props)
        self._draw_effect(layout, props)
        self._draw_shake(layout, props)
        self._draw_actions(layout)
        self._draw_bake(layout, props)

    # -- sections ------------------------------------------------------------

    def _draw_storm(self, layout, props):
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(props, "storm_object")
        row.operator("stormfx.pick_default_storm", text="", icon='VIEWZOOM')
        col.prop(props, "radius")
        col.prop(props, "falloff")
        if props.storm_object is None:
            layout.label(text="Pick a Storm Object to begin", icon='ERROR')

    def _draw_ceiling(self, layout, props):
        box = layout.box()
        box.label(text="Ceiling (don't enter storm)", icon='TRIA_UP_BAR')
        box.prop(props, "use_manual_bottom")
        if props.use_manual_bottom:
            box.prop(props, "storm_bottom_z")
        else:
            box.prop(props, "storm_bottom_object")
        box.prop(props, "ceiling_margin")

    def _draw_weight(self, layout, props):
        box = layout.box()
        box.label(text="Weight response", icon='PHYSICS')
        box.prop(props, "min_factor", slider=True)

    def _draw_effect(self, layout, props):
        box = layout.box()
        box.label(text="Effect", icon='FORCE_TURBULENCE')
        row = box.row(align=True)
        row.prop(props, "do_lift", toggle=True)
        row.prop(props, "do_shake", toggle=True)

    def _draw_shake(self, layout, props):
        if not props.do_shake:
            return
        box = layout.box()
        box.label(text="Shake", icon='FORCE_HARMONIC')

        col = box.column(align=True)
        col.prop(props, "tilt_degrees")
        col.prop(props, "twist_degrees")
        row = col.row(align=True)
        row.label(text="Axes:")
        row.prop(props, "shake_x", toggle=True)
        row.prop(props, "shake_y", toggle=True)
        row.prop(props, "shake_z", toggle=True)

        col = box.column(align=True)
        col.prop(props, "shake_speed")
        col.prop(props, "shake_roughness", slider=True)
        col.prop(props, "shake_speed_variation", slider=True)
        col.prop(props, "shake_speed_by_weight", slider=True)
        col.prop(props, "shake_reach")

        sub = box.box()
        sub.prop(props, "do_rattle")
        if props.do_rattle:
            sub.prop(props, "rattle_distance")

        box.prop(props, "seed")

    def _draw_actions(self, layout):
        layout.separator()
        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator("stormfx.apply", icon='CHECKMARK')
        col.operator("stormfx.clear", icon='X')

    def _draw_bake(self, layout, props):
        box = layout.box()
        box.label(text="Bake", icon='RENDER_ANIMATION')
        box.prop(props, "bake_use_scene_range")
        if not props.bake_use_scene_range:
            row = box.row(align=True)
            row.prop(props, "bake_start")
            row.prop(props, "bake_end")
        box.operator("stormfx.bake", icon='RENDER_ANIMATION')


CLASSES = (STORMFX_PT_panel,)
