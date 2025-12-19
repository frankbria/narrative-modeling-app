# Recipe Library UI Components

This directory contains the comprehensive UI components for the Recipe Library feature, which allows users to save, share, browse, and reuse data transformation workflows.

## Components Overview

### 1. RecipeCard (`RecipeCard.tsx`)
A reusable card component that displays recipe information with actions.

**Features:**
- Displays recipe metadata (name, description, tags, usage count, rating)
- Shows compatibility badge when available
- Dropdown menu with actions: Apply, Duplicate, Share, Export, Delete
- Responsive design with hover effects
- Ownership-based action visibility

**Props:**
```typescript
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
```

**Usage:**
```tsx
<RecipeCard
  recipe={recipe}
  compatibility={compatibilityData}
  onApply={handleApply}
  currentUserId={userId}
/>
```

### 2. RecipeLibrary (`RecipeLibrary.tsx`)
Main library component with search, filter, and pagination.

**Features:**
- Grid/list view toggle
- Real-time search across recipe names, descriptions, and tags
- Tag-based filtering with visual chips
- Sorting options (recent, popular, name)
- Pagination controls
- Loading and empty states
- Integration with RecipeCard components

**Props:**
```typescript
interface RecipeLibraryProps {
  onApplyRecipe?: (recipe: Recipe) => void;
  onCreateNew?: () => void;
  showCreateButton?: boolean;
}
```

**Usage:**
```tsx
<RecipeLibrary
  onApplyRecipe={handleApplyRecipe}
  onCreateNew={handleCreateNew}
  showCreateButton={true}
/>
```

### 3. RecipeCompatibilityBadge (`RecipeCompatibilityBadge.tsx`)
Visual indicator for recipe compatibility with datasets.

**Features:**
- Color-coded badges (green, yellow, red) based on compatibility score
- Percentage display
- Hover tooltip with warnings and suggestions
- Loading state animation

**Props:**
```typescript
interface RecipeCompatibilityBadgeProps {
  compatibility: RecipeCompatibilityResponse | null;
  isLoading?: boolean;
}
```

**Compatibility Levels:**
- **Compatible** (≥90%): Green checkmark, full compatibility
- **Partially Compatible** (70-89%): Yellow warning, some issues
- **Incompatible** (<70%): Red X, significant incompatibilities

### 4. RecipeShareDialog (`RecipeShareDialog.tsx`)
Modal dialog for sharing recipes with other users.

**Features:**
- User ID input field
- Real-time validation
- Success/error feedback
- Auto-close on success
- Creates independent copy for recipient

**Props:**
```typescript
interface RecipeShareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recipeId: string;
  recipeName: string;
}
```

**Usage:**
```tsx
<RecipeShareDialog
  open={shareDialogOpen}
  onOpenChange={setShareDialogOpen}
  recipeId={recipe.id}
  recipeName={recipe.name}
/>
```

### 5. RecipeExportDialog (`RecipeExportDialog.tsx`)
Modal dialog for exporting recipes as JSON.

**Features:**
- JSON preview with syntax highlighting
- Download as .json file
- Copy to clipboard functionality
- File size and metadata display
- Tabbed interface (preview/formatted view)

**Props:**
```typescript
interface RecipeExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recipeId: string;
  recipeName: string;
}
```

## Pages

### Recipes Page (`app/recipes/page.tsx`)
Dedicated page for browsing the recipe library.

**Features:**
- Four tabs: All Recipes, My Recipes, Shared with Me, Popular
- Tab-specific data loading
- Create new recipe button
- Integration with all recipe components
- Authentication check
- Error handling

**Route:** `/recipes`

## API Integration

All components use the `TransformationService` from `@/lib/services/transformation` which includes:

- `listRecipes()` - Get paginated recipe list
- `getPopularRecipes()` - Get most used recipes
- `getSharedRecipes()` - Get recipes shared with user
- `checkRecipeCompatibility()` - Check recipe compatibility with dataset
- `duplicateRecipe()` - Create copy of recipe
- `shareRecipe()` - Share recipe with another user
- `exportRecipeAsJSON()` - Export recipe as JSON
- `importRecipe()` - Import recipe from JSON
- `deleteRecipe()` - Delete recipe

## Styling

All components use:
- **Shadcn/UI** components for consistency
- **Tailwind CSS** for styling
- **Lucide React** icons
- Responsive design patterns
- Dark mode compatible color schemes

## TypeScript Support

All components are fully typed with:
- Strict TypeScript mode
- Proper interface definitions
- Type-safe props
- ESLint compliant

## Dependencies

- `next` - Next.js framework
- `next-auth` - Authentication
- `react` - React library
- `date-fns` - Date formatting
- `lucide-react` - Icon library
- Shadcn/UI components:
  - `@/components/ui/card`
  - `@/components/ui/badge`
  - `@/components/ui/button`
  - `@/components/ui/dialog`
  - `@/components/ui/input`
  - `@/components/ui/select`
  - `@/components/ui/tabs`
  - `@/components/ui/alert`

## Best Practices

1. **Error Handling**: All API calls include try-catch blocks with user-friendly error messages
2. **Loading States**: Visual feedback during async operations
3. **Optimistic Updates**: UI updates before API confirmation where appropriate
4. **Accessibility**: Proper ARIA labels and keyboard navigation
5. **Performance**: Pagination and lazy loading for large datasets
6. **Security**: Authentication checks and ownership validation

## Future Enhancements

Potential improvements:
- Recipe versioning UI
- Recipe rating system
- Recipe comments/feedback
- Bulk operations (delete, share multiple recipes)
- Recipe collections/folders
- Advanced search with filters
- Recipe templates
- Import from file upload
