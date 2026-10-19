import { Fragment, useState } from 'react';
import { SearchBox } from './MultiSelectSearch';

/**
 * MultiSelect component for selecting multiple columns
 * Supports keyboard navigation and search filtering
 */
export interface MultiSelectProps {
  id: string;
  options: string[];
  value: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  error?: string;
  'aria-invalid'?: boolean;
  'aria-describedby'?: string;
}

/** The selection after toggling one option. */
function toggleOption(value: string[], option: string): string[] {
  return value.includes(option) ? value.filter((v) => v !== option) : [...value, option];
}

/** Select every visible option, or clear the selection when all of them are already chosen. */
function toggleAll(value: string[], visible: string[]): string[] {
  if (value.length === visible.length) return [];
  return [...value, ...visible.filter((v) => !value.includes(v))];
}

function triggerLabel(value: string[], placeholder: string): string {
  return value.length > 0 ? `${value.length} selected` : placeholder;
}

const TRIGGER_BASE =
  'w-full h-9 px-3 py-1 text-sm text-left border rounded-md bg-transparent transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring';

function triggerClass(error: string | undefined): string {
  return TRIGGER_BASE + (error ? ' border-red-500' : ' border-input');
}


interface SelectAllProps {
  allChosen: boolean;
  onClick: VoidFunction;
}

function SelectAll(props: SelectAllProps) {
  const { allChosen, onClick } = props;
  const label = allChosen ? 'Deselect All' : 'Select All';
  return (
    <div className="p-2">
      <button
        type="button"
        onClick={onClick}
        className="w-full p-2 text-sm text-left hover:bg-accent rounded transition-colors mb-1"
      >
        <span className="font-medium">{label}</span>
      </button>
    </div>
  );
}

interface MultiSelectOptionProps {
  option: string;
  value: string[];
  onChange(selected: string[]): void;
}

function MultiSelectOption(props: MultiSelectOptionProps) {
  const { option, value, onChange } = props;
  const chosen = value.includes(option);
  const toggle = () => onChange(toggleOption(value, option));
  return (
    <label
      className="flex items-center gap-2 p-2 hover:bg-accent cursor-pointer transition-colors"
      role="option"
      aria-selected={chosen}
    >
      <input type="checkbox" checked={chosen} onChange={toggle} className="w-4 h-4 rounded border border-input" />
      <span className="text-sm">{option}</span>
    </label>
  );
}

const NO_MATCH = <div className="p-4 text-sm text-center text-muted-foreground">No columns found</div>;

interface MultiSelectPanelProps {
  id: string;
  options: string[];
  value: string[];
  onChange(selected: string[]): void;
  onClose: VoidFunction;
  searchTerm: string;
  onSearch(term: string): void;
}

function MultiSelectPanel(props: MultiSelectPanelProps) {
  const { id, options, value, onChange, onClose, searchTerm, onSearch } = props;
  const term = searchTerm.toLowerCase();
  const filteredOptions = options.filter((option) => option.toLowerCase().includes(term));
  const selectAll = () => onChange(toggleAll(value, filteredOptions));
  const row = (option: string) => <MultiSelectOption key={option} option={option} value={value} onChange={onChange} />;
  const empty = filteredOptions.length === 0 ? NO_MATCH : null;
  const listboxId = id + '-listbox';
  return (
    <Fragment>
      <div className="absolute top-0 left-0 right-0 bottom-0" onClick={onClose} />
      <div
        className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-md shadow-lg z-50 max-h-64 overflow-y-auto"
        role="listbox"
        aria-multiselectable="true"
        id={listboxId}
      >
        <SearchBox searchTerm={searchTerm} onSearch={onSearch} />
        <SelectAll allChosen={value.length === filteredOptions.length} onClick={selectAll} />
        <div className="border-t">{filteredOptions.map(row)}</div>
        {empty}
      </div>
    </Fragment>
  );
}

export function MultiSelect(props: MultiSelectProps) {
  const { id, options, value, onChange, error } = props;
  const placeholder = props.placeholder ?? 'Select items...';
  const [isOpen, setIsOpen] = useState(false);
  // The search text outlives the open list, as it always has.
  const [searchTerm, setSearchTerm] = useState('');
  const toggle = () => setIsOpen(!isOpen);
  const close = () => setIsOpen(false);
  const textClass = value.length > 0 ? 'text-foreground' : 'text-muted-foreground';

  return (
    <div className="relative">
      <button
        type="button"
        onClick={toggle}
        className={triggerClass(error)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={`${id}-listbox`}
        aria-describedby={props['aria-describedby']}
      >
        <div className="flex items-center justify-between">
          <span className={textClass}>{triggerLabel(value, placeholder)}</span>
          <span className="text-xs text-muted-foreground">▼</span>
        </div>
      </button>

      {isOpen && <MultiSelectPanel id={id} options={options} value={value} onChange={onChange} onClose={close} searchTerm={searchTerm} onSearch={setSearchTerm} />}
    </div>
  );
}
