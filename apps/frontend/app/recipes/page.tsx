'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Plus, BookOpen, Share2, TrendingUp, AlertCircle } from 'lucide-react';
import { RecipeLibrary } from '@/components/recipes/RecipeLibrary';
import { Recipe, TransformationService, SharedRecipe } from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';
import { RecipeCard } from '@/components/recipes/RecipeCard';

export default function RecipesPage() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const [activeTab, setActiveTab] = useState<'all' | 'my-recipes' | 'shared' | 'popular'>('all');
  const [sharedRecipes, setSharedRecipes] = useState<SharedRecipe[]>([]);
  const [popularRecipes, setPopularRecipes] = useState<Recipe[]>([]);
  const [loadingShared, setLoadingShared] = useState(false);
  const [loadingPopular, setLoadingPopular] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreateNew = () => {
    router.push('/transform');
  };

  const handleApplyRecipe = (recipe: Recipe) => {
    router.push(`/transform?recipeId=${recipe.id}`);
  };

  const loadSharedRecipes = async () => {
    if (!session || sharedRecipes.length > 0) return;

    setLoadingShared(true);
    setError(null);

    try {
      const token = await getAuthToken();
      const response = await TransformationService.getSharedRecipes(token);
      setSharedRecipes(response.shared_recipes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load shared recipes');
    } finally {
      setLoadingShared(false);
    }
  };

  const loadPopularRecipes = async () => {
    if (!session || popularRecipes.length > 0) return;

    setLoadingPopular(true);
    setError(null);

    try {
      const token = await getAuthToken();
      const response = await TransformationService.getPopularRecipes(token, 20);
      setPopularRecipes(response.recipes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load popular recipes');
    } finally {
      setLoadingPopular(false);
    }
  };

  const handleTabChange = (value: string) => {
    setActiveTab(value as 'all' | 'my-recipes' | 'shared' | 'popular');

    if (value === 'shared') {
      loadSharedRecipes();
    } else if (value === 'popular') {
      loadPopularRecipes();
    }
  };

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (status === 'unauthenticated') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Alert className="max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Please sign in to access the recipe library.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-7xl">
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-3xl font-bold">Recipe Library</h1>
          <Button onClick={handleCreateNew} size="lg">
            <Plus className="w-5 h-5 mr-2" />
            Create New Recipe
          </Button>
        </div>
        <p className="text-gray-600">
          Save, share, and reuse data transformation workflows
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
          <TabsTrigger value="all" className="gap-2">
            <BookOpen className="w-4 h-4" />
            All Recipes
          </TabsTrigger>
          <TabsTrigger value="my-recipes" className="gap-2">
            <BookOpen className="w-4 h-4" />
            My Recipes
          </TabsTrigger>
          <TabsTrigger value="shared" className="gap-2">
            <Share2 className="w-4 h-4" />
            Shared with Me
          </TabsTrigger>
          <TabsTrigger value="popular" className="gap-2">
            <TrendingUp className="w-4 h-4" />
            Popular
          </TabsTrigger>
        </TabsList>

        {/* All Recipes Tab */}
        <TabsContent value="all" className="space-y-4">
          <RecipeLibrary
            onApplyRecipe={handleApplyRecipe}
            onCreateNew={handleCreateNew}
            showCreateButton={false}
          />
        </TabsContent>

        {/* My Recipes Tab */}
        <TabsContent value="my-recipes" className="space-y-4">
          <RecipeLibrary
            onApplyRecipe={handleApplyRecipe}
            onCreateNew={handleCreateNew}
            showCreateButton={true}
            includePublic={false}
          />
        </TabsContent>

        {/* Shared with Me Tab */}
        <TabsContent value="shared" className="space-y-4">
          <div className="mb-4">
            <h2 className="text-xl font-semibold mb-2">Recipes Shared with You</h2>
            <p className="text-gray-600 text-sm">
              These recipes have been shared by other users. You have full access to use and modify them.
            </p>
          </div>

          {loadingShared && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          )}

          {!loadingShared && sharedRecipes.length === 0 && (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <Share2 className="w-12 h-12 mx-auto text-gray-400 mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No shared recipes</h3>
              <p className="text-gray-600">
                When someone shares a recipe with you, it will appear here
              </p>
            </div>
          )}

          {!loadingShared && sharedRecipes.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {sharedRecipes.map((sharedRecipe) => (
                <div key={sharedRecipe.id} className="space-y-2">
                  <div className="text-xs text-gray-500">
                    Shared by {sharedRecipe.original_owner_id} on{' '}
                    {new Date(sharedRecipe.shared_at).toLocaleDateString()}
                  </div>
                  {/* Note: We would need to fetch the full recipe details here */}
                  <div className="bg-white border rounded-lg p-4">
                    <h3 className="font-semibold mb-1">{sharedRecipe.name}</h3>
                    <p className="text-sm text-gray-600 mb-3">{sharedRecipe.description}</p>
                    <div className="flex items-center justify-between text-xs text-gray-500">
                      <span>{sharedRecipe.steps_count} steps</span>
                      <span>Version {sharedRecipe.version}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Popular Tab */}
        <TabsContent value="popular" className="space-y-4">
          <div className="mb-4">
            <h2 className="text-xl font-semibold mb-2">Most Popular Recipes</h2>
            <p className="text-gray-600 text-sm">
              The most used and highly-rated recipes from the community
            </p>
          </div>

          {loadingPopular && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          )}

          {!loadingPopular && popularRecipes.length === 0 && (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <TrendingUp className="w-12 h-12 mx-auto text-gray-400 mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No popular recipes yet</h3>
              <p className="text-gray-600">
                Create and share recipes to build the community library
              </p>
            </div>
          )}

          {!loadingPopular && popularRecipes.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {popularRecipes.map((recipe) => (
                <RecipeCard
                  key={recipe.id}
                  recipe={recipe}
                  onApply={handleApplyRecipe}
                  currentUserId={session?.user?.id}
                  showActions={true}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
