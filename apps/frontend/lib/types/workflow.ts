export enum WorkflowStage {
  DATA_LOADING = 'data_loading',
  DATA_PROFILING = 'data_profiling',
  DATA_PREPARATION = 'data_preparation',
  FEATURE_ENGINEERING = 'feature_engineering',
  MODEL_TRAINING = 'model_training',
  MODEL_EVALUATION = 'model_evaluation',
  PREDICTION = 'prediction',
  DEPLOYMENT = 'deployment'
}

export interface StageConfig {
  id: WorkflowStage;
  name: string;
  description: string;
  icon: string; // Lucide icon name
  route: string;
  requiredStages: WorkflowStage[]; // Stages that must be completed before this one
}

export interface WorkflowState {
  currentStage: WorkflowStage;
  completedStages: Set<WorkflowStage>;
  stageData: Record<WorkflowStage, any>;
  datasetId?: string;
  modelId?: string;
  deploymentId?: string;
  // Transformation history state
  historyPosition?: number;
  canUndo?: boolean;
  canRedo?: boolean;
}

export interface WorkflowContextType {
  state: WorkflowState;
  /**
   * True once workflow state has been restored from storage. Stage-gating
   * redirects must wait for this — checking canAccessStage before hydration
   * always sees an empty state and wrongly kicks the user back to /upload.
   */
  isHydrated: boolean;
  /**
   * A helpful message shown when a stage guard redirects the user away from a
   * stage they can't access yet (e.g. opening /predict with no trained model).
   * Rendered globally by StageGuardBanner; `null` when there is nothing to show.
   */
  guardMessage: string | null;
  canAccessStage: (stage: WorkflowStage) => boolean;
  /**
   * Mark a stage complete and record its data. By default this no longer
   * navigates — explicit "Continue" CTAs (StageNavigation) drive transitions so
   * the user stays in control. Pass `{ autoAdvance: true }` to advance to the
   * next stage automatically once its prerequisites are met.
   */
  completeStage: (
    stage: WorkflowStage,
    data?: any,
    opts?: { autoAdvance?: boolean }
  ) => void;
  setCurrentStage: (stage: WorkflowStage) => void;
  setDatasetId: (datasetId: string) => void;
  resetWorkflow: () => void;
  loadWorkflow: (datasetId: string) => Promise<void>;
  saveWorkflow: () => Promise<void>;
  /** Navigate forward to the next stage (route-aware). No-op on the last stage. */
  goToNextStage: () => void;
  /** Navigate back to the previous stage (route-aware). No-op on the first stage. */
  goToPreviousStage: () => void;
  /** Redirect to `targetStage` and surface `message` via StageGuardBanner. */
  requestStageRedirect: (targetStage: WorkflowStage, message: string) => void;
  /** Dismiss the current guard message. */
  clearGuardMessage: () => void;
  // Transformation history methods
  updateHistoryPosition: (position: number) => void;
  updateHistoryState: (historyState: { position: number; canUndo: boolean; canRedo: boolean }) => void;
  refreshHistory: () => Promise<void>;
}

export const WORKFLOW_STAGES: StageConfig[] = [
  {
    id: WorkflowStage.DATA_LOADING,
    name: 'Data Loading',
    description: 'Upload and connect your data sources',
    icon: 'Upload',
    route: '/upload',
    requiredStages: []
  },
  {
    id: WorkflowStage.DATA_PROFILING,
    name: 'Data Profiling',
    description: 'Explore and understand your data',
    icon: 'BarChart3',
    route: '/explore',
    requiredStages: [WorkflowStage.DATA_LOADING]
  },
  {
    id: WorkflowStage.DATA_PREPARATION,
    name: 'Data Preparation',
    description: 'Clean and transform your data',
    icon: 'Wrench',
    route: '/prepare',
    requiredStages: [WorkflowStage.DATA_PROFILING]
  },
  {
    id: WorkflowStage.FEATURE_ENGINEERING,
    name: 'Feature Engineering',
    description: 'Create and select features for modeling',
    icon: 'Sparkles',
    route: '/features',
    requiredStages: [WorkflowStage.DATA_PREPARATION]
  },
  {
    id: WorkflowStage.MODEL_TRAINING,
    name: 'Model Training',
    description: 'Train and optimize ML models',
    icon: 'Brain',
    route: '/model',
    requiredStages: [WorkflowStage.FEATURE_ENGINEERING]
  },
  {
    id: WorkflowStage.MODEL_EVALUATION,
    name: 'Model Evaluation',
    description: 'Evaluate model performance',
    icon: 'LineChart',
    route: '/evaluate',
    requiredStages: [WorkflowStage.MODEL_TRAINING]
  },
  {
    id: WorkflowStage.PREDICTION,
    name: 'Prediction',
    description: 'Make predictions with your model',
    icon: 'Target',
    route: '/predict',
    requiredStages: [WorkflowStage.MODEL_EVALUATION]
  },
  {
    id: WorkflowStage.DEPLOYMENT,
    name: 'Deployment',
    description: 'Deploy your model to production',
    icon: 'Rocket',
    route: '/deploy',
    requiredStages: [WorkflowStage.PREDICTION]
  }
];