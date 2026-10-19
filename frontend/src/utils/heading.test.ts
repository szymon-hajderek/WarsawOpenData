import { describe, expect, it } from 'vitest';
import { addFix, angleDiff, bearing, compassHeading, movementHeading, smoothAngle, unwrapRotation, type Fix } from './heading';

/** A point `m` metres north / east of Warsaw centre. */
const at = (north: number, east: number): [number, number] => [52.23 + north / 111_320, 21.01 + east / (111_320 * Math.cos((52.23 * Math.PI) / 180))];
let clock = 0;
/** A fix 2 s after the previous one. */
const fix = (north: number, east: number, accuracy = 5): Fix => ({ pos: at(north, east), accuracy, time: (clock += 2_000) });

describe('heading helpers', () => {
  it('bearing: north 0, east 90, south 180, west 270', () => {
    expect(bearing(at(0, 0), at(100, 0))).toBeCloseTo(0, 0);
    expect(bearing(at(0, 0), at(0, 100))).toBeCloseTo(90, 0);
    expect(bearing(at(0, 0), at(-100, 0))).toBeCloseTo(180, 0);
    expect(bearing(at(0, 0), at(0, -100))).toBeCloseTo(270, 0);
  });

  it('compass: iOS webkitCompassHeading, Android absolute alpha (counter-clockwise), screen rotation', () => {
    expect(compassHeading({ alpha: 10, webkitCompassHeading: 45 }, 0, false)).toBe(45);
    expect(compassHeading({ alpha: 10, webkitCompassHeading: 45, webkitCompassAccuracy: -1 }, 0, false)).toBeNull();
    expect(compassHeading({ alpha: 90 }, 0, true)).toBe(270);
    expect(compassHeading({ alpha: 90, absolute: true }, 0, false)).toBe(270);
    expect(compassHeading({ alpha: 0 }, 90, true)).toBe(90);
    // a relative alpha is not a compass
    expect(compassHeading({ alpha: 90, absolute: false }, 0, false)).toBeNull();
    expect(compassHeading({ alpha: null }, 0, true)).toBeNull();
  });

  it('movement: GPS jitter while standing still never gives a direction', () => {
    let kept: Fix[] = [];
    for (const [n, e] of [[0, 0], [4, -3], [-5, 2], [3, 6], [-2, -7], [6, 1]]) kept = addFix(kept, fix(n, e));
    expect(kept).toHaveLength(1);
    expect(movementHeading(kept, clock)).toBeNull();
  });

  it('movement: the last 3 fixes farther apart than the GPS error give the direction', () => {
    let kept: Fix[] = [];
    for (let i = 0; i <= 10; i++) kept = addFix(kept, fix(i * 4, i * 4)); // walking north-east, 4 m steps
    expect(kept).toHaveLength(3);
    expect(movementHeading(kept, clock)!).toBeCloseTo(45, 0);
    // turn west: after two well-spaced fixes the direction follows
    for (let i = 1; i <= 8; i++) kept = addFix(kept, fix(40, 40 - i * 4));
    expect(movementHeading(kept, clock)!).toBeCloseTo(270, 0);
  });

  it('movement: a poor fix (30 m error) needs a longer step', () => {
    const kept = addFix([fix(0, 0, 30)], fix(20, 0, 30));
    expect(kept).toHaveLength(1);
    expect(addFix(kept, fix(31, 0, 30))).toHaveLength(2);
  });

  it('movement: a coarse first fix (network location) and Wi-Fi jumps never give a direction', () => {
    let kept = addFix([], fix(0, 0, 800));
    kept = addFix(kept, fix(400, 0, 8));
    expect(movementHeading(kept, clock)).toBeNull();
    kept = addFix(kept, fix(450, 60, 80));
    expect(movementHeading(kept, clock)).toBeNull();
  });

  it('movement: after a stop the direction is unknown again, old fixes are forgotten', () => {
    let kept: Fix[] = [];
    for (let i = 0; i <= 3; i++) kept = addFix(kept, fix(i * 12, 0));
    expect(movementHeading(kept, clock)).toBeCloseTo(0, 0);
    expect(movementHeading(kept, clock + 31_000)).toBeNull();
    // an hour later one drift jump: not combined with the old fixes
    clock += 3_600_000;
    kept = addFix(kept, fix(36, 15));
    expect(kept).toHaveLength(1);
    expect(movementHeading(kept, clock)).toBeNull();
  });

  it('movement: a zigzag of drift is not a direction', () => {
    let kept = addFix([], fix(0, 0));
    kept = addFix(kept, fix(12, 0));
    kept = addFix(kept, fix(1, 1));
    expect(movementHeading(kept, clock)).toBeNull();
  });

  it('compass: landscape on iOS and the old window.orientation -90', () => {
    expect(compassHeading({ alpha: 0, webkitCompassHeading: 10 }, 90, false)).toBe(100);
    expect(compassHeading({ alpha: 0 }, -90, true)).toBe(270);
  });

  it('smoothing and rotation take the short way round north', () => {
    expect(angleDiff(350, 10)).toBe(20);
    expect(smoothAngle(350, 10, 0.5)).toBeCloseTo(0, 5);
    expect(unwrapRotation(350, 10)).toBe(370);
    expect(unwrapRotation(-710, 0)).toBe(-720);
  });
});
