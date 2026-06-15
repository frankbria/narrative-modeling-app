import React from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Upload,
  BarChart3,
  Wrench,
  Sparkles,
  Brain,
  LineChart,
  Target,
  Rocket,
  ArrowRight,
  CheckCircle,
} from 'lucide-react';

interface QuickstartStage {
  id: string;
  number: number;
  title: string;
  icon: React.ElementType;
  purpose: string;
  actions: string[];
  outcome: string;
  route: string;
  routeLabel: string;
}

/**
 * Quickstart guide (issue #152, AC2).
 *
 * A static, user-facing walkthrough of the 8-stage ML workflow:
 * upload → profile → prepare → features → train → evaluate → predict → deploy.
 */
const STAGES: QuickstartStage[] = [
  {
    id: 'upload',
    number: 1,
    title: 'Upload Data',
    icon: Upload,
    purpose: 'Bring your dataset into the platform to start building a model.',
    actions: [
      'Drag and drop a CSV or XLSX file, or browse to select one.',
      'Confirm the detected columns and preview a few rows.',
      'Start with a clean file that has a header row and one record per line.',
    ],
    outcome: 'Your data is stored securely and ready for automatic profiling.',
    route: '/upload',
    routeLabel: 'Go to Upload',
  },
  {
    id: 'profiling',
    number: 2,
    title: 'Data Profiling',
    icon: BarChart3,
    purpose: 'Understand your data before you model it.',
    actions: [
      'Review automatic column statistics, types, and distributions.',
      'Check the data-quality report for missing values and outliers.',
      'Note which column you want to predict (your target).',
    ],
    outcome: 'A clear picture of data quality and what each column contains.',
    route: '/explore',
    routeLabel: 'Go to Explore',
  },
  {
    id: 'preparation',
    number: 3,
    title: 'Data Preparation',
    icon: Wrench,
    purpose: 'Clean and transform the data so a model can learn from it.',
    actions: [
      'Apply cleaning steps (handle missing values, drop bad rows).',
      'Encode categorical columns and scale numeric ones.',
      'Build a reusable transformation chain you can review and undo.',
    ],
    outcome: 'A tidy, model-ready dataset with transformations recorded.',
    route: '/prepare',
    routeLabel: 'Go to Prepare',
  },
  {
    id: 'features',
    number: 4,
    title: 'Feature Engineering',
    icon: Sparkles,
    purpose: 'Improve model accuracy with better input features.',
    actions: [
      'Review AI-powered feature suggestions tailored to your data.',
      'Apply the suggestions you want and keep at least two features.',
      'Inspect how each feature relates to your target.',
    ],
    outcome: 'A stronger feature set that gives the model more to learn from.',
    route: '/features',
    routeLabel: 'Go to Features',
  },
  {
    id: 'training',
    number: 5,
    title: 'Model Training',
    icon: Brain,
    purpose: 'Let AutoML train and compare models for you.',
    actions: [
      'Pick your target column and start training.',
      'Let AI-guided algorithm selection rank candidate models.',
      'Watch training progress and the live model comparison.',
    ],
    outcome: 'A trained best model selected from several candidates.',
    route: '/model',
    routeLabel: 'Go to Train',
  },
  {
    id: 'evaluation',
    number: 6,
    title: 'Model Evaluation',
    icon: LineChart,
    purpose: 'Confirm the model performs well before you rely on it.',
    actions: [
      'Read the plain-language model report card.',
      'Review metrics, the confusion matrix, and ROC/PR curves.',
      'Use interpretability (feature importance, SHAP) to see why it works.',
    ],
    outcome: 'Confidence that the model is accurate and understandable.',
    route: '/evaluate',
    routeLabel: 'Go to Evaluate',
  },
  {
    id: 'prediction',
    number: 7,
    title: 'Prediction',
    icon: Target,
    purpose: 'Use the model to predict outcomes on new data.',
    actions: [
      'Fill in the auto-generated form for a single prediction.',
      'Or upload a file for batch predictions.',
      'Review confidence scores and per-prediction explanations.',
    ],
    outcome: 'Predictions you can trust, with confidence and explanations.',
    route: '/predict',
    routeLabel: 'Go to Predict',
  },
  {
    id: 'deployment',
    number: 8,
    title: 'Deployment',
    icon: Rocket,
    purpose: 'Make your model available for ongoing use.',
    actions: [
      'Export the model or deploy it behind an API.',
      'Generate an API key for programmatic access.',
      'Monitor usage once it is live.',
    ],
    outcome: 'A deployed model ready to serve predictions in production.',
    route: '/deploy',
    routeLabel: 'Go to Deploy',
  },
];

export const metadata = {
  title: 'Quickstart Guide | Narrative Modeling App',
};

export default function QuickstartPage() {
  return (
    <div className="max-w-6xl mx-auto p-6" data-testid="quickstart">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Quickstart Guide</h1>
        <p className="text-gray-600 mt-2">
          Build, evaluate, and deploy a machine-learning model in eight guided
          stages — no code required. Follow them in order or jump to any step.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Quick-navigation sidebar */}
        <nav
          aria-label="Quickstart sections"
          className="lg:col-span-1 lg:sticky lg:top-4 self-start"
        >
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">On this page</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-1 text-sm">
                {STAGES.map((stage) => (
                  <li key={stage.id}>
                    <a
                      href={`#${stage.id}`}
                      className="text-gray-700 hover:text-primary hover:underline"
                    >
                      {stage.number}. {stage.title}
                    </a>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </nav>

        {/* Stage sections */}
        <div className="lg:col-span-3 space-y-6">
          {STAGES.map((stage) => {
            const Icon = stage.icon;
            return (
              <Card key={stage.id} id={stage.id} className="scroll-mt-4">
                <CardHeader>
                  <CardTitle className="flex items-center gap-3 text-xl">
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <Icon className="h-5 w-5" />
                    </span>
                    <span>
                      Stage {stage.number}: {stage.title}
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-gray-700">{stage.purpose}</p>

                  <div>
                    <h3 className="font-semibold text-gray-900 mb-2">Key actions</h3>
                    <ul className="space-y-1">
                      {stage.actions.map((action, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                          <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
                          <span>{action}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="rounded-md bg-gray-50 p-3 text-sm">
                    <span className="font-semibold text-gray-900">What you get: </span>
                    <span className="text-gray-700">{stage.outcome}</span>
                  </div>

                  <Button asChild variant="outline" size="sm">
                    <Link href={stage.route}>
                      {stage.routeLabel}
                      <ArrowRight className="ml-1 h-4 w-4" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            );
          })}

          <Card className="bg-primary/5">
            <CardContent className="py-4 flex items-center justify-between flex-wrap gap-4">
              <div>
                <h3 className="font-semibold text-gray-900">Ready to begin?</h3>
                <p className="text-sm text-gray-600">
                  Start at Stage 1 by uploading your first dataset.
                </p>
              </div>
              <Button asChild>
                <Link href="/upload">
                  Upload Your Data
                  <ArrowRight className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
