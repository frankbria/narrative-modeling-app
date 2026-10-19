import React from 'react';

type InputChange = React.ChangeEvent<HTMLInputElement>;

interface SearchBoxProps {
  searchTerm: string;
  onSearch(term: string): void;
}

export function SearchBox(props: SearchBoxProps) {
  const { searchTerm, onSearch } = props;
  const search = (e: InputChange) => onSearch(e.target.value);
  return (
    <div className="p-2 border-b sticky top-0 bg-background">
      <input type="text" placeholder="Search..." value={searchTerm} onChange={search} aria-label={"Search columns"} className="w-full h-8 px-2 text-sm border rounded" />
    </div>
  );
}
