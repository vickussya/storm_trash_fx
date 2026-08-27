# -*- coding: utf-8 -*-
"""The channels this add-on owns, and the only code allowed to write them.

Storm Trash FX touches exactly four properties on an object: Delta Location Z
and the three Delta Rotation Euler axes.  Everything that adds, removes or
resets one of them goes through this module, so the ownership boundary is
visible in one place.
"""

from mathutils import Quaternion, Vector

LIFT_PATH = "delta_location"
LIFT_INDEX = 2
SHAKE_PATH = "delta_rotation_euler"

#: Every (data_path, array_index) this add-on is allowed to write.
OWNED_CHANNELS = (
    (LIFT_PATH, LIFT_INDEX),
    (SHAKE_PATH, 0),
    (SHAKE_PATH, 1),
    (SHAKE_PATH, 2),
)

EULER_MODES = {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'}


def remove_driver(obj, data_path, index):
    """Remove any driver on this channel; ignore if none exists."""
    try:
        return bool(obj.driver_remove(data_path, index))
    except Exception:
        return False


def remove_keyframes(obj, data_path, index):
    """Remove baked keyframes on this channel, so Clear can undo a Bake."""
    ad = obj.animation_data
    if ad is None or ad.action is None:
        return False
    removed = False
    try:
        for fc in list(ad.action.fcurves):
            if fc.data_path == data_path and fc.array_index == index:
                ad.action.fcurves.remove(fc)
                removed = True
    except Exception:
        pass
    return removed


def reset_channel(obj, data_path, index):
    """Drop the driver, drop baked keys, and put the channel back to rest.

    Zeroing matters: removing a driver leaves the last evaluated value behind,
    which is what strands objects mid-air or permanently tilted.  Never call
    ``remove_driver`` on its own at a call site - use this.
    """
    had = remove_driver(obj, data_path, index)
    had = remove_keyframes(obj, data_path, index) or had
    try:
        getattr(obj, data_path)[index] = 0.0
    except Exception:
        pass
    return had


def reset_all(obj):
    """Return every owned channel on this object to rest."""
    for data_path, index in OWNED_CHANNELS:
        reset_channel(obj, data_path, index)


def owned_driver_channels(obj):
    """Channels on this object currently driven by Storm FX."""
    ad = obj.animation_data
    if ad is None:
        return []
    return [(fc.data_path, fc.array_index) for fc in ad.drivers
            if (fc.data_path, fc.array_index) in OWNED_CHANNELS]


def ensure_euler(obj):
    """Switch to an Euler rotation mode without moving the object.

    ``delta_rotation_euler`` is ignored while the object is in Quaternion or
    Axis-Angle mode, so shake needs Euler - but flipping the mode blind makes
    the object jump, because ``rotation_euler`` keeps whatever stale values it
    had.  Convert the orientation first.
    """
    if obj.rotation_mode in EULER_MODES:
        return
    try:
        if obj.rotation_mode == 'QUATERNION':
            obj.rotation_euler = obj.rotation_quaternion.to_euler('XYZ')
        else:  # AXIS_ANGLE
            aa = obj.rotation_axis_angle
            axis = Vector((aa[1], aa[2], aa[3]))
            if axis.length > 1e-9:
                obj.rotation_euler = Quaternion(axis, aa[0]).to_euler('XYZ')
    except Exception:
        pass
    obj.rotation_mode = 'XYZ'
