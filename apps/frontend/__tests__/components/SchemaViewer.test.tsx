import React from 'react'
import { render, screen } from '@testing-library/react'
import { SchemaViewer } from '@/components/SchemaViewer'

const mockSchema = {
  columns: [
    {
      name: 'id',
      data_type: 'integer',
      nullable: false,
      unique: true,
      cardinality: 100,
      null_count: 0,
      null_percentage: 0.0,
      sample_values: [1, 2, 3, 4, 5]
    },
    {
      name: 'name',
      data_type: 'string',
      nullable: false,
      unique: false,
      cardinality: 95,
      null_count: 0,
      null_percentage: 0.0,
      sample_values: ['John', 'Jane', 'Bob', 'Alice', 'Charlie']
    },
    {
      name: 'email',
      data_type: 'email',
      nullable: true,
      unique: false,
      cardinality: 98,
      null_count: 2,
      null_percentage: 2.0,
      sample_values: ['john@example.com', 'jane@test.com', null, 'bob@mail.com', 'alice@domain.org']
    },
    {
      name: 'age',
      data_type: 'integer',
      nullable: false,
      unique: false,
      cardinality: 25,
      null_count: 0,
      null_percentage: 0.0,
      sample_values: [25, 30, 35, 28, 42]
    },
    {
      name: 'salary',
      data_type: 'currency',
      nullable: true,
      unique: false,
      cardinality: 87,
      null_count: 13,
      null_percentage: 13.0,
      sample_values: [50000, 75000, 60000, null, 85000]
    }
  ],
  row_count: 100,
  column_count: 5,
  inference_confidence: 0.95
}

describe('SchemaViewer', () => {
  it('renders schema information correctly', () => {
    render(<SchemaViewer schema={mockSchema} />)
    
    expect(screen.getByText('Schema Information')).toBeInTheDocument()
    expect(screen.getByText(/5.*columns.*100.*rows/)).toBeInTheDocument()
  })

  it('displays data types in table cells', () => {
    render(<SchemaViewer schema={mockSchema} />)
    
    // Check for data type labels in the table 
    expect(screen.getAllByText('integer')).toHaveLength(2) // id and age
    expect(screen.getByText('string')).toBeInTheDocument()
    expect(screen.getAllByText('email')).toHaveLength(2) // column name and data type
    expect(screen.getByText('currency')).toBeInTheDocument()
  })

  it('renders column details table', () => {
    render(<SchemaViewer schema={mockSchema} />)
    
    // Check table headers
    expect(screen.getByRole('columnheader', { name: 'Column Name' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Data Type' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Nullable' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Unique' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Cardinality' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Missing %' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Sample Values' })).toBeInTheDocument()

    // Check column names
    expect(screen.getByText('id')).toBeInTheDocument()
    expect(screen.getByText('name')).toBeInTheDocument()
    expect(screen.getAllByText('email')).toHaveLength(2) // column name and data type
    expect(screen.getByText('age')).toBeInTheDocument()
    expect(screen.getByText('salary')).toBeInTheDocument()
  })

  it('displays nullable status correctly', () => {
    render(<SchemaViewer schema={mockSchema} />)
    
    // Check nullable indicators - should have Yes/No badges
    const yesBadges = screen.getAllByText('Yes')
    const noBadges = screen.getAllByText('No')
    
    // Should have badges for nullable status
    expect(yesBadges.length).toBeGreaterThan(0)
    expect(noBadges.length).toBeGreaterThan(0)
  })

  it('displays cardinality correctly', () => {
    render(<SchemaViewer schema={mockSchema} />)
    
    expect(screen.getByText('100')).toBeInTheDocument() // id cardinality
    expect(screen.getByText('95')).toBeInTheDocument()  // name cardinality
    expect(screen.getByText('98')).toBeInTheDocument()  // email cardinality
    expect(screen.getByText('25')).toBeInTheDocument()  // age cardinality
    expect(screen.getByText('87')).toBeInTheDocument()  // salary cardinality
  })

  it('displays sample values correctly', () => {
    render(<SchemaViewer schema={mockSchema} />)
    
    // Check that sample values are displayed (they should be truncated and joined)
    expect(screen.getByText(/1, 2, 3/)).toBeInTheDocument() // id samples
    expect(screen.getByText(/John, Jane, Bob/)).toBeInTheDocument() // name samples
    expect(screen.getByText(/john@example.com/)).toBeInTheDocument() // email samples
  })

  it('handles empty schema gracefully', () => {
    const emptySchema = {
      columns: [],
      row_count: 0,
      column_count: 0,
      inference_confidence: 0.0
    }
    
    render(<SchemaViewer schema={emptySchema} />)
    
    expect(screen.getByText('Schema Information')).toBeInTheDocument()
    expect(screen.getByText(/0.*columns.*0.*rows/)).toBeInTheDocument()
    // Component shows empty table, no specific "No columns found" message
    expect(screen.getByText('Column Name')).toBeInTheDocument()
  })

  it('renders data type badges with correct variants', () => {
    render(<SchemaViewer schema={mockSchema} />)
    
    // Check that data type labels are present 
    expect(screen.getAllByText('integer')).toHaveLength(2)
    expect(screen.getByText('string')).toBeInTheDocument() 
    expect(screen.getAllByText('email')).toHaveLength(2)
    expect(screen.getByText('currency')).toBeInTheDocument()
  })

  it('displays confidence score when available', () => {
    render(<SchemaViewer schema={mockSchema} />)
    
    // Should display confidence score
    expect(screen.getByText(/Confidence.*95\.0%/)).toBeInTheDocument()
  })

  it('handles missing optional fields gracefully', () => {
    const incompleteSchema = {
      columns: [
        {
          name: 'test_column',
          data_type: 'string',
          nullable: false,
          unique: false,
          cardinality: 10,
          null_count: 0,
          null_percentage: 0.0
          // missing sample_values
        }
      ],
      row_count: 50,
      column_count: 1
      // missing inference_confidence
    }
    
    render(<SchemaViewer schema={incompleteSchema} />)
    
    expect(screen.getByText('Schema Information')).toBeInTheDocument()
    expect(screen.getByText('test_column')).toBeInTheDocument()
    expect(screen.getByText('string')).toBeInTheDocument()
  })
})