import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  Search,
  Copy,
  Scissors,
  Type,
  Hash,
  Calendar,
  Filter,
  Shuffle,
  Code,
  Sparkles,
} from 'lucide-react';

interface TransformationSidebarProps {
  onTransformationAdd: (type: string) => void;
  datasetInfo?: any;
}

const transformationCategories = [
  {
    name: 'Data Cleaning',
    icon: Scissors,
    transformations: [
      {
        type: 'remove_duplicates',
        label: 'Remove Duplicates',
        description: 'Remove duplicate rows based on selected columns',
        icon: Copy,
      },
      {
        type: 'trim_whitespace',
        label: 'Trim Whitespace',
        description: 'Remove leading and trailing spaces',
        icon: Type,
      },
      {
        type: 'fix_casing',
        label: 'Fix Casing',
        description: 'Standardize text casing (upper/lower/title)',
        icon: Type,
      },
      {
        type: 'remove_special_chars',
        label: 'Remove Special Characters',
        description: 'Clean text by removing special characters',
        icon: Filter,
      },
    ],
  },
  {
    name: 'Missing Values',
    icon: Filter,
    transformations: [
      {
        type: 'drop_missing',
        label: 'Drop Missing',
        description: 'Remove rows with missing values',
        icon: Filter,
      },
      {
        type: 'fill_missing',
        label: 'Fill Missing',
        description: 'Fill missing values with specific value or strategy',
        icon: Filter,
      },
      {
        type: 'impute_mean',
        label: 'Impute Mean',
        description: 'Replace missing with column mean',
        icon: Hash,
      },
      {
        type: 'impute_median',
        label: 'Impute Median',
        description: 'Replace missing with column median',
        icon: Hash,
      },
    ],
  },
  {
    name: 'Type Conversions',
    icon: Shuffle,
    transformations: [
      {
        type: 'to_numeric',
        label: 'To Numeric',
        description: 'Convert text to numbers',
        icon: Hash,
      },
      {
        type: 'to_string',
        label: 'To String',
        description: 'Convert values to text',
        icon: Type,
      },
      {
        type: 'to_datetime',
        label: 'To DateTime',
        description: 'Parse dates and times',
        icon: Calendar,
      },
      {
        type: 'one_hot_encode',
        label: 'One-Hot Encode',
        description: 'Create binary columns for categories',
        icon: Shuffle,
      },
    ],
  },
  {
    name: 'Custom',
    icon: Code,
    transformations: [
      {
        type: 'formula',
        label: 'Formula',
        description: 'Create custom formulas',
        icon: Code,
      },
      {
        type: 'conditional',
        label: 'Conditional',
        description: 'If-then-else logic',
        icon: Code,
      },
      {
        type: 'regex_replace',
        label: 'Regex Replace',
        description: 'Pattern-based text replacement',
        icon: Code,
      },
    ],
  },
];

export function TransformationSidebar({
  onTransformationAdd,
  datasetInfo,
}: TransformationSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const filteredCategories = transformationCategories.map((category) => ({
    ...category,
    transformations: category.transformations.filter(
      (t) =>
        t.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.description.toLowerCase().includes(searchQuery.toLowerCase())
    ),
  })).filter((category) => category.transformations.length > 0);

  const handleDragStart = (e: React.DragEvent, transformationType: string) => {
    e.dataTransfer.setData('transformationType', transformationType);
    e.dataTransfer.effectAllowed = 'copy';
  };

  return (
    <div className="w-80 border-r bg-white flex flex-col">
      <div className="p-4 border-b">
        <h2 className="text-lg font-semibold mb-3">Transformations</h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <Input
            placeholder="Search transformations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {suggestions.length > 0 && (
        <div className="p-4 border-b bg-blue-50">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-medium">AI Suggestions</span>
          </div>
          <div className="space-y-2">
            {suggestions.map((suggestion, idx) => (
              <Badge
                key={idx}
                variant="secondary"
                className="cursor-pointer hover:bg-blue-100"
                onClick={() => onTransformationAdd(suggestion)}
              >
                {suggestion}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <ScrollArea className="flex-1">
        <Accordion
          type="multiple"
          defaultValue={['data-cleaning', 'missing-values']}
          className="w-full"
        >
          {filteredCategories.map((category, idx) => (
            <AccordionItem
              key={idx}
              value={category.name.toLowerCase().replace(' ', '-')}
            >
              <AccordionTrigger className="px-4 hover:no-underline">
                <div className="flex items-center gap-2">
                  <category.icon className="w-4 h-4" />
                  <span>{category.name}</span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-1 px-4 pb-2">
                  {category.transformations.map((transformation) => (
                    <div
                      key={transformation.type}
                      draggable
                      onDragStart={(e) => handleDragStart(e, transformation.type)}
                      onClick={() => onTransformationAdd(transformation.type)}
                      className="flex items-start gap-3 p-2 rounded-lg hover:bg-gray-100 cursor-move transition-colors"
                    >
                      <transformation.icon className="w-4 h-4 mt-0.5 text-gray-600" />
                      <div className="flex-1">
                        <div className="font-medium text-sm">
                          {transformation.label}
                        </div>
                        <div className="text-xs text-gray-500">
                          {transformation.description}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </ScrollArea>

      <div className="p-4 border-t">
        <Button
          variant="outline"
          className="w-full"
          onClick={() => onTransformationAdd('formula')}
        >
          <Code className="w-4 h-4 mr-2" />
          Custom Formula
        </Button>
      </div>
    </div>
  );
}