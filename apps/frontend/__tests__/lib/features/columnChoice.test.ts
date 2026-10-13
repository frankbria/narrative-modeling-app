import {
  choiceOf,
  excludedFromTraining,
  recordedChoice,
  sameChoice,
  startingSelection,
} from '@/lib/features/columnChoice';

const COLUMNS = ['plan', 'region', 'spend', 'bought'];

describe('the Feature Engineering stage choice', () => {
  it('records the columns selected and the ones left out, in the dataset order', () => {
    expect(choiceOf(COLUMNS, ['spend', 'plan'])).toEqual({
      selectedFeatures: ['plan', 'spend'],
      excludedFeatures: ['region', 'bought'],
    });
  });

  it('reads back what a completed stage recorded', () => {
    const recorded = choiceOf(COLUMNS, ['plan', 'spend']);
    expect(recordedChoice({ ...recorded, timestamp: 'x' })).toEqual(recorded);
  });

  it.each([undefined, null, 'x', {}, { selectedFeatures: 'plan' }, { selectedFeatures: [1, 2] }])(
    'treats %p as no recorded choice',
    (stageData) => {
      expect(recordedChoice(stageData)).toBeNull();
    },
  );

  it('reads a stage completed before exclusions were recorded as leaving nothing out', () => {
    expect(recordedChoice({ selectedFeatures: ['plan', 'spend'] })).toEqual({
      selectedFeatures: ['plan', 'spend'],
      excludedFeatures: [],
    });
  });

  it('starts with every column selected', () => {
    expect(startingSelection(COLUMNS, null)).toEqual(COLUMNS);
  });

  it('starts from the recorded choice, and selects a column that is new since', () => {
    const recorded = { selectedFeatures: ['plan', 'spend'], excludedFeatures: ['region', 'gone'] };
    expect(startingSelection(COLUMNS, recorded)).toEqual(['plan', 'spend', 'bought']);
  });

  it('knows a selection that is what was recorded, whatever the order', () => {
    const recorded = choiceOf(COLUMNS, ['plan', 'spend']);
    expect(sameChoice(recorded, ['spend', 'plan'])).toBe(true);
    expect(sameChoice(recorded, ['plan'])).toBe(false);
    expect(sameChoice(recorded, ['plan', 'region'])).toBe(false);
    expect(sameChoice(null, ['plan', 'spend'])).toBe(false);
  });

  it('leaves the recorded columns out of training, but never the target', () => {
    const stageData = choiceOf(COLUMNS, ['plan', 'spend']);
    expect(excludedFromTraining(stageData, 'spend')).toEqual(['region', 'bought']);
    expect(excludedFromTraining(stageData, 'bought')).toEqual(['region']);
    expect(excludedFromTraining(undefined, 'bought')).toEqual([]);
  });
});
