'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import {
  Filter,
  X,
  Search,
  SlidersHorizontal,
  ArrowUpDown,
} from 'lucide-react';
import { FeatureType, ComputationCost } from '@/lib/hooks/useFeatureSuggestions';
import { FilterState, useFeatureEngineering } from '@/lib/contexts/FeatureEngineeringContext';

const featureTypes: { value: FeatureType; label: string }[] = [
  { value: 'polynomial', label: 'Polynomial' },
  { value: 'interaction', label: 'Interaction' },
  { value: 'aggregation', label: 'Aggregation' },
  { value: 'time_based', label: 'Time-Based' },
  { value: 'text', label: 'Text' },
  { value: 'binning', label: 'Binning' },
  { value: 'encoding', label: 'Encoding' },
  { value: 'scaling', label: 'Scaling' },
  { value: 'mathematical', label: 'Mathematical' },
  { value: 'domain_specific', label: 'Domain-Specific' },
];

const computationCosts: { value: ComputationCost; label: string }[] = [
  { value: 'low', label: 'Fast' },
  { value: 'medium', label: 'Moderate' },
  { value: 'high', label: 'Slow' },
];

const sortOptions: { value: FilterState['sortBy']; label: string }[] = [
  { value: 'importance', label: 'Importance' },
  { value: 'name', label: 'Name' },
  { value: 'type', label: 'Type' },
  { value: 'cost', label: 'Computation Cost' },
];

interface SuggestionFiltersProps {
  className?: string;
}

export function SuggestionFilters({ className }: SuggestionFiltersProps) {
  const { filters, setFilters, resetFilters } = useFeatureEngineering();

  const activeFilterCount =
    (filters.featureTypes.length > 0 ? 1 : 0) +
    (filters.computationCosts.length > 0 ? 1 : 0) +
    (filters.minImportance > 0 || filters.maxImportance < 100 ? 1 : 0) +
    (filters.searchQuery ? 1 : 0);

  const handleFeatureTypeToggle = (type: FeatureType) => {
    const newTypes = filters.featureTypes.includes(type)
      ? filters.featureTypes.filter((t) => t !== type)
      : [...filters.featureTypes, type];
    setFilters({ featureTypes: newTypes });
  };

  const handleCostToggle = (cost: ComputationCost) => {
    const newCosts = filters.computationCosts.includes(cost)
      ? filters.computationCosts.filter((c) => c !== cost)
      : [...filters.computationCosts, cost];
    setFilters({ computationCosts: newCosts });
  };

  return (
    <div className={cn('flex flex-wrap items-center gap-3', className)}>
      {/* Search */}
      <div className="relative flex-1 min-w-[200px] max-w-xs">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search features..."
          value={filters.searchQuery}
          onChange={(e) => setFilters({ searchQuery: e.target.value })}
          className="pl-9"
        />
      </div>

      {/* Feature Type Filter */}
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            <Filter className="h-4 w-4" />
            Type
            {filters.featureTypes.length > 0 && (
              <Badge variant="secondary" className="ml-1">
                {filters.featureTypes.length}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-56" align="start">
          <div className="space-y-2">
            <Label className="text-sm font-medium">Feature Types</Label>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {featureTypes.map((type) => (
                <div key={type.value} className="flex items-center space-x-2">
                  <Checkbox
                    id={`type-${type.value}`}
                    checked={filters.featureTypes.includes(type.value)}
                    onCheckedChange={() => handleFeatureTypeToggle(type.value)}
                  />
                  <label
                    htmlFor={`type-${type.value}`}
                    className="text-sm cursor-pointer"
                  >
                    {type.label}
                  </label>
                </div>
              ))}
            </div>
          </div>
        </PopoverContent>
      </Popover>

      {/* Computation Cost Filter */}
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            <SlidersHorizontal className="h-4 w-4" />
            Cost
            {filters.computationCosts.length > 0 && (
              <Badge variant="secondary" className="ml-1">
                {filters.computationCosts.length}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-48" align="start">
          <div className="space-y-2">
            <Label className="text-sm font-medium">Computation Cost</Label>
            <div className="space-y-2">
              {computationCosts.map((cost) => (
                <div key={cost.value} className="flex items-center space-x-2">
                  <Checkbox
                    id={`cost-${cost.value}`}
                    checked={filters.computationCosts.includes(cost.value)}
                    onCheckedChange={() => handleCostToggle(cost.value)}
                  />
                  <label
                    htmlFor={`cost-${cost.value}`}
                    className="text-sm cursor-pointer"
                  >
                    {cost.label}
                  </label>
                </div>
              ))}
            </div>
          </div>
        </PopoverContent>
      </Popover>

      {/* Importance Range */}
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            Importance
            {(filters.minImportance > 0 || filters.maxImportance < 100) && (
              <Badge variant="secondary" className="ml-1">
                {filters.minImportance}-{filters.maxImportance}%
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-64" align="start">
          <div className="space-y-4">
            <Label className="text-sm font-medium">Importance Range</Label>
            <div className="px-2">
              <Slider
                value={[filters.minImportance, filters.maxImportance]}
                onValueChange={([min, max]) =>
                  setFilters({ minImportance: min, maxImportance: max })
                }
                min={0}
                max={100}
                step={5}
                className="w-full"
              />
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{filters.minImportance}%</span>
              <span>{filters.maxImportance}%</span>
            </div>
          </div>
        </PopoverContent>
      </Popover>

      {/* Sort */}
      <div className="flex items-center gap-2">
        <Select
          value={filters.sortBy}
          onValueChange={(value) => setFilters({ sortBy: value as FilterState['sortBy'] })}
        >
          <SelectTrigger className="w-[140px] h-9">
            <ArrowUpDown className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            {sortOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            setFilters({ sortOrder: filters.sortOrder === 'asc' ? 'desc' : 'asc' })
          }
          className="px-2"
        >
          {filters.sortOrder === 'asc' ? '↑' : '↓'}
        </Button>
      </div>

      {/* Clear filters */}
      {activeFilterCount > 0 && (
        <Button
          variant="ghost"
          size="sm"
          onClick={resetFilters}
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4 mr-1" />
          Clear ({activeFilterCount})
        </Button>
      )}
    </div>
  );
}
