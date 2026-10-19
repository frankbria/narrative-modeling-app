import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TransformationConfigDialog } from '@/components/transformation/TransformationConfigDialog';

type Schema = Record<string, Record<string, unknown>>;

// The form seeds from `existingConfig` when the dialog goes from closed to open
// (not on a first render that is already open), so open it that way. A value the
// form's own inputs could never produce (a string in a number slot) then still
// reaches validation.
function renderWith(schema: Schema, parameters: Record<string, unknown>, extra = {}) {
  const onAdd = jest.fn();
  const onOpenChange = jest.fn();
  const element = (open: boolean) => (
    <TransformationConfigDialog
      open={open}
      onOpenChange={onOpenChange}
      transformationType="t"
      transformationLabel="T"
      transformationDescription="d"
      parametersSchema={schema}
      availableColumns={['id', 'name', 'age']}
      datasetId="ds"
      onAdd={onAdd}
      existingConfig={existing}
      {...extra}
    />
  );
  const existing = { type: 't', parameters };
  const view = render(element(false));
  view.rerender(element(true));
  return { onAdd, onOpenChange };
}

const submit = async () => {
  await userEvent.setup().click(screen.getByRole('button', { name: /to pipeline/i }));
};

describe('TransformationConfigDialog validation messages', () => {
  it('names a required text field that is empty', async () => {
    const { onAdd } = renderWith({ fill_value: { type: 'string' } }, {});
    await submit();
    expect(await screen.findByText('Fill Value is required')).toBeInTheDocument();
    expect(onAdd).not.toHaveBeenCalled();
  });

  it('treats an empty array as missing for a required field', async () => {
    renderWith({ cols: { type: 'array', items: { type: 'string' } } }, { cols: [] });
    await submit();
    expect(await screen.findByText('Cols is required')).toBeInTheDocument();
  });

  it('does not require a field with required:false or a default', async () => {
    const { onAdd } = renderWith(
      { a: { type: 'string', required: false }, b: { type: 'string', default: 'x' } },
      {}
    );
    await submit();
    await waitFor(() => expect(onAdd).toHaveBeenCalledTimes(1));
  });

  it('rejects a non-array value for an array field', async () => {
    renderWith({ cols: { type: 'array', items: { type: 'number' } } }, { cols: 'a' });
    await submit();
    expect(await screen.findByText('Cols must be an array')).toBeInTheDocument();
  });

  it('rejects a non-numeric string for a number field', async () => {
    renderWith({ n: { type: 'number' } }, { n: 'abc' });
    await submit();
    expect(await screen.findByText('N must be a number')).toBeInTheDocument();
  });

  it('accepts a numeric string for a number field without changing it', async () => {
    const { onAdd } = renderWith({ n: { type: 'number' } }, { n: '12' });
    await submit();
    await waitFor(() => expect(onAdd).toHaveBeenCalledTimes(1));
    expect(onAdd).toHaveBeenCalledWith({ type: 't', parameters: { n: '12' } });
  });

  it('rejects a non-string value for a string field', async () => {
    renderWith({ s: { type: 'string' } }, { s: 5 });
    await submit();
    expect(await screen.findByText('S must be text')).toBeInTheDocument();
  });

  it('does not type-check an integer field', async () => {
    const { onAdd } = renderWith({ i: { type: 'integer' } }, { i: 'abc' });
    await submit();
    await waitFor(() => expect(onAdd).toHaveBeenCalledTimes(1));
  });

  it('lists the allowed values when an enum value is not among them', async () => {
    renderWith({ method: { type: 'string', enum: ['mean', 'median'] } }, { method: 'mode' });
    await submit();
    expect(await screen.findByText('Method must be one of: mean, median')).toBeInTheDocument();
  });

  it('enforces a minimum and a maximum on numbers', async () => {
    renderWith({ p: { type: 'number', minimum: 5 } }, { p: 1 });
    await submit();
    expect(await screen.findByText('P must be at least 5')).toBeInTheDocument();
  });

  it('reports the maximum when the number is above it', async () => {
    renderWith({ p: { type: 'number', maximum: 5 } }, { p: 9 });
    await submit();
    expect(await screen.findByText('P must be no more than 5')).toBeInTheDocument();
  });

  it('accepts a number on the bounds', async () => {
    const { onAdd } = renderWith({ p: { type: 'number', minimum: 5, maximum: 5 } }, { p: 5 });
    await submit();
    await waitFor(() => expect(onAdd).toHaveBeenCalledTimes(1));
  });

  it('lets an enum failure win over a type failure', async () => {
    renderWith({ s: { type: 'string', enum: ['a'] } }, { s: 7 });
    await submit();
    expect(await screen.findByText('S must be one of: a')).toBeInTheDocument();
    expect(screen.queryByText('S must be text')).not.toBeInTheDocument();
  });

  it('turns snake_case and camelCase keys into spaced, capitalised names', async () => {
    renderWith({ fill_value_now: { type: 'string' }, keepAll: { type: 'string' } }, {});
    await submit();
    expect(await screen.findByText('Fill Value Now is required')).toBeInTheDocument();
    expect(screen.getByText('Keep All is required')).toBeInTheDocument();
  });

  it('reports every failing field at once', async () => {
    renderWith({ a: { type: 'string' }, b: { type: 'string' } }, {});
    await submit();
    expect(await screen.findByText('A is required')).toBeInTheDocument();
    expect(screen.getByText('B is required')).toBeInTheDocument();
  });
});

