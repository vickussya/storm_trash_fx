# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The version here mirrors `bl_info["version"]` in `__init__.py`.

## [1.4.0] - 2026-08-27

### Added

- **Spin** - objects tumble as the storm passes and keep the orientation they
  are left in, so the pile settles at new angles instead of returning to its
  rest pose. Controls: *Spin Turns* (rotations the lightest object makes),
  *Spin Axis* (X / Y / Z / Random per object) and *Spin Variation*. Direction
  is randomly signed per object, and the amount is weight-scaled.

  A driver has no memory - it is a pure function of `frame` and where the storm
  is right now - so an accumulating rotation cannot be integrated from the
  proximity gate; gating `rate * frame` winds an object up on the way in and
  unwinds it on the way out. Apply therefore samples the storm's path across
  the scene frame range, finds the frames during which it comes within reach of
  each object, and emits a ramp clamped at both ends. Two consequences: Apply
  steps the frame range when Spin is on (and only then), and re-timing or
  moving the storm means re-applying.

- Apply warns when Spin is on but the storm never passes within reach of
  anything selected.

### Changed

- Wobble and spin can share a rotation axis, so the expression builder now
  gives the wobble a character budget and drops octaves rather than overrun
  Blender's 256-character driver limit. Worst case measured at 233.
- `tools/check.py` covers the spin ramp (zero before the pass, monotonic
  through it, holding after, never running backwards), the pass-window
  search, random axis and direction spread, and the worst-case combined
  expression length.

## [1.3.0] - 2026-08-27

Shake polish. The old shake read as fast vibration rather than wind, and had
one speed control for the whole scene.

### Fixed

- **Shake Speed was radians per frame, not a rate.** At the default `0.9` the
  base wobble cycled every ~7 frames and the detail layer every ~3 - a 3-8 Hz
  buzz at 24fps, which is why objects appeared to judder up and down. **Speed
  is now in cycles per second**, converted using the scene frame rate at Apply
  time, and defaults to `1.5`. Note the frame rate is baked into the driver, so
  changing the scene fps means re-applying.

### Added

- **Rattle** - small horizontal jitter on Delta Location X and Y, on by
  default, with its own *Rattle Amount*. The add-on now owns six channels
  rather than four; Clear and Bake cover the new ones.
- **Roughness** - how much fast detail rides on the base wobble. `0` is a clean
  sway, `1` a busy rattle. Replaces the fixed second sine with up to two
  octaves at deliberately non-integer ratios (2.3x, 4.7x), so the motion does
  not settle into an obvious repeat.
- **Speed Variation** - random per-object spread of wobble rate, so a pile
  stops moving in lockstep. Previously only the phase varied, which still left
  everything pulsing at one frequency.
- **Speed by Weight** - lighter objects wobble faster than heavy ones, the way
  a smaller object has a higher natural frequency. A can buzzes, a dumpster
  lumbers.
- **Shake Reach** - shake radius as a multiple of the influence radius,
  defaulting to `1.4`, so trash trembles before it starts to rise.
- **Twist Amount** - separate peak for the Z axis, so twist can be dialled
  independently of tilt. *Shake Amount* is renamed **Tilt Amount** and now
  covers X and Y only.
- **Falloff** - shapes the proximity ramp for both lift and shake. `1` is a
  straight line; the previous fixed square is the default `2`.

### Changed

- Shake and rattle phases come from separate per-object random streams, so the
  rotation and the jitter are not locked together.
- `measure.light_factor` is split into `lightness` (1.0 for the smallest object
  in the selection, 0.0 for the largest) and `light_factor` (lightness mapped
  through *Heaviest Effect*), because amplitude and speed read the same
  lightness through different curves.
- The panel has a dedicated **Shake** section.
- `tools/check.py` covers the new behaviour: that Speed tracks the frame rate,
  that lighter objects come out faster, that objects do not share a rate, that
  shake outreaches lift, and that the octave sum still peaks at exactly *Tilt
  Amount*.

## [1.2.0] - 2026-08-27

### Fixed

- **Apply crashed with `RuntimeError: Keyframe not in F-Curve`.** After
  creating a driver, `add_driver` stripped any keyframes off the new F-curve by
  iterating a `list()` snapshot and calling `remove()` on each. Removing from a
  live Blender collection reallocates it, so every reference after the first
  was stale. It now clears the collection in place, and the whole cleanup is
  wrapped so this nicety can never abort an Apply again.

### Changed

- **The repository root is now the add-on package**, so GitHub's *Code →
  Download ZIP* archive installs in Blender as-is. The modules used to live in
  a nested `storm_trash_fx/` folder, which meant the zip extracted to
  `storm_trash_fx-main/` with no `__init__.py` at its root and Blender
  installed nothing, reporting `Modules Installed ()`. The installed module is
  named after the zip folder (`storm_trash_fx-main`); nothing depends on the
  package name.
- `tools/check.py` loads the add-on by path under a synthetic name rather than
  importing it by directory name, which now varies.
- Split the single ~500-line file into one module per concern - `channels` (the
  four delta channels the add-on owns), `measure` (reading the scene), `rig`
  (driver expressions), `props`, `operators`, `ui` - layered one-way so nothing
  reaches back up. Cross-module helpers lost their leading underscore.
- `__init__.py` reloads its submodules when the add-on is re-enabled, so edits
  take effect without restarting Blender.
- The panel `draw()` is split into one method per section.
- `bl_info["author"]` is now `vickussya`.

### Added

- `tools/check.py` - stubs `bpy` and `mathutils`, imports every module, and
  asserts the driver expressions, weight curve, phase seeding and channel
  ownership. Runs without Blender.

### Removed

- **Running the add-on from Blender's Text Editor.** A package cannot be run as
  a loose script; install the zip instead.

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
