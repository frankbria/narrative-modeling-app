/**
 * The body the Model Training stage posts must match `POST /ml/train`'s request
 * model, which forbids undeclared fields (#969). `trainModelRequestSchema.json` is
 * the API's own JSON schema, captured and kept current by the backend's
 * `test_train_request_schema_fixture.py`.
 */
import schema from '@/__tests__/fixtures/trainModelRequestSchema.json';
import { trainRequest } from '@/components/model-training/useTrainingRun';
import { violations, type Root } from '@/__tests__/utils/jsonSchema';

const root = schema as Root;
const choice = { targetColumn: 'bought', mode: 'quick' as const };

describe('the training request matches the API request model', () => {
  it('with nothing kept and nothing left out', () => {
    const body = trainRequest('ds1', choice, { keep: [], exclude: [] });

    expect(body).toEqual({
      dataset_id: 'ds1',
      target_column: 'bought',
      training_config: { training_mode: 'quick' },
    });
    expect(violations(body, root, root)).toEqual([]);
  });

  it('with the columns left out in Feature Engineering', () => {
    const body = trainRequest('ds1', choice, { keep: [], exclude: ['region'] });

    expect(body.feature_config).toEqual({ exclude_columns: ['region'] });
    expect(violations(body, root, root)).toEqual([]);
  });

  it('with columns kept on a retrain, and columns left out', () => {
    const body = trainRequest('ds1', choice, { keep: ['order_no'], exclude: ['region'] });

    expect(body.feature_config).toEqual({ keep_columns: ['order_no'], exclude_columns: ['region'] });
    expect(violations(body, root, root)).toEqual([]);
  });

  it('with the interaction switch on, and nothing sent when it is off (#974)', () => {
    const on = trainRequest('ds1', choice, { keep: [], exclude: [], interactions: true });
    const off = trainRequest('ds1', choice, { keep: [], exclude: [], interactions: false });

    expect(on.feature_config).toEqual({ create_interactions: true });
    expect(violations(on, root, root)).toEqual([]);
    expect(off.feature_config).toBeUndefined();
  });

  it('a knob the API does not declare is caught', () => {
    const body = { ...trainRequest('ds1', choice, { keep: [], exclude: [] }), feature_config: { drop_columns: ['region'] } };

    // feature_config is "the model, or null": a body that is neither names the field.
    expect(violations(body, root, root)).toEqual(['$.feature_config: matches no allowed shape']);
  });
});
