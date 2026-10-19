import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { columnsOfType, type ColumnType, type DashboardColumn } from './chartSelection'

interface ColumnButtonProps {
  name: string
  selectedColumns: string[]
  /** Show the column's position in the selection next to its name. */
  showOrder: boolean
  onToggle(columnName: string): void
}

function ColumnButton(props: ColumnButtonProps) {
  const { name, selectedColumns, showOrder, onToggle } = props
  const isSelected = selectedColumns.includes(name)
  const handleClick = () => onToggle(name)
  return (
    <Button
      variant={isSelected ? 'default' : 'outline'}
      size="sm"
      onClick={handleClick}
      className="justify-start"
    >
      {name}
      {isSelected && showOrder ? (
        <Badge variant="secondary" className="ml-2">
          {selectedColumns.indexOf(name) + 1}
        </Badge>
      ) : null}
    </Button>
  )
}

interface ColumnGroupProps {
  title: string
  titleClassName: string
  columns: DashboardColumn[]
  selectedColumns: string[]
  showOrder: boolean
  onToggle(columnName: string): void
}

function ColumnGroup(props: ColumnGroupProps) {
  const { title, titleClassName, columns, selectedColumns, showOrder, onToggle } = props
  const renderButton = (col: DashboardColumn) => (
    <ColumnButton
      key={col.name}
      name={col.name}
      selectedColumns={selectedColumns}
      showOrder={showOrder}
      onToggle={onToggle}
    />
  )
  if (columns.length === 0) return null
  return (
    <div>
      <h4 className={`text-sm font-medium mb-2 ${titleClassName}`}>
        {title} ({columns.length})
      </h4>
      <div className="grid grid-cols-2 gap-2">{columns.map(renderButton)}</div>
    </div>
  )
}

interface GroupStyle {
  type: ColumnType
  title: string
  titleClassName: string
  showOrder: boolean
}

const GROUPS: GroupStyle[] = [
  { type: 'numeric', title: 'Numeric', titleClassName: 'text-green-700 dark:text-green-300', showOrder: true },
  { type: 'categorical', title: 'Categorical', titleClassName: 'text-blue-700 dark:text-blue-300', showOrder: false },
  { type: 'datetime', title: 'DateTime', titleClassName: 'text-purple-700 dark:text-purple-300', showOrder: false },
]

interface ColumnPickerProps {
  columns: DashboardColumn[]
  selectedColumns: string[]
  onToggle(columnName: string): void
}

/** The dataset's columns by kind, as toggle buttons for the chart's selection. */
export function ColumnPicker(props: ColumnPickerProps) {
  const { columns, selectedColumns, onToggle } = props
  const renderGroup = (group: GroupStyle) => (
    <ColumnGroup
      key={group.type}
      title={group.title}
      titleClassName={group.titleClassName}
      columns={columnsOfType(columns, group.type)}
      selectedColumns={selectedColumns}
      showOrder={group.showOrder}
      onToggle={onToggle}
    />
  )
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Select Columns</CardTitle>
        <CardDescription>
          Choose columns for visualization ({selectedColumns.length} selected)
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">{GROUPS.map(renderGroup)}</div>
      </CardContent>
    </Card>
  )
}
