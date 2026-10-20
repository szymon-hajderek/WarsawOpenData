import { describe, expect, it } from 'vitest';
import { applyHeading, userArrowHtml } from './userArrow';

const marker = () => {
  const el = document.createElement('div');
  el.innerHTML = userArrowHtml('red');
  return el;
};
const arrow = (el: HTMLElement) => el.querySelector<HTMLElement>('.user-heading')!;
const dot = (el: HTMLElement) => el.querySelector<HTMLElement>('.user-dot')!;

describe('user arrow', () => {
  it('shows a dot while the heading is unknown', () => {
    const el = marker();
    applyHeading(el, null);
    expect(arrow(el).style.display).toBe('none');
    expect(dot(el).style.display).toBe('block');
  });

  it('turns the arrow by the shortest way, the first time without animation', () => {
    const el = marker();
    applyHeading(el, 350);
    expect(arrow(el).style.display).toBe('block');
    expect(dot(el).style.display).toBe('none');
    expect(arrow(el).style.transform).toBe('rotate(-10deg)');
    expect(arrow(el).style.transition).toBe('none');
    applyHeading(el, 10);
    expect(arrow(el).style.transform).toBe('rotate(10deg)');
    expect(arrow(el).style.transition).toContain('transform');
  });

  it('subtracts the rotation of the 3D map', () => {
    const el = marker();
    applyHeading(el, 90, 30);
    expect(arrow(el).style.transform).toBe('rotate(60deg)');
  });
});
