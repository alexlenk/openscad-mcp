"""Common OpenSCAD pitfalls resource (openscad://pitfalls)."""

from __future__ import annotations

RESOURCE_URI = "openscad://pitfalls"
RESOURCE_NAME = "OpenSCAD Common Pitfalls"
RESOURCE_DESCRIPTION = (
    "Common OpenSCAD pitfalls and error patterns including manifold errors, "
    "z-fighting, boolean order, coordinate mismatches, and missing $fn."
)


def get_pitfalls() -> str:
    """Return the common pitfalls reference text."""
    return _PITFALLS


_PITFALLS = """\
# Common OpenSCAD Pitfalls

## 1. Non-Manifold Geometry

Manifold errors occur when the resulting solid has invalid topology — edges shared
by more than two faces, self-intersecting surfaces, or zero-thickness walls.

Symptoms:
- OpenSCAD warnings: "Object may not be a valid 2-manifold"
- STL slicers reject the file or produce unexpected infill

Common causes:
- Two solids sharing exactly one edge or face (touching but not overlapping)
- Boolean operations on coplanar faces
- Zero-thickness walls from subtracting a shape that exactly matches a face

Fix:
- Ensure boolean operands overlap by a small epsilon (e.g., 0.01 mm)
- Use `render()` to force CGAL evaluation and catch errors early

Example — BAD:
  difference() {
      cube(10);
      translate([10, 0, 0]) cube(10);  // shares a face exactly
  }

Example — GOOD:
  difference() {
      cube(10);
      translate([9.99, 0, 0]) cube(10);  // slight overlap
  }

## 2. Z-Fighting

Z-fighting happens when two surfaces occupy the same plane, causing flickering
in preview and unpredictable boolean results.

Common causes:
- Cutting a hole with a shape that starts exactly at the surface
- Stacking objects without any overlap

Fix:
- Extend cutting shapes slightly beyond the surface (add 0.01 to height,
  translate by -0.005)

Example — BAD:
  difference() {
      cube([20, 20, 5]);
      translate([5, 5, 0]) cylinder(h=5, r=3);  // bottom face is coplanar
  }

Example — GOOD:
  difference() {
      cube([20, 20, 5]);
      translate([5, 5, -0.01]) cylinder(h=5.02, r=3);  // extends past both faces
  }

## 3. Boolean Operation Order

The order of children in `difference()` and `intersection()` matters.
The first child is the base; subsequent children are subtracted or intersected.

Common mistake:
- Putting the cutting shape first in `difference()`
- Forgetting that `union()` is implicit when multiple shapes are at the same level

Example — BAD (subtracts cube from cylinder instead of the reverse):
  difference() {
      cylinder(h=5, r=3);
      cube([20, 20, 10], center=true);
  }

## 4. Coordinate System Mismatches Between Libraries

Different OpenSCAD libraries may use different conventions:
- Some libraries assume Y-up, others Z-up
- Some use millimeters, others inches
- Module origins may be at the bottom, center, or corner

Fix:
- ALWAYS read library source code before using it
- Check the coordinate system and unit conventions
- Apply `rotate()` or `scale()` to align conventions
- Document the conventions you discovered before writing code

## 5. Missing $fn for Smooth Curves

OpenSCAD defaults to a low fragment count for circles and spheres, producing
visibly faceted geometry.

Common mistake:
- Forgetting to set `$fn` and getting a hexagonal "circle"
- Setting `$fn` too high globally, causing extremely slow renders

Fix:
- Set `$fn` explicitly on curved primitives: `sphere(r=10, $fn=64)`
- Use `$fn=32` to `$fn=128` depending on the required smoothness
- For final renders use higher values; for preview use lower values
- Alternatively set `$fa` and `$fs` for adaptive resolution:
  $fa = 1;   // minimum 1 degree per fragment
  $fs = 0.5; // minimum 0.5 mm per fragment

## 6. Variable Scoping Surprises

OpenSCAD uses a unique scoping model where the LAST assignment in a scope wins,
and all assignments are evaluated before any geometry.

Example — SURPRISING:
  x = 5;
  cube(x);    // uses x = 10, not 5!
  x = 10;

Fix:
- Assign each variable only once per scope
- Use `let()` for local bindings inside expressions
- Use module parameters instead of relying on outer variables

## 7. 2D vs 3D Context Errors

Some operations only work in 2D or 3D contexts.

Common mistakes:
- Using `circle()` where `sphere()` is needed (or vice versa)
- Forgetting `linear_extrude()` to convert 2D shapes to 3D
- Using `rotate_extrude()` with geometry in the negative X half-plane

Fix:
- `rotate_extrude()` requires the 2D profile to be entirely in the positive X region
- Always extrude 2D shapes before applying 3D boolean operations

## 8. Include vs Use Confusion

- `include <file.scad>` — runs ALL code in the file (modules AND top-level geometry)
- `use <file.scad>` — imports modules and functions ONLY (no top-level geometry)

Common mistake:
- Using `include` when you only want the modules, causing unwanted geometry
  to appear in your model

Fix:
- Prefer `use` for libraries; use `include` only when you need the file's
  top-level geometry or variable definitions
"""
