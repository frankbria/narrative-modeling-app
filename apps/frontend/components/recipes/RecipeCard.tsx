'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Play,
  Copy,
  Share2,
  Download,
  Trash2,
  MoreVertical,
  Clock,
  Users,
  CheckCircle,
} from 'lucide-react';
import { Recipe, RecipeCompatibilityResponse } from '@/lib/services/transformation';
import { RecipeCompatibilityBadge } from './RecipeCompatibilityBadge';
import { RecipeShareDialog } from './RecipeShareDialog';
import { RecipeExportDialog } from './RecipeExportDialog';
import { format } from 'date-fns';

interface RecipeCardProps {
  recipe: Recipe;
  compatibility?: RecipeCompatibilityResponse | null;
  isLoadingCompatibility?: boolean;
  onApply?: (recipe: Recipe) => void;
  onDuplicate?: (recipe: Recipe) => void;
  onDelete?: (recipe: Recipe) => void;
  showActions?: boolean;
  currentUserId?: string;
}

export function RecipeCard({
  recipe,
  compatibility,
  isLoadingCompatibility = false,
  onApply,
  onDuplicate,
  onDelete,
  showActions = true,
  currentUserId
}: RecipeCardProps) {
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);

  const isOwner = currentUserId && recipe.user_id === currentUserId;
  const canApply = compatibility?.is_compatible ?? true;

  const handleApply = () => {
    if (onApply && canApply) {
      onApply(recipe);
    }
  };

  const handleDuplicate = () => {
    if (onDuplicate) {
      onDuplicate(recipe);
    }
  };

  const handleDelete = () => {
    if (onDelete && window.confirm(`Are you sure you want to delete "${recipe.name}"?`)) {
      onDelete(recipe);
    }
  };

  return (
    <>
      <Card className="hover:shadow-md transition-shadow">
        <CardHeader>
          <div className="flex justify-between items-start gap-4">
            <div className="flex-1 min-w-0">
              <CardTitle className="text-lg truncate">{recipe.name}</CardTitle>
              <CardDescription className="line-clamp-2 mt-1">
                {recipe.description}
              </CardDescription>
            </div>

            {showActions && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    aria-label="Recipe actions"
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {onApply && (
                    <DropdownMenuItem onClick={handleApply} disabled={!canApply}>
                      <Play className="w-4 h-4 mr-2" />
                      Apply Recipe
                    </DropdownMenuItem>
                  )}
                  {onDuplicate && (
                    <DropdownMenuItem onClick={handleDuplicate}>
                      <Copy className="w-4 h-4 mr-2" />
                      Duplicate
                    </DropdownMenuItem>
                  )}
                  {isOwner && (
                    <DropdownMenuItem onClick={() => setShareDialogOpen(true)}>
                      <Share2 className="w-4 h-4 mr-2" />
                      Share
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem onClick={() => setExportDialogOpen(true)}>
                    <Download className="w-4 h-4 mr-2" />
                    Export JSON
                  </DropdownMenuItem>
                  {isOwner && onDelete && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={handleDelete}
                        className="text-red-600 focus:text-red-600"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Delete
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Tags */}
          {recipe.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {recipe.tags.map((tag) => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
            </div>
          )}

          {/* Compatibility Badge */}
          {(compatibility || isLoadingCompatibility) && (
            <RecipeCompatibilityBadge
              compatibility={compatibility}
              isLoading={isLoadingCompatibility}
            />
          )}

          {/* Metadata */}
          <div className="flex items-center justify-between text-sm text-gray-500">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <CheckCircle className="w-4 h-4" />
                {recipe.steps.length} steps
              </span>
              <span className="flex items-center gap-1">
                <Users className="w-4 h-4" />
                {recipe.usage_count} uses
              </span>
            </div>
            <span className="flex items-center gap-1 text-xs">
              <Clock className="w-3 h-3" />
              {format(new Date(recipe.created_at), 'MMM d, yyyy')}
            </span>
          </div>

          {/* Rating */}
          {recipe.rating > 0 && (
            <div className="flex items-center gap-2">
              <div className="flex items-center">
                {[...Array(5)].map((_, i) => (
                  <span
                    key={i}
                    className={`text-lg ${
                      i < Math.round(recipe.rating) ? 'text-yellow-400' : 'text-gray-300'
                    }`}
                  >
                    ★
                  </span>
                ))}
              </div>
              <span className="text-sm text-gray-600">{recipe.rating.toFixed(1)}</span>
            </div>
          )}

          {/* Public Badge */}
          {recipe.is_public && (
            <Badge variant="outline" className="w-fit">
              Public Recipe
            </Badge>
          )}

          {/* Quick Actions */}
          {showActions && onApply && (
            <div className="pt-2">
              <Button
                onClick={handleApply}
                disabled={!canApply}
                className="w-full"
                size="sm"
              >
                <Play className="w-4 h-4 mr-2" />
                Apply Recipe
              </Button>
              {!canApply && (
                <p className="text-xs text-red-600 mt-2">
                  This recipe is not compatible with the current dataset
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialogs */}
      {isOwner && (
        <>
          <RecipeShareDialog
            open={shareDialogOpen}
            onOpenChange={setShareDialogOpen}
            recipeId={recipe.id}
            recipeName={recipe.name}
          />
          <RecipeExportDialog
            open={exportDialogOpen}
            onOpenChange={setExportDialogOpen}
            recipeId={recipe.id}
            recipeName={recipe.name}
          />
        </>
      )}

      {!isOwner && (
        <RecipeExportDialog
          open={exportDialogOpen}
          onOpenChange={setExportDialogOpen}
          recipeId={recipe.id}
          recipeName={recipe.name}
        />
      )}
    </>
  );
}
