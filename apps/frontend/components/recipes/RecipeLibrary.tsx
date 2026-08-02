'use client';

import React, { useState, useMemo } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { useSession } from 'next-auth/react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Search, Grid, List, AlertCircle, Plus } from 'lucide-react';
import { Recipe, TransformationService } from '@/lib/services/transformation';
import { RecipeCard } from './RecipeCard';
import { getAuthToken } from '@/lib/auth-helpers';

interface RecipeLibraryProps {
  onApplyRecipe?: (recipe: Recipe) => void;
  onCreateNew?: () => void;
  showCreateButton?: boolean;
  includePublic?: boolean;
}

type ViewMode = 'grid' | 'list';
type SortBy = 'recent' | 'popular' | 'name';

export function RecipeLibrary({
  onApplyRecipe,
  onCreateNew,
  showCreateButton = false,
  includePublic = true
}: RecipeLibraryProps) {
  const { data: session } = useSession();
  // `useSession().data` is a NEW OBJECT on every render, and useAsyncData keys
  // its effect on dep identity — passing `session` re-fetched on every render,
  // forever, behind a spinner that never cleared (#402). Depend on the user id,
  // which is a string and therefore stable, and keep `enabled` on the session
  // itself so the request still waits for auth.
  const userId = session?.user?.id
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<SortBy>('recent');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [page, setPage] = useState(1);

  const perPage = 12;

  const {
    data: recipeResponse,
    loading,
    error: loadError,
    reload: loadRecipes,
  } = useAsyncData(
    async () => {
      const token = await getAuthToken();
      return TransformationService.listRecipes(
        token,
        page,
        perPage,
        includePublic,
        selectedTags.length > 0 ? selectedTags : undefined
      );
    },
    [userId, page, selectedTags],
    { enabled: !!session },
  );
  // Duplicate/delete failures are the user's action, not a load failure, so they
  // get their own slot rather than overwriting the list's error.
  const [actionError, setActionError] = useState<string | null>(null);
  const error = actionError ?? loadError;
  const recipes = useMemo(() => recipeResponse?.recipes ?? [], [recipeResponse]);
  const totalPages = recipeResponse ? Math.ceil(recipeResponse.total / perPage) : 0;

  // Pure derivation of props/state — computed during render rather than pushed
  // into state by an effect, which is both a render cheaper and one less way for
  // the list to disagree with its inputs.
  const filteredRecipes = useMemo(() => {
    let filtered = [...recipes];

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (recipe) =>
          recipe.name.toLowerCase().includes(query) ||
          recipe.description.toLowerCase().includes(query) ||
          recipe.tags.some((tag) => tag.toLowerCase().includes(query))
      );
    }

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'popular':
          return b.usage_count - a.usage_count;
        case 'name':
          return a.name.localeCompare(b.name);
        case 'recent':
        default:
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
    });

    return filtered;
  }, [recipes, searchQuery, sortBy]);

  const handleDuplicate = async (recipe: Recipe) => {
    try {
      const token = await getAuthToken();
      const newName = `${recipe.name} (Copy)`;
      await TransformationService.duplicateRecipe(recipe.id, newName, token);
      await loadRecipes();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to duplicate recipe');
    }
  };

  const handleDelete = async (recipe: Recipe) => {
    try {
      const token = await getAuthToken();
      await TransformationService.deleteRecipe(recipe.id, token);
      await loadRecipes();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete recipe');
    }
  };

  const allTags = Array.from(new Set(recipes.flatMap((r) => r.tags)));

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Recipe Library</h2>
          <p className="text-muted-foreground mt-1">
            Browse and apply transformation recipes
          </p>
        </div>
        {showCreateButton && onCreateNew && (
          <Button onClick={onCreateNew}>
            <Plus className="w-4 h-4 mr-2" />
            Create New Recipe
          </Button>
        )}
      </div>

      {/* Filters and Controls */}
      <div className="space-y-4">
        <div className="flex gap-4 items-center">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              placeholder="Search recipes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Sort */}
          <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortBy)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="recent">Most Recent</SelectItem>
              <SelectItem value="popular">Most Popular</SelectItem>
              <SelectItem value="name">Name (A-Z)</SelectItem>
            </SelectContent>
          </Select>

          {/* View Mode Toggle */}
          <div className="flex gap-1 border rounded-lg p-1">
            <Button
              variant={viewMode === 'grid' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('grid')}
              className="h-8 w-8 p-0"
              aria-label="Grid view"
              aria-pressed={viewMode === 'grid'}
            >
              <Grid className="w-4 h-4" aria-hidden="true" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('list')}
              className="h-8 w-8 p-0"
              aria-label="List view"
              aria-pressed={viewMode === 'list'}
            >
              <List className="w-4 h-4" aria-hidden="true" />
            </Button>
          </div>
        </div>

        {/* Tag Filter */}
        {allTags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {allTags.map((tag) => (
              <Badge
                key={tag}
                variant={selectedTags.includes(tag) ? 'default' : 'outline'}
                className="cursor-pointer"
                onClick={() => toggleTag(tag)}
              >
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      )}

      {/* Recipe Grid/List */}
      {!loading && filteredRecipes.length > 0 && (
        <div
          className={
            viewMode === 'grid'
              ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6'
              : 'space-y-4'
          }
        >
          {filteredRecipes.map((recipe) => (
            <RecipeCard
              key={recipe.id}
              recipe={recipe}
              onApply={onApplyRecipe}
              onDuplicate={handleDuplicate}
              onDelete={handleDelete}
              currentUserId={session?.user?.id}
              showActions={true}
            />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredRecipes.length === 0 && (
        <div className="text-center py-12">
          <div className="text-gray-400 mb-4">
            <Search className="w-12 h-12 mx-auto" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">No recipes found</h3>
          <p className="text-muted-foreground">
            {searchQuery || selectedTags.length > 0
              ? 'Try adjusting your search filters'
              : 'Create your first recipe to get started'}
          </p>
        </div>
      )}

      {/* Pagination */}
      {!loading && filteredRecipes.length > 0 && totalPages > 1 && (
        <div className="flex justify-center gap-2 pt-4">
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <div className="flex items-center gap-2 px-4">
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
          </div>
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
