'use client';

import React, { useState } from 'react';
import { BookOpen, Save, X } from 'lucide-react';
import type { SavedRecipe } from '@/lib/services/pipelineApi';
import RecipeBrowser from './RecipeBrowser';
import SaveRecipeForm from './SaveRecipeForm';

type Tab = 'browse' | 'save';

interface RecipeManagerProps {
  onClose: VoidFunction;
  onSave(name: string, description: string, isPublic: boolean): void;
  onLoad(recipe: SavedRecipe): void;
}

const ACTIVE_TAB = 'text-blue-600 border-b-2 border-blue-600';
const INACTIVE_TAB = 'text-muted-foreground hover:text-foreground';
const TAB_ICON = 'w-4 h-4 inline mr-2';

interface TabButtonProps {
  tab: Tab;
  active: Tab;
  icon: React.ReactNode;
  label: string;
  onSelect(tab: Tab): void;
}

function TabButton(props: TabButtonProps) {
  const { tab, active, onSelect } = props;
  const select = () => onSelect(tab);
  const tone = tab === active ? ACTIVE_TAB : INACTIVE_TAB;
  return (
    <button onClick={select} className={`flex-1 px-4 py-3 font-medium ${tone}`}>
      {props.icon}
      {props.label}
    </button>
  );
}

export default function RecipeManager(props: RecipeManagerProps) {
  const { onClose, onSave, onLoad } = props;
  const [activeTab, setActiveTab] = useState<Tab>('browse');
  const body = activeTab === 'browse' ? <RecipeBrowser onLoad={onLoad} /> : <SaveRecipeForm onSave={onSave} />;
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg shadow-xl w-[600px] max-h-[80vh] flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recipe Manager</h2>
          <button onClick={onClose} aria-label="Close recipe manager" className="p-1 hover:bg-muted rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="border-b">
          <div className="flex">
            <TabButton
              tab="browse"
              active={activeTab}
              icon={<BookOpen className={TAB_ICON} />}
              label="Browse Recipes"
              onSelect={setActiveTab}
            />
            <TabButton
              tab="save"
              active={activeTab}
              icon={<Save className={TAB_ICON} />}
              label="Save Recipe"
              onSelect={setActiveTab}
            />
          </div>
        </div>

        <div className="flex-1 overflow-hidden">{body}</div>
      </div>
    </div>
  );
}
