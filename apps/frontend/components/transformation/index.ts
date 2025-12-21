/**
 * Transformation Components Export
 *
 * This file provides a central export point for all transformation-related components.
 * Use this to import components with clean, organized imports.
 *
 * @example
 * import {
 *   TransformationConfigDialog,
 *   TransformationConfig,
 * } from '@/components/transformation';
 */

export {
  TransformationConfigDialog,
  type TransformationConfigDialogProps,
  type TransformationConfig,
} from './TransformationConfigDialog';

export { default as TransformationPipeline } from './TransformationPipeline';
export { default as TransformationChainView } from './TransformationChainView';
export { default as ColumnSelector } from './ColumnSelector';
export { default as TransformationNode } from './TransformationNode';
export { default as TransformationSidebar } from './TransformationSidebar';
export { default as RecipeManager } from './RecipeManager';
export { default as PreviewPanel } from './PreviewPanel';
export {
  PreviewControls,
  type PreviewControlsProps,
} from './PreviewControls';
export {
  TransformationPreview,
  type TransformationPreviewProps,
  type PreviewResult,
  type PreviewResponse,
  type ImpactStatistics,
} from './TransformationPreview';

export {
  ImpactStats,
  type ImpactStatsProps,
} from './ImpactStats';

export { HistoryItem } from './HistoryItem';
export { UndoRedoControls } from './UndoRedoControls';
export { TransformationHistory } from './TransformationHistory';

// Export integration examples for documentation
export {
  BasicPipelineIntegration,
  PipelineWithPreview,
  PipelineWithEditDelete,
  MultiTypeTransformationBuilder,
  TRANSFORMATION_CATALOG,
} from './TransformationConfigDialog.integration.example';
