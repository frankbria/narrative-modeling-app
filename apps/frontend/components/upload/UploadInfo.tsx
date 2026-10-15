import React from 'react';
import { CheckCircle, Database, FileText } from 'lucide-react';

export const FILE_TYPE_CARDS = (
  <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
    <div className="p-4 bg-muted rounded-lg">
      <FileText className="w-8 h-8 text-blue-600 mb-2" />
      <h3 className="font-semibold mb-1">CSV Files</h3>
      <p className="text-sm text-muted-foreground">
        Standard comma-separated values with headers
      </p>
    </div>
    <div className="p-4 bg-muted rounded-lg">
      <FileText className="w-8 h-8 text-green-600 mb-2" />
      <h3 className="font-semibold mb-1">Excel Files</h3>
      <p className="text-sm text-muted-foreground">
        .xls and .xlsx formats supported
      </p>
    </div>
    <div className="p-4 bg-muted rounded-lg">
      <Database className="w-8 h-8 text-purple-600 mb-2" />
      <h3 className="font-semibold mb-1">Connect Database</h3>
      <p className="text-sm text-muted-foreground">
        Coming soon: Direct database connections
      </p>
    </div>
  </div>
);

export const WHAT_HAPPENS_NEXT = (
  <div className="mt-8 p-4 bg-blue-50 dark:bg-blue-950/40 rounded-lg border border-blue-200 dark:border-blue-900">
    <h3 className="font-semibold mb-2 flex items-center gap-2">
      <CheckCircle className="w-5 h-5 text-blue-600" />
      What happens next?
    </h3>
    <ol className="text-sm text-foreground space-y-1 list-decimal list-inside">
      <li>Your data will be securely uploaded and processed</li>
      <li>We&apos;ll automatically analyze and profile your data</li>
      <li>You&apos;ll be guided through the 8-stage modeling workflow</li>
      <li>AI assistance will be available at every step</li>
    </ol>
  </div>
);
