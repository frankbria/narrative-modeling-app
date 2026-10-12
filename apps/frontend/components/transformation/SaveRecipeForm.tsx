'use client';

import React, { useState } from 'react';

interface SaveRecipeFormProps {
  onSave(name: string, description: string, isPublic: boolean): void;
}

const FIELD = 'w-full px-3 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500';

/** Name the current pipeline and save it as a recipe, for this account or for everyone. */
export default function SaveRecipeForm(props: SaveRecipeFormProps) {
  const { onSave } = props;
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const incomplete = name === '' || description === '';
  const save = () => onSave(name, description, isPublic);
  const changeName = (event: React.ChangeEvent<HTMLInputElement>) => setName(event.target.value);
  const changeDescription = (event: React.ChangeEvent<HTMLTextAreaElement>) => setDescription(event.target.value);
  const changePublic = (event: React.ChangeEvent<HTMLInputElement>) => setIsPublic(event.target.checked);
  return (
    <div className="p-6">
      <div className="space-y-4">
        <div>
          <label htmlFor="recipe-name" className="block text-sm font-medium mb-2">
            Recipe Name
          </label>
          <input
            id="recipe-name"
            type="text"
            value={name}
            onChange={changeName}
            placeholder="Enter a descriptive name"
            className={FIELD}
          />
        </div>

        <div>
          <label htmlFor="recipe-description" className="block text-sm font-medium mb-2">
            Description
          </label>
          <textarea
            id="recipe-description"
            value={description}
            onChange={changeDescription}
            placeholder="Describe what this recipe does..."
            rows={4}
            className={FIELD}
          />
        </div>

        <div className="flex items-center gap-2">
          <input type="checkbox" id="recipe-public" className="w-4 h-4" checked={isPublic} onChange={changePublic} />
          <label htmlFor="recipe-public" className="text-sm">
            Make this recipe public for others to use
          </label>
        </div>

        <button
          onClick={save}
          disabled={incomplete}
          className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Save Recipe
        </button>
      </div>
    </div>
  );
}
