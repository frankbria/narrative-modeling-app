import { planOrder, runOrder, PipelineOrderError } from '@/components/transformation/runOrder';

/**
 * #862: Preview and Apply sent the steps in the order they were added and ignored the
 * arrows drawn between them. The order is now the drawn chain when one is drawn, and
 * the listed order when nothing is drawn.
 */
const step = (id: string, label = id.toUpperCase()) => ({ id, data: { label } });
const edge = (source: string, target: string) => ({ source, target });
const [a, b, c] = [step('a'), step('b'), step('c')];
const ids = (nodes: { id: string }[]) => nodes.map((n) => n.id);

describe('runOrder', () => {
  it('is the listed order when nothing is drawn', () => {
    expect(ids(runOrder([a, b, c], []))).toEqual(['a', 'b', 'c']);
    expect(runOrder([], [])).toEqual([]);
  });

  it('follows the arrows when they make one chain, whatever order the steps were added in', () => {
    expect(ids(runOrder([a, b, c], [edge('c', 'a'), edge('a', 'b')]))).toEqual(['c', 'a', 'b']);
    expect(ids(runOrder([a, b, c], [edge('b', 'c'), edge('a', 'b')]))).toEqual(['a', 'b', 'c']);
  });

  it('ignores an arrow left behind by a step that is gone', () => {
    expect(ids(runOrder([a, b], [edge('a', 'b'), edge('b', 'gone'), edge('gone', 'a')]))).toEqual(['a', 'b']);
  });

  it.each([
    ['a step left out of the chain', [edge('a', 'b')], /C is not connected/],
    ['one step feeding two', [edge('a', 'b'), edge('a', 'c')], /A leads to more than one step/],
    ['two steps feeding one', [edge('a', 'c'), edge('b', 'c')], /more than one step leads to C/],
    ['a loop', [edge('a', 'b'), edge('b', 'c'), edge('c', 'a')], /loop/],
    ['a loop beside a chain', [edge('a', 'a')], /loop/],
  ])('refuses %s', (_name, edges, said) => {
    expect(() => runOrder([a, b, c], edges)).toThrow(PipelineOrderError);
    expect(() => runOrder([a, b, c], edges)).toThrow(said);
  });
});

describe('planOrder', () => {
  it('gives the run order and no problem for a chain', () => {
    const plan = planOrder([a, b, c], [edge('c', 'a'), edge('a', 'b')]);
    expect(ids(plan.nodes)).toEqual(['c', 'a', 'b']);
    expect(plan.problem).toBeNull();
  });

  it('keeps the listed order and names the problem when the arrows do not make a chain', () => {
    const plan = planOrder([a, b, c], [edge('a', 'b'), edge('a', 'c')]);
    expect(ids(plan.nodes)).toEqual(['a', 'b', 'c']);
    expect(plan.problem).toMatch(/not one chain.*A leads to more than one step.*Chain view/);
  });
});
