import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import available from '@/__tests__/fixtures/availableTransformations.json';
import TransformationSidebar from '@/components/transformation/TransformationSidebar';
import type { TransformationTypeMeta } from '@/lib/services/pipelineApi';

/** The sidebar lists the registry the API serves (#855), not a hand-kept menu. */
const types = available as TransformationTypeMeta[];

describe('TransformationSidebar', () => {
  it('lists every executable type under its category and adds one on click', async () => {
    const onAdd = jest.fn();
    render(<TransformationSidebar types={types} onAdd={onAdd} />);

    for (const t of types) expect(screen.getByRole('button', { name: `Add ${t.label}` })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: `Add ${types[0].label}` }));
    expect(onAdd).toHaveBeenCalledWith(types[0].type, types[0].label);
  });

  it('filters by the search term', async () => {
    render(<TransformationSidebar types={types} />);
    await userEvent.type(screen.getByPlaceholderText('Search transformations...'), types[0].label);
    expect(screen.getAllByRole('button', { name: /^Add / })).toHaveLength(1);
  });

  it('collapses and expands a category', async () => {
    render(<TransformationSidebar types={types} />);
    const header = screen.getByRole('button', { name: new RegExp(types[0].category) });

    await userEvent.click(header);
    expect(header).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: `Add ${types[0].label}` })).not.toBeInTheDocument();

    await userEvent.click(header);
    expect(screen.getByRole('button', { name: `Add ${types[0].label}` })).toBeInTheDocument();
  });

  it('says so when the list could not be loaded, instead of an empty menu', () => {
    render(<TransformationSidebar types={null} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load the transformations');
  });
});
