# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The version here mirrors `bl_info["version"]` in `storm_trash_fx/__init__.py`.

## [Unreleased]

### Changed

- **Split the single `storm_trash_fx.py` into a package.** The file had grown
  to roughly 500 lines mixing measurement, driver construction, operators and
  UI. It is now `storm_trash_fx/` with one concern per module - `channels`
  (the four delta channels the add-on owns), `measure` (reading the scene),
  `rig` (driver expressions), `props`, `operators`, `ui` - layered one-way so
  nothing reaches back up. No behaviour changed.
- Cross-module helpers lost their leading underscore; module-private ones kept
  it.
- `__init__.py` reloads its submodules when the add-on is re-enabled, so edits
  take effect without restarting Blender.
- The panel `draw()` is split into one method per section.

### Added

- `tools/check.py` - stubs `bpy` and `mathutils`, imports every module, and
  asserts the driver expressions, weight curve, phase seeding and channel
  ownership. Runs without Blender.

### Removed

- **Running the add-on from Blender's Text Editor.** A package cannot be run as
  a loose script. Zip the repository contents and install that, or drop the
  `storm_trash_fx/` folder into `scripts/addons/`.

## [1.1.0] - 2026-08-27

The rig did not evaluate reliably in 1.0.0. This release fixes that and the
related cleanup bugs.

### Fixed

- **Dependency cycle in every driver.** The proximity term used a `LOC_DIFF`
  (Distance) variable between the object and the storm, which made the object's
  own transform an input to a driver on that same transform. Blender detected
  the cycle and broke it with stale data, so the rig froze or jittered.
  Proximity is now read from two native Transform Channel variables on the
  *storm*, compared against the object's resting position baked into the
  expression as constants — a one-way dependency, still on the fast
  simple-expression path.
- **Objects stranded mid-air or permanently tilted.** Removing a driver leaves
  the last evaluated value on the channel. Disabling Lift, deselecting a shake
  axis, or re-applying with different settings left those values behind. Every
  channel this add-on owns is now zeroed whenever its driver is removed.
- **Clear could not undo a Bake.** It removed drivers only, so baked keyframes
  kept driving the object. Clear now removes keyframes on the owned channels
  too.
- **Bake read the wrong values.** It sampled the original datablock rather than
  the depsgraph-evaluated copy the drivers actually write to. It also resolved
  objects by name mid-bake, which broke on renames and on name collisions
  between libraries; it now holds object references.
- **Nothing was ever at full strength.** Distance was measured in 3D, so an
  object directly beneath a storm 5 m overhead only saw ~75% of the effect.
  Proximity is now measured horizontally: full effect underneath, zero at the
  influence radius.
- **Flat and thin pieces broke the weight scale.** Size came from bounding-box
  *volume*, which is zero for anything planar, dropping those objects to the
  lightest end of a log scale and squashing every other object toward
  *Heaviest Effect*. Size is now the bounding-box diagonal.
- **Switching to Euler made objects jump.** Shake needs an Euler rotation mode,
  and the mode was flipped without converting the rotation, so Quaternion and
  Axis-Angle objects snapped to whatever stale values `rotation_euler` held.
  The orientation is now converted first.
- **Shake phases were not reproducible.** They came from a shared RNG advanced
  in selection order, which is not stable, so re-applying reshuffled the whole
  scene. Phases now derive from the object's name plus the seed.
- **Driver F-curves could remap the result.** Generated modifiers and stray
  keyframe points on a driver F-curve are now cleared, so the driver's raw
  value is what reaches the channel.
- Ceilings are measured with the rig reset to rest, so re-applying with the
  storm parked over a pile no longer measures from an already-lifted object.
- `unregister()` no longer raises when the scene property is already gone
  (re-enabling the add-on).

### Changed

- The proximity ramp is squared, so the effect eases off instead of hitting the
  influence radius with a visible kink.
- *Shake Amount* is normalised against the sine sum's 1.5 peak, so the value in
  the panel is the actual peak wobble in degrees (it used to overshoot by 50%).
- Apply now forces a depsgraph refresh, so the new rig evaluates immediately
  instead of on the next scrub.
- Auto-detect Storm falls back to any object with "storm" in its name.
- The panel shows a hint when no Storm Object is set.

## [1.0.0] - 2026-08-27

### Added

- Proximity-driven **lift** on `delta_location[2]` and proximity-gated **shake**
  on `delta_rotation_euler`, with per-axis frequencies, per-object random
  phases, and selectable X/Y/Z axes.
- **Automatic size weighting** on a log curve between *Heaviest Effect* and 1.0.
- **Automatic per-object ceiling** so an object's top can never reach the storm
  underside — read from an object's bounding box or a manual Z, with a margin.
- Operators: *Apply to Selected*, *Clear on Selected*, *Bake to Keyframes*
  (scene or custom frame range), and *Auto-detect Storm*.
- 3D View N-panel UI under the **Storm FX** tab.
- Works both as an installed add-on and as a script run from the Text Editor.
- `README.md`, `AGENTS.md` and this changelog; the long module docstring moved
  out of the source into the README.
