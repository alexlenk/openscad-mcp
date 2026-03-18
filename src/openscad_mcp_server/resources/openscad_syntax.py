"""OpenSCAD syntax reference resource (openscad://syntax-reference)."""

from __future__ import annotations

RESOURCE_URI = "openscad://syntax-reference"
RESOURCE_NAME = "OpenSCAD Syntax Reference"
RESOURCE_DESCRIPTION = (
    "Comprehensive OpenSCAD language reference covering primitives, "
    "transformations, boolean operations, module definitions, and variable scoping."
)


def get_syntax_reference() -> str:
    """Return the full OpenSCAD syntax reference text."""
    return _SYNTAX_REFERENCE


_SYNTAX_REFERENCE = """\
# OpenSCAD Language Reference

## Primitive Shapes

### cube
  cube(size)              — cube with equal sides
  cube([x, y, z])         — rectangular box
  cube(size, center=true) — centered on origin

### sphere
  sphere(r)               — sphere with radius r
  sphere(d=10)            — sphere with diameter
  sphere(r, $fn=64)       — smooth sphere (more fragments)

### cylinder
  cylinder(h, r)                    — cylinder with height h, radius r
  cylinder(h, r1, r2)              — cone/frustum (r1=bottom, r2=top)
  cylinder(h, d=10)                — using diameter
  cylinder(h, r, center=true)      — centered on Z axis
  cylinder(h, r, $fn=6)            — hexagonal prism

### polyhedron
  polyhedron(points, faces)         — arbitrary solid from vertices and face indices

### text (2D)
  text("string", size=10, font="Liberation Sans")

### polygon (2D)
  polygon(points)                   — 2D shape from vertex list
  polygon(points, paths)            — with explicit paths

### circle (2D)
  circle(r)
  circle(d=10)

### square (2D)
  square(size)
  square([x, y], center=true)

## Transformations

### translate
  translate([x, y, z]) object;

### rotate
  rotate([x, y, z]) object;         — Euler angles in degrees
  rotate(a, v=[x,y,z]) object;      — angle a around axis v

### scale
  scale([x, y, z]) object;

### mirror
  mirror([x, y, z]) object;         — mirror across plane through origin

### multmatrix
  multmatrix(m) object;             — 4x4 affine transformation matrix

### resize
  resize([x, y, z]) object;         — resize to exact dimensions

### color
  color("red") object;
  color([r, g, b, a]) object;       — RGBA values 0.0–1.0

### offset (2D)
  offset(r=1) 2d_object;            — round offset
  offset(delta=1) 2d_object;        — sharp offset

### hull
  hull() { objects; }               — convex hull of children

### minkowski
  minkowski() { objects; }          — Minkowski sum of children

## Boolean Operations

### union
  union() { a(); b(); }             — combine shapes (default for multiple children)

### difference
  difference() { base(); cut(); }   — subtract subsequent children from first child

### intersection
  intersection() { a(); b(); }      — keep only overlapping volume

## Extrusion (2D to 3D)

### linear_extrude
  linear_extrude(height, center=false, twist=0, slices=20, scale=1.0)
    2d_shape();

### rotate_extrude
  rotate_extrude(angle=360, $fn=64)
    2d_shape();                      — 2D shape must be in positive X half-plane

## Module Definitions

### Defining a module
  module my_module(param1, param2=default_value) {
      // body using param1, param2
      cube(param1);
      translate([0, 0, param2]) sphere(5);
  }

### Calling a module
  my_module(10, param2=20);

### children()
  module wrapper() {
      translate([10, 0, 0]) children();   — passes child objects through
  }
  wrapper() cube(5);

## Functions

### Defining a function
  function add(a, b) = a + b;

### Built-in math functions
  abs, sign, sin, cos, tan, asin, acos, atan, atan2
  floor, ceil, round, ln, log, exp, sqrt, pow
  min, max, norm, cross

### List functions
  len(list), concat(a, b), lookup(key, table)

## Variable Scoping

- Variables are lexically scoped within modules and blocks.
- A variable assigned multiple times in the same scope takes the LAST assigned value
  (OpenSCAD evaluates all assignments before execution).
- Special variables starting with $ are dynamically scoped:
  $fn — number of fragments for curves
  $fa — minimum angle for fragments
  $fs — minimum size for fragments
  $t  — animation time (0.0–1.0)
- Use `let()` for local bindings:
  let(x = 10, y = x + 5) cube([x, y, 1]);

## Include and Use

### include
  include <filename.scad>           — executes all code in the file (modules + top-level geometry)

### use
  use <filename.scad>               — imports modules and functions only (no top-level geometry)

## Control Flow

### for loop
  for (i = [0:10]) translate([i*5, 0, 0]) cube(3);
  for (i = [0:2:10]) ...            — step of 2
  for (p = [[0,0],[10,0],[5,10]]) translate(p) sphere(1);

### if / else
  if (condition) { ... } else { ... }

### intersection_for
  intersection_for(i = [0:2]) rotate([0, 0, i*60]) cube(10, center=true);

### conditional expression
  x = (a > b) ? a : b;

## Modifier Characters

  *  — disable (comment out) subtree
  !  — show only this subtree
  #  — highlight / debug (transparent red)
  %  — transparent / background

## Render Hint

  render(convexity=2) { ... }       — force CGAL rendering for preview
"""