describe('TransformationConfigDialog behaviour', () => {
  it('clears a field error as soon as that field changes, leaving other errors', async () => {
    const user = userEvent.setup();
    renderWith({ a: { type: 'string', title: 'Alpha' }, b: { type: 'string', title: 'Beta' } }, {});
    await submit();
    await screen.findByText('A is required');
    await user.type(screen.getByLabelText(/Alpha/), 'x');
    expect(screen.queryByText('A is required')).not.toBeInTheDocument();
    expect(screen.getByText('B is required')).toBeInTheDocument();
  });

  it('links an invalid field to its error text', async () => {
    renderWith({ a: { type: 'string', title: 'Alpha' } }, {});
    await submit();
    const input = screen.getByLabelText(/Alpha/);
    await waitFor(() => expect(input).toHaveAttribute('aria-invalid', 'true'));
    expect(input).toHaveAttribute('aria-describedby', 'a-error');
    expect(document.getElementById('a-error')).toHaveTextContent('A is required');
  });

  it('stores a typed number as a number and an emptied one as an empty string', async () => {
    const user = userEvent.setup();
    const { onAdd } = renderWith({ n: { type: 'number', required: false } }, {});
    const input = screen.getByRole('spinbutton');
    await user.type(input, '7');
    await submit();
    await waitFor(() => expect(onAdd).toHaveBeenLastCalledWith({ type: 't', parameters: { n: 7 } }));
    await user.clear(input);
    await submit();
    await waitFor(() => expect(onAdd).toHaveBeenLastCalledWith({ type: 't', parameters: { n: '' } }));
  });

  it('gives an integer field a step of 1 and a number field any', () => {
    renderWith({ i: { type: 'integer', title: 'Int' }, f: { type: 'number', title: 'Flt' } }, {});
    expect(screen.getByLabelText(/Int/)).toHaveAttribute('step', '1');
    expect(screen.getByLabelText(/Flt/)).toHaveAttribute('step', 'any');
  });

  it('stores a checked boolean and shows no required star for it', async () => {
    const user = userEvent.setup();
    const { onAdd } = renderWith({ flag: { type: 'boolean', title: 'Flag' } }, {});
    expect(screen.queryByText('*')).not.toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: /Flag/ }));
    await submit();
    await waitFor(() => expect(onAdd).toHaveBeenCalledWith({ type: 't', parameters: { flag: true } }));
  });

  it('shows a star only for fields that are required without a default', () => {
    renderWith(
      {
        a: { type: 'string', title: 'Aa' },
        b: { type: 'string', title: 'Bb', required: false },
        c: { type: 'string', title: 'Cc', default: 'x' },
      },
      {}
    );
    expect(screen.getAllByText('*')).toHaveLength(1);
  });

  it('turns a string field into a column dropdown when its name mentions a column', () => {
    renderWith({ target_column: { type: 'string' }, plain: { type: 'string', title: 'Plain' } }, {});
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getByLabelText(/Plain/)).toHaveAttribute('type', 'text');
  });

  it('turns a string field into a column dropdown when its title or description mentions a column', () => {
    renderWith(
      {
        a: { type: 'string', title: 'Pick a Column' },
        b: { type: 'string', description: 'which column to use' },
      },
      {}
    );
    expect(screen.getAllByRole('combobox')).toHaveLength(2);
  });

  it('keeps a text input for a column-named field when the dataset has no columns', () => {
    renderWith({ target_column: { type: 'string', title: 'Target' } }, {}, { availableColumns: [] });
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Target/)).toHaveAttribute('type', 'text');
  });

  it('uses the schema description as a placeholder, with a default per input kind', () => {
    renderWith(
      {
        t: { type: 'string', title: 'Tt' },
        n: { type: 'number', title: 'Nn' },
        m: { type: 'array', items: { type: 'string' }, title: 'Mm', required: false },
      },
      {}
    );
    expect(screen.getByPlaceholderText('Enter value')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter a number')).toBeInTheDocument();
    expect(screen.getByText('Select columns...')).toBeInTheDocument();
  });

  it('shows a failed submit and keeps the dialog open', async () => {
    const onAdd = jest.fn(() => {
      throw new Error('boom');
    });
    const { onOpenChange } = renderWith({}, {}, { onAdd });
    await submit();
    expect(await screen.findByText('boom')).toBeInTheDocument();
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it('falls back to a generic message when the failure is not an Error', async () => {
    const onAdd = jest.fn(() => {
      throw 'nope';
    });
    renderWith({}, {}, { onAdd });
    await submit();
    expect(await screen.findByText('Failed to add transformation')).toBeInTheDocument();
  });

  it('falls back to a generic preview message when the failure is not an Error', async () => {
    const onPreview = jest.fn().mockRejectedValue('nope');
    renderWith({}, {}, { onPreview });
    await userEvent.setup().click(screen.getByRole('button', { name: /preview/i }));
    expect(await screen.findByText('Preview failed')).toBeInTheDocument();
  });

  it('previews the entered parameters under the transformation type', async () => {
    const onPreview = jest.fn().mockResolvedValue(undefined);
    renderWith({ a: { type: 'string' } }, { a: 'x' }, { onPreview });
    await userEvent.setup().click(screen.getByRole('button', { name: /preview/i }));
    await waitFor(() => expect(onPreview).toHaveBeenCalledWith({ type: 't', parameters: { a: 'x' } }));
  });

  it('does not preview invalid parameters', async () => {
    const onPreview = jest.fn();
    renderWith({ a: { type: 'string' } }, {}, { onPreview });
    await userEvent.setup().click(screen.getByRole('button', { name: /preview/i }));
    expect(await screen.findByText('A is required')).toBeInTheDocument();
    expect(onPreview).not.toHaveBeenCalled();
  });

  it('does nothing on Add or Preview without a transformation type', async () => {
    const onPreview = jest.fn();
    const { onAdd } = renderWith({}, {}, { transformationType: null, onPreview });
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /to pipeline/i }));
    await user.click(screen.getByRole('button', { name: /preview/i }));
    expect(onAdd).not.toHaveBeenCalled();
    expect(onPreview).not.toHaveBeenCalled();
  });

  it('seeds the form from the existing config on open and resets when reopened', () => {
    const props = {
      onOpenChange: jest.fn(),
      transformationType: 't',
      transformationLabel: 'T',
      transformationDescription: 'd',
      parametersSchema: { a: { type: 'string', title: 'Alpha' } },
      availableColumns: [],
      datasetId: 'ds',
      onAdd: jest.fn(),
    };
    const existing = { type: 't', parameters: { a: 'seeded' } };
    const { rerender } = render(<TransformationConfigDialog {...props} open={false} existingConfig={existing} />);
    rerender(<TransformationConfigDialog {...props} open existingConfig={existing} />);
    expect(screen.getByLabelText(/Alpha/)).toHaveValue('seeded');
    fireEvent.change(screen.getByLabelText(/Alpha/), { target: { value: 'edited' } });
    rerender(<TransformationConfigDialog {...props} open={false} existingConfig={existing} />);
    rerender(<TransformationConfigDialog {...props} open existingConfig={existing} />);
    expect(screen.getByLabelText(/Alpha/)).toHaveValue('seeded');
  });

  it('wraps focus from the last button to the first input on Tab, and back on Shift+Tab', async () => {
    renderWith({ a: { type: 'string', title: 'Alpha' } }, { a: 'x' });
    const first = screen.getByLabelText(/Alpha/);
    await waitFor(() => expect(first).toHaveFocus());
    const last = screen.getByRole('button', { name: /to pipeline/i });
    last.focus();
    fireEvent.keyDown(last, { key: 'Tab' });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: 'Tab', shiftKey: true });
    expect(last).toHaveFocus();
  });

  it('treats the Delete button as the last stop of the focus trap', async () => {
    renderWith({ a: { type: 'string', title: 'Alpha' } }, { a: 'x' }, { onDelete: jest.fn() });
    const first = screen.getByLabelText(/Alpha/);
    await waitFor(() => expect(first).toHaveFocus());
    const del = screen.getByRole('button', { name: /delete this transformation/i });
    del.focus();
    fireEvent.keyDown(del, { key: 'Tab' });
    expect(first).toHaveFocus();
  });
});

