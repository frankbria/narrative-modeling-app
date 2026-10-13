"use client";

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { BookOpen, Clock, Play, Zap } from 'lucide-react';
import { SampleDatasetSelector } from '@/components/SampleDatasetSelector';

interface HighlightProps {
  icon: string;
  title: string;
  text: string;
}

const GUIDES = ['Understanding Data Quality', 'Choosing the Right Model', 'Interpreting Results'];

/** The landing card a user sees before they have picked a step. */
export function OnboardingWelcome(props: { onStart: VoidFunction }) {
  const { onStart } = props;
  const router = useRouter();
  // Load complete: take the user to their new dataset.
  const openDataset = (datasetId: string) => router.push(`/explore/${datasetId}`);
  return (
    <Card className="@container">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Zap className="h-6 w-6 text-blue-600" />
          Welcome to SheetPredict!
        </CardTitle>
        <CardDescription>Your AI-powered machine learning platform</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="text-center space-y-4">
          <div className="text-lg">
            Ready to build your first machine learning model?
            {' '}Our interactive tutorial will guide you through every step!
          </div>

          <div className="grid grid-cols-1 @xl:grid-cols-3 gap-4 text-center">
            <Highlight icon="📊" title="Upload Data" text="Start with your CSV file" />
            <Highlight icon="🤖" title="Train Models" text="AI finds the best algorithm" />
            <Highlight icon="🚀" title="Make Predictions" text="Get insights from your data" />
          </div>

          <Button onClick={onStart} size="lg" className="bg-blue-600 hover:bg-blue-700">
            <Play className="mr-2 h-4 w-4" />
            Start Tutorial
          </Button>
        </div>

        <Tabs defaultValue="overview" className="mt-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="sample-data">Sample Data</TabsTrigger>
            <TabsTrigger value="help">Help & Resources</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            {OVERVIEW}
          </TabsContent>

          <TabsContent value="sample-data">
            <SampleDatasetSelector onDatasetSelected={openDataset} />
          </TabsContent>

          <TabsContent value="help" className="space-y-4">
            <Documentation />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function Highlight(props: HighlightProps) {
  const { icon, title, text } = props;
  return (
    <div className="p-4 border rounded-lg">
      <div className="text-2xl mb-2">{icon}</div>
      <div className="font-medium">{title}</div>
      <div className="text-sm text-muted-foreground">{text}</div>
    </div>
  );
}

const OVERVIEW = (
  <div className="prose dark:prose-invert max-w-none">
    <h3>What you&apos;ll learn:</h3>
    <ul>
      <li>How to upload and validate your data</li>
      <li>Understanding data quality and preparation</li>
      <li>Training machine learning models with AutoML</li>
      <li>Making predictions and interpreting results</li>
      <li>Exporting models for production use</li>
    </ul>

    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Clock className="h-4 w-4" />
      Estimated time: 20-30 minutes
    </p>
  </div>
);

// The Video Tutorials card was removed (#281): no video content exists, so its
// buttons were inert dead-ends.
function Documentation() {
  const links = GUIDES.map((label) => (
    <Button key={label} asChild variant="ghost" className="w-full justify-start">
      <Link href="/quickstart">{label}</Link>
    </Button>
  ));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BookOpen className="h-5 w-5" />
          Documentation
        </CardTitle>
        <CardDescription>Step-by-step guides for every stage of the workflow.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">{links}</div>
      </CardContent>
    </Card>
  );
}
