/**
 * The body the settings switch sends must match `PUT /users/me/notification-preferences`'s
 * request model, which forbids undeclared fields (#494). The fixture is the API's own JSON
 * schema, captured by the backend's `test_notification_preferences_schema_fixture.py`.
 */
import schema from '@/__tests__/fixtures/notificationPreferencesSchema.json';
import { jobEmailsBody } from '@/lib/services/notificationPreferences';
import { violations, type Root } from '@/__tests__/utils/jsonSchema';

const root = schema as Root;

describe('the notification preference body matches the API request model', () => {
  it.each([true, false])('with job emails %s', (enabled) => {
    expect(violations(jobEmailsBody(enabled), root, root)).toEqual([]);
  });

  it('is refused by the schema under any other key', () => {
    expect(violations({ jobEmails: true }, root, root)).not.toEqual([]);
  });
});
