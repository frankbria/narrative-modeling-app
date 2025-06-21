import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Search,
  Star,
  Users,
  Clock,
  Download,
  Play,
  Code,
  ChevronRight,
} from 'lucide-react';
import { TransformationService, Recipe } from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';


interface RecipeBrowserProps {
  datasetId: string;
  onApplyRecipe: (recipe: Recipe) => void;
}

export function RecipeBrowser({ datasetId, onApplyRecipe }: RecipeBrowserProps) {
  const { data: session } = useSession();
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [popularRecipes, setPopularRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
  const [activeTab, setActiveTab] = useState('my-recipes');

  useEffect(() => {
    if (session) {
      fetchRecipes();
      fetchPopularRecipes();
    }
  }, [session]);

  const fetchRecipes = async () => {
    if (!session) return;
    
    try {
      const token = await getAuthToken();
      const response = await TransformationService.listRecipes(token);
      setRecipes(response.recipes);
    } catch (error) {
      console.error('Failed to fetch recipes:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPopularRecipes = async () => {
    if (!session) return;
    
    try {
      const token = await getAuthToken();
      const response = await TransformationService.getPopularRecipes(token, 10);
      setPopularRecipes(response.recipes);
    } catch (error) {
      console.error('Failed to fetch popular recipes:', error);
    }
  };

  const handleApplyRecipe = async (recipe: Recipe) => {
    if (!session) return;
    
    try {
      const token = await getAuthToken();
      const response = await TransformationService.applyRecipe(recipe.id, datasetId, token);
      
      if (response.success) {
        onApplyRecipe(recipe);
      }
    } catch (error) {
      console.error('Failed to apply recipe:', error);
    }
  };

  const handleExportRecipe = async (recipe: Recipe, language: string = 'python') => {
    if (!session) return;
    
    try {
      const token = await getAuthToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/transformations/recipes/${recipe.id}/export`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ language })
        }
      );
      
      if (!response.ok) {
        throw new Error('Export failed');
      }
      
      const data = await response.json();
      
      // Download the code
      const blob = new Blob([data.code], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${recipe.name.replace(/\s+/g, '_')}.py`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export recipe:', error);
    }
  };

  const filteredRecipes = recipes.filter(
    (recipe) =>
      recipe.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      recipe.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      recipe.tags.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const RecipeCard = ({ recipe }: { recipe: Recipe }) => (
    <Card
      className="cursor-pointer hover:shadow-lg transition-shadow"
      onClick={() => setSelectedRecipe(recipe)}
    >
      <CardHeader>
        <div className="flex justify-between items-start">
          <CardTitle className="text-lg">{recipe.name}</CardTitle>
          {recipe.rating && (
            <div className="flex items-center gap-1">
              <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
              <span className="text-sm">{recipe.rating.toFixed(1)}</span>
            </div>
          )}
        </div>
        <CardDescription>{recipe.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2 mb-3">
          {recipe.tags.map((tag) => (
            <Badge key={tag} variant="secondary">
              {tag}
            </Badge>
          ))}
        </div>
        <div className="flex items-center justify-between text-sm text-gray-500">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <Users className="w-4 h-4" />
              {recipe.usage_count} uses
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {recipe.steps.length} steps
            </span>
          </div>
          <ChevronRight className="w-4 h-4" />
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              placeholder="Search recipes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
          <TabsList className="px-4">
            <TabsTrigger value="my-recipes">My Recipes</TabsTrigger>
            <TabsTrigger value="community">Community</TabsTrigger>
            <TabsTrigger value="popular">Popular</TabsTrigger>
          </TabsList>

          <TabsContent value="my-recipes" className="flex-1 p-0">
            <ScrollArea className="h-full">
              <div className="p-4 grid gap-4">
                {loading ? (
                  <div className="text-center py-8">Loading recipes...</div>
                ) : filteredRecipes.filter((r) => !r.is_public).length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No recipes found. Create your first recipe by building a transformation pipeline!
                  </div>
                ) : (
                  filteredRecipes
                    .filter((r) => !r.is_public)
                    .map((recipe) => <RecipeCard key={recipe.id} recipe={recipe} />)
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="community" className="flex-1 p-0">
            <ScrollArea className="h-full">
              <div className="p-4 grid gap-4">
                {filteredRecipes.filter((r) => r.is_public).length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No community recipes found.
                  </div>
                ) : (
                  filteredRecipes
                    .filter((r) => r.is_public)
                    .map((recipe) => <RecipeCard key={recipe.id} recipe={recipe} />)
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="popular" className="flex-1 p-0">
            <ScrollArea className="h-full">
              <div className="p-4 grid gap-4">
                {popularRecipes.map((recipe) => (
                  <RecipeCard key={recipe.id} recipe={recipe} />
                ))}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </div>

      {selectedRecipe && (
        <div className="w-96 border-l bg-white p-6">
          <div className="mb-6">
            <h2 className="text-xl font-bold mb-2">{selectedRecipe.name}</h2>
            {selectedRecipe.description && (
              <p className="text-gray-600">{selectedRecipe.description}</p>
            )}
          </div>

          <div className="mb-6">
            <h3 className="font-semibold mb-3">Transformation Steps</h3>
            <div className="space-y-2">
              {selectedRecipe.steps
                .sort((a, b) => a.order - b.order)
                .map((step, idx) => (
                  <div key={step.step_id} className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-medium">
                      {idx + 1}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-sm">{step.type}</div>
                      {step.description && (
                        <div className="text-xs text-gray-500">{step.description}</div>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          </div>

          <div className="space-y-2">
            <Button
              className="w-full"
              onClick={() => handleApplyRecipe(selectedRecipe)}
            >
              <Play className="w-4 h-4 mr-2" />
              Apply Recipe
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => handleExportRecipe(selectedRecipe)}
            >
              <Code className="w-4 h-4 mr-2" />
              Export as Code
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}