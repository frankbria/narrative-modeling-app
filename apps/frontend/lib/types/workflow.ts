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
}

export interface WorkflowContextType {
  state: WorkflowState;
  canAccessStage: (stage: WorkflowStage) => boolean;
  completeStage: (stage: WorkflowStage, data?: any) => void;
  setCurrentStage: (stage: WorkflowStage) => void;
  setDatasetId: (datasetId: string) => void;
  resetWorkflow: () => void;
  loadWorkflow: (datasetId: string) => Promise<void>;
  saveWorkflow: () => Promise<void>;
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