describe('TransformationConfigDialog multi-select', () => {
  const schema = { cols: { type: 'array', items: { type: 'string' }, title: 'Cols' } };

  it('filters by the search text, selects all matches, then deselects them', async () => {
    const user = userEvent.setup();
    const { onAdd } = renderWith(schema, {});
    await user.click(screen.getByText('Select columns...'));
    await user.type(screen.getByLabelText('Search columns'), 'a');
    expect(screen.getAllByRole('option')).toHaveLength(2);
    await user.click(screen.getByText(/Select All/));
    expect(screen.getByText('2 selected')).toBeInTheDocument();
    expect(screen.getByText(/Deselect All/)).toBeInTheDocument();
    await user.click(screen.getByText(/Deselect All/));
    expect(screen.getByText('Select columns...')).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: /name/ }));
    await user.click(screen.getByRole('checkbox', { name: /age/ }));
    await user.click(screen.getByRole('checkbox', { name: /name/ }));
    await submit();
    await waitFor(() => expect(onAdd).toHaveBeenCalledWith({ type: 't', parameters: { cols: ['age'] } }));
  });

  // The trigger is a button, where this repo's jsx-a11y rule (role-supports-aria-props) flags
  // aria-invalid; it points at its error text with aria-describedby instead.
  it('links an invalid multi-select to its error text', async () => {
    renderWith({ cols: { type: 'array', items: { type: 'string' } } }, { cols: [] });
    await submit();
    await screen.findByText('Cols is required');
    const trigger = screen.getByRole('button', { name: /select columns/i });
    expect(trigger).toHaveAttribute('aria-describedby', 'cols-error');
    expect(document.getElementById('cols-error')).toHaveTextContent('Cols is required');
  });

  it('says so when the search matches no column', async () => {
    const user = userEvent.setup();
    renderWith(schema, {});
    await user.click(screen.getByText('Select columns...'));
    await user.type(screen.getByLabelText('Search columns'), 'zzz');
    expect(screen.getByText('No columns found')).toBeInTheDocument();
  });

  it('closes the list when the backdrop is clicked', async () => {
    const user = userEvent.setup();
    renderWith(schema, {});
    await user.click(screen.getByText('Select columns...'));
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    await user.click(document.querySelector('.absolute.top-0.left-0.right-0.bottom-0') as Element);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('marks the trigger red when the field has an error', async () => {
    renderWith(schema, {});
    await submit();
    await screen.findByText('Cols is required');
    expect(screen.getByRole('button', { name: /select columns/i })).toHaveClass('border-red-500');
  });
});
