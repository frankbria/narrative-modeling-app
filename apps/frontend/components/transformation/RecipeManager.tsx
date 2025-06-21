'use client';

import React, { useState, useEffect } from 'react';
import { X, Save, BookOpen, Users, Star, Clock } from 'lucide-react';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';

interface Recipe {
  id: string;
  name: string;
  description: string;
  transformations: any[];
  created_by: string;
  created_at: string;
  is_public: boolean;
  usage_count: number;
}

interface RecipeManagerProps {
  onClose: () => void;
  onSave: (name: string, description: string) => void;
  onLoad: (recipe: Recipe) => void;
  datasetId: string;
}

export default function RecipeManager({ onClose, onSave, onLoad, datasetId }: RecipeManagerProps) {
  const [activeTab, setActiveTab] = useState<'save' | 'browse'>('browse');
  const [recipeName, setRecipeName] = useState('');
  const [recipeDescription, setRecipeDescription] = useState('');
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<'all' | 'mine' | 'popular'>('all');

  useEffect(() => {
    if (activeTab === 'browse') {
      loadRecipes();
    }
  }, [activeTab, filter]);

  const loadRecipes = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      const response = await fetch(
        `${API_URL}/recipes?filter=${filter}&dataset_id=${datasetId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setRecipes(data.recipes);
      }
    } catch (error) {
      console.error('Failed to load recipes:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = () => {
    if (recipeName && recipeDescription) {
      onSave(recipeName, recipeDescription);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-[600px] max-h-[80vh] flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recipe Manager</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="border-b">
          <div className="flex">
            <button
              onClick={() => setActiveTab('browse')}
              className={`flex-1 px-4 py-3 font-medium ${
                activeTab === 'browse'
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              <BookOpen className="w-4 h-4 inline mr-2" />
              Browse Recipes
            </button>
            <button
              onClick={() => setActiveTab('save')}
              className={`flex-1 px-4 py-3 font-medium ${
                activeTab === 'save'
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              <Save className="w-4 h-4 inline mr-2" />
              Save Recipe
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          {activeTab === 'browse' ? (
            <div className="flex flex-col h-full">
              <div className="p-4 border-b">
                <div className="flex gap-2">
                  <button
                    onClick={() => setFilter('all')}
                    className={`px-3 py-1 rounded text-sm ${
                      filter === 'all'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    All
                  </button>
                  <button
                    onClick={() => setFilter('mine')}
                    className={`px-3 py-1 rounded text-sm ${
                      filter === 'mine'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    My Recipes
                  </button>
                  <button
                    onClick={() => setFilter('popular')}
                    className={`px-3 py-1 rounded text-sm ${
                      filter === 'popular'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    <Star className="w-4 h-4 inline mr-1" />
                    Popular
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4">
                {loading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                  </div>
                ) : recipes.length > 0 ? (
                  <div className="space-y-3">
                    {recipes.map((recipe) => (
                      <div
                        key={recipe.id}
                        className="p-4 border rounded-lg hover:border-blue-400 cursor-pointer transition-colors"
                        onClick={() => onLoad(recipe)}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <h3 className="font-medium">{recipe.name}</h3>
                          {recipe.is_public && (
                            <Users className="w-4 h-4 text-gray-400" />
                          )}
                        </div>
                        <p className="text-sm text-gray-600 mb-2">
                          {recipe.description}
                        </p>
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(recipe.created_at).toLocaleDateString()}
                          </span>
                          <span>{recipe.transformations.length} steps</span>
                          {recipe.usage_count > 0 && (
                            <span>{recipe.usage_count} uses</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <BookOpen className="w-12 h-12 mx-auto mb-2 opacity-20" />
                    <p>No recipes found</p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Recipe Name
                  </label>
                  <input
                    type="text"
                    value={recipeName}
                    onChange={(e) => setRecipeName(e.target.value)}
                    placeholder="Enter a descriptive name"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">
                    Description
                  </label>
                  <textarea
                    value={recipeDescription}
                    onChange={(e) => setRecipeDescription(e.target.value)}
                    placeholder="Describe what this recipe does..."
                    rows={4}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="public"
                    className="w-4 h-4"
                  />
                  <label htmlFor="public" className="text-sm">
                    Make this recipe public for others to use
                  </label>
                </div>

                <button
                  onClick={handleSave}
                  disabled={!recipeName || !recipeDescription}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Save Recipe
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}