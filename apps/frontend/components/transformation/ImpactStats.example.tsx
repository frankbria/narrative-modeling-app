/**
 * ImpactStats Component Usage Examples
 *
 * This file demonstrates how to use the ImpactStats component
 * in various scenarios.
 */

import React from 'react';
import { ImpactStats } from './ImpactStats';

/**
 * Example 1: Basic Impact Stats Display
 * Shows transformation impact with standard metrics
 */
export function BasicImpactStatsExample() {
  const impactStats = {
    rows_affected: 1250,
    values_changed: 3847,
    columns_affected: ['age', 'salary', 'department'],
    quality_score_before: 0.72,
    quality_score_after: 0.88,
  };

  return <ImpactStats impactStats={impactStats} />;
}

/**
 * Example 2: Impact Stats with Value Distributions
 * Shows before/after distributions for affected columns
 */
export function ImpactStatsWithDistributionsExample() {
  const impactStats = {
    rows_affected: 5000,
    values_changed: 12500,
    columns_affected: ['status', 'category', 'region'],
    quality_score_before: 0.65,
    quality_score_after: 0.91,
    value_distributions: {
      status: {
        before: {
          'Active': 3000,
          'Inactive': 1500,
          'Pending': 500,
          'Unknown': 0,
        },
        after: {
          'Active': 3500,
          'Inactive': 1200,
          'Pending': 300,
          'Unknown': 0,
        },
      },
      category: {
        before: {
          'A': 1500,
          'B': 2000,
          'C': 1500,
        },
        after: {
          'A': 1800,
          'B': 2100,
          'C': 1100,
        },
      },
    },
  };

  return <ImpactStats impactStats={impactStats} />;
}

/**
 * Example 3: High Impact Transformation
 * Shows significant quality improvement
 */
export function HighImpactExample() {
  const impactStats = {
    rows_affected: 50000,
    values_changed: 125000,
    columns_affected: [
      'customer_name',
      'email',
      'phone',
      'address',
      'postal_code',
      'country',
    ],
    quality_score_before: 0.45,
    quality_score_after: 0.95,
    value_distributions: {
      customer_name: {
        before: {
          'UNKNOWN': 2000,
          'N/A': 1500,
          'null': 500,
          'John Doe': 100,
        },
        after: {
          'UNKNOWN': 0,
          'N/A': 0,
          'null': 0,
          'Valid Names': 4000,
        },
      },
    },
  };

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-4">Data Standardization Impact</h2>
      <ImpactStats impactStats={impactStats} />
    </div>
  );
}

/**
 * Example 4: No Quality Change
 * Shows transformation with neutral quality impact
 */
export function NeutralImpactExample() {
  const impactStats = {
    rows_affected: 2000,
    values_changed: 5000,
    columns_affected: ['format_column', 'structure_column'],
    quality_score_before: 0.85,
    quality_score_after: 0.85, // No change
  };

  return <ImpactStats impactStats={impactStats} />;
}

/**
 * Example 5: Quality Degradation
 * Shows transformation with decreased quality
 */
export function QualityDegradationExample() {
  const impactStats = {
    rows_affected: 3000,
    values_changed: 8000,
    columns_affected: ['sensitive_data', 'encrypted_field'],
    quality_score_before: 0.92,
    quality_score_after: 0.78,
    value_distributions: {
      sensitive_data: {
        before: {
          'Verified': 2500,
          'Unverified': 400,
          'Corrupted': 100,
        },
        after: {
          'Masked': 2800,
          'Encrypted': 200,
          'Removed': 0,
        },
      },
    },
  };

  return <ImpactStats impactStats={impactStats} />;
}

/**
 * Example 6: Large Scale Transformation
 * Shows comprehensive impact with multiple distributions
 */
export function LargeScaleTransformationExample() {
  const impactStats = {
    rows_affected: 100000,
    values_changed: 450000,
    columns_affected: [
      'id',
      'name',
      'email',
      'phone',
      'status',
      'created_date',
      'last_updated',
      'region',
      'department',
      'role',
    ],
    quality_score_before: 0.58,
    quality_score_after: 0.94,
    value_distributions: {
      status: {
        before: {
          'active': 45000,
          'inactive': 35000,
          'pending': 15000,
          'null': 5000,
        },
        after: {
          'active': 50000,
          'inactive': 38000,
          'pending': 10000,
          'unknown': 2000,
        },
      },
      region: {
        before: {
          'USA': 40000,
          'Europe': 30000,
          'Asia': 20000,
          'Other': 10000,
        },
        after: {
          'North America': 45000,
          'Western Europe': 32000,
          'Eastern Europe': 10000,
          'Asia-Pacific': 25000,
          'Other': 18000,
        },
      },
      department: {
        before: {
          'Sales': 30000,
          'Engineering': 25000,
          'HR': 15000,
          'Operations': 20000,
          'Unknown': 10000,
        },
        after: {
          'Sales': 32000,
          'Engineering': 28000,
          'HR': 15000,
          'Operations': 22000,
          'Executive': 3000,
        },
      },
    },
  };

  return (
    <div className="p-4 bg-gray-50">
      <h2 className="text-3xl font-bold mb-2">Enterprise Data Migration</h2>
      <p className="text-gray-600 mb-6">
        Comprehensive impact analysis for system-wide transformation
      </p>
      <ImpactStats impactStats={impactStats} />
    </div>
  );
}

/**
 * Example 7: Minimal Distribution Data
 * Shows single value distribution
 */
export function MinimalDistributionExample() {
  const impactStats = {
    rows_affected: 500,
    values_changed: 1200,
    columns_affected: ['status'],
    quality_score_before: 0.82,
    quality_score_after: 0.89,
    value_distributions: {
      status: {
        before: {
          'A': 250,
          'B': 150,
          'C': 100,
        },
        after: {
          'Active': 280,
          'Inactive': 130,
          'Pending': 90,
        },
      },
    },
  };

  return <ImpactStats impactStats={impactStats} />;
}

/**
 * Integration with Transformation Pipeline
 *
 * Usage in a real transformation workflow:
 */
export function TransformationPipelineIntegration() {
  // This would typically come from your backend API
  const [transformationResults, setTransformationResults] = React.useState(null);

  const handleTransformation = async () => {
    try {
      const response = await fetch('/api/transformations/apply', {
        method: 'POST',
        body: JSON.stringify({
          dataset_id: 'dataset-123',
          transformations: [
            {
              type: 'standardize',
              columns: ['name', 'email'],
            },
            {
              type: 'fill_missing',
              columns: ['age', 'salary'],
              method: 'mean',
            },
          ],
        }),
      });

      const data = await response.json();
      setTransformationResults(data.impact_statistics);
    } catch (error) {
      console.error('Transformation failed:', error);
    }
  };

  return (
    <div className="space-y-4">
      <button
        onClick={handleTransformation}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
      >
        Apply Transformation
      </button>

      {transformationResults && (
        <ImpactStats impactStats={transformationResults} />
      )}
    </div>
  );
}
