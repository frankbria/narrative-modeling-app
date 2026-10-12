'use client';

import React, { useState } from 'react';
import { BookOpen, Clock, Star, Users } from 'lucide-react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { fetchRecipes, type RecipeFilter, type SavedRecipe } from '@/lib/services/pipelineApi';

/**
 * The saved recipes a pipeline can be loaded from (#859).
 *
 * The list is read through `fetchRecipes`, whose routes are pinned to the API. It used
 * to be fetched inline from a route that does not exist, with the failure swallowed, so
 * the tab was always empty and never said why.
 */

const FILTERS: { value: RecipeFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'mine', label: 'My Recipes' },
  { value: 'popular', label: 'Popular' },
];

const CHOSEN = 'bg-blue-600 text-white';
const NOT_CHOSEN = 'bg-muted text-foreground hover:bg-gray-200';
const POPULAR_ICON = <Star className="w-4 h-4 inline mr-1" />;

interface FilterButtonProps {
  value: RecipeFilter;
  label: string;
  chosen: boolean;
  onChoose(filter: RecipeFilter): void;
}

function FilterButton(props: FilterButtonProps) {
  const { value, label, chosen, onChoose } = props;
  const choose = () => onChoose(value);
  const tone = chosen ? CHOSEN : NOT_CHOSEN;
  return (
    <button onClick={choose} aria-pressed={chosen} className={`px-3 py-1 rounded text-sm ${tone}`}>
      {value === 'popular' && POPULAR_ICON}
      {label}
    </button>
  );
}

function stepCount(recipe: SavedRecipe): string {
  const steps = recipe.steps.length;
  return steps === 1 ? '1 step' : `${steps} steps`;
}

interface RecipeCardProps {
  recipe: SavedRecipe;
  onLoad(recipe: SavedRecipe): void;
}

function RecipeCard(props: RecipeCardProps) {
  const { recipe, onLoad } = props;
  const load = () => onLoad(recipe);
  return (
    <button
      type="button"
      onClick={load}
      className="block w-full text-left p-4 border rounded-lg hover:border-blue-400 transition-colors"
    >
      <span className="flex items-start justify-between mb-2">
        <span className="font-medium">{recipe.name}</span>
        {recipe.is_public && <Users className="w-4 h-4 text-gray-400" aria-label="Public recipe" />}
      </span>
      <span className="block text-sm text-muted-foreground mb-2">{recipe.description}</span>
      <span className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {new Date(recipe.created_at).toLocaleDateString()}
        </span>
        <span>{stepCount(recipe)}</span>
        {recipe.usage_count > 0 && <span>{recipe.usage_count} uses</span>}
      </span>
    </button>
  );
}

const SPINNER = (
  <div className="text-center py-8">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
  </div>
);

const NOTHING_FOUND = (
  <div className="text-center py-8 text-muted-foreground">
    <BookOpen className="w-12 h-12 mx-auto mb-2 opacity-20" />
    <p>No recipes found</p>
  </div>
);

interface RecipeListProps {
  loading: boolean;
  error: string | null;
  recipes: SavedRecipe[] | undefined;
  onLoad(recipe: SavedRecipe): void;
}

function RecipeList(props: RecipeListProps) {
  const { loading, error, recipes, onLoad } = props;
  if (loading) return SPINNER;
  if (error) {
    return (
      <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        Could not load recipes: {error}
      </p>
    );
  }
  if (!recipes?.length) return NOTHING_FOUND;
  return (
    <div className="space-y-3">
      {recipes.map((recipe) => (
        <RecipeCard key={recipe.id} recipe={recipe} onLoad={onLoad} />
      ))}
    </div>
  );
}

interface RecipeBrowserProps {
  onLoad(recipe: SavedRecipe): void;
}

export default function RecipeBrowser(props: RecipeBrowserProps) {
  const { onLoad } = props;
  const [filter, setFilter] = useState<RecipeFilter>('all');
  const { data: recipes, loading, error } = useAsyncData(() => fetchRecipes(filter), [filter]);
  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b">
        <div className="flex gap-2">
          {FILTERS.map((option) => (
            <FilterButton
              key={option.value}
              value={option.value}
              label={option.label}
              chosen={filter === option.value}
              onChoose={setFilter}
            />
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <RecipeList loading={loading} error={error} recipes={recipes} onLoad={onLoad} />
      </div>
    </div>
  );
}
