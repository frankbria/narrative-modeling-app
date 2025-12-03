/**
 * AI Mock Provider for Deterministic E2E Testing
 *
 * Provides hybrid AI mocking strategy:
 * - Mock AI responses in CI for fast, deterministic tests
 * - Use real AI in nightly runs for accuracy validation
 *
 * Usage:
 *   const aiMock = new AIMockProvider();
 *   await aiMock.mockAIRecommendations(page, 'binary_classification');
 */

import { Page } from '@playwright/test';

export interface AIRecommendation {
  problem_type: string;
  recommended_transformations: Array<{
    type: string;
    columns: string[];
    reasoning: string;
    parameters?: Record<string, any>;
  }>;
  recommended_algorithms: Array<{
    name: string;
    confidence: number;
    reasoning: string;
    hyperparameters?: Record<string, any>;
  }>;
  data_quality_issues?: Array<{
    issue: string;
    severity: 'low' | 'medium' | 'high';
    recommendation: string;
  }>;
}

export class AIMockProvider {
  private useMock: boolean;

  constructor() {
    // Use mock AI responses in CI, real AI locally or in nightly tests
    this.useMock = process.env.USE_AI_MOCK === 'true' || process.env.CI === 'true';
  }

  /**
   * Mock AI recommendation endpoint
   */
  async mockAIRecommendations(page: Page, datasetType: string) {
    if (!this.useMock) {
      console.log('🔴 Using REAL AI (not mocked)');
      return; // Use real AI
    }

    console.log(`🟡 Using MOCKED AI for dataset type: ${datasetType}`);

    // Intercept AI recommendation API calls
    await page.route('**/api/v1/ai/recommendations', async (route) => {
      const response = this.getMockedRecommendation(datasetType);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(response)
      });
    });

    // Also intercept analyze-dataset endpoint
    await page.route('**/api/v1/ai/analyze-dataset', async (route) => {
      const response = this.getMockedRecommendation(datasetType);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(response)
      });
    });
  }

  /**
   * Mock AI problem type detection
   */
  async mockProblemTypeDetection(page: Page, expectedProblemType: string) {
    if (!this.useMock) return;

    await page.route('**/api/v1/ai/detect-problem-type', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          problem_type: expectedProblemType,
          confidence: 0.92,
          reasoning: `Detected ${expectedProblemType} based on target column analysis`,
          suggested_metrics: this.getMetricsForProblemType(expectedProblemType)
        })
      });
    });
  }

  /**
   * Mock AI algorithm recommendation
   */
  async mockAlgorithmRecommendation(page: Page, problemType: string) {
    if (!this.useMock) return;

    await page.route('**/api/v1/models/recommend-algorithm', async (route) => {
      const algorithms = this.getAlgorithmRecommendations(problemType);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          recommended_algorithms: algorithms
        })
      });
    });
  }

  /**
   * Get mocked recommendation for dataset type
   */
  private getMockedRecommendation(datasetType: string): AIRecommendation {
    const recommendations: Record<string, AIRecommendation> = {
      'binary_classification': {
        problem_type: 'binary_classification',
        recommended_transformations: [
          {
            type: 'one_hot_encoding',
            columns: ['contract_type', 'payment_method'],
            reasoning: 'Convert categorical variables to numeric format for model training',
            parameters: {
              drop_first: false,
              handle_unknown: 'ignore'
            }
          },
          {
            type: 'standard_scaling',
            columns: ['age', 'tenure', 'monthly_charges', 'total_charges'],
            reasoning: 'Normalize numeric features to have mean=0 and std=1',
            parameters: {
              with_mean: true,
              with_std: true
            }
          },
          {
            type: 'boolean_encoding',
            columns: ['has_internet', 'has_phone'],
            reasoning: 'Convert boolean columns to 0/1 encoding'
          }
        ],
        recommended_algorithms: [
          {
            name: 'Random Forest',
            confidence: 0.85,
            reasoning: 'Handles imbalanced data well, robust to outliers, good feature importance',
            hyperparameters: {
              n_estimators: 100,
              max_depth: 10,
              min_samples_split: 5,
              class_weight: 'balanced'
            }
          },
          {
            name: 'Gradient Boosting',
            confidence: 0.82,
            reasoning: 'High accuracy for classification tasks, handles non-linear relationships',
            hyperparameters: {
              n_estimators: 100,
              learning_rate: 0.1,
              max_depth: 5
            }
          },
          {
            name: 'Logistic Regression',
            confidence: 0.70,
            reasoning: 'Simple baseline model, fast training, interpretable coefficients',
            hyperparameters: {
              C: 1.0,
              class_weight: 'balanced',
              max_iter: 1000
            }
          }
        ],
        data_quality_issues: [
          {
            issue: 'Imbalanced target distribution (70/30)',
            severity: 'medium',
            recommendation: 'Use class_weight="balanced" or apply SMOTE oversampling'
          }
        ]
      },

      'multiclass_classification': {
        problem_type: 'multiclass_classification',
        recommended_transformations: [
          {
            type: 'label_encoding',
            columns: ['brand', 'color'],
            reasoning: 'Convert categorical variables with multiple categories to numeric labels'
          },
          {
            type: 'min_max_scaling',
            columns: ['price', 'rating', 'weight', 'stock_quantity'],
            reasoning: 'Scale numeric features to [0, 1] range'
          }
        ],
        recommended_algorithms: [
          {
            name: 'Random Forest',
            confidence: 0.88,
            reasoning: 'Excellent for multiclass classification, handles categorical features well',
            hyperparameters: {
              n_estimators: 150,
              max_depth: 12,
              min_samples_split: 10
            }
          },
          {
            name: 'Gradient Boosting',
            confidence: 0.84,
            reasoning: 'High accuracy for multiclass problems',
            hyperparameters: {
              n_estimators: 100,
              learning_rate: 0.1
            }
          }
        ]
      },

      'regression': {
        problem_type: 'regression',
        recommended_transformations: [
          {
            type: 'target_encoding',
            columns: ['location'],
            reasoning: 'High cardinality categorical (50 unique values) - use target encoding to preserve information',
            parameters: {
              smoothing: 1.0,
              min_samples_leaf: 10
            }
          },
          {
            type: 'standard_scaling',
            columns: ['sqft', 'bedrooms', 'bathrooms', 'age', 'lot_size'],
            reasoning: 'Normalize numeric features for regression'
          },
          {
            type: 'polynomial_features',
            columns: ['sqft', 'bedrooms'],
            reasoning: 'Create interaction terms to capture non-linear relationships',
            parameters: {
              degree: 2,
              include_bias: false
            }
          }
        ],
        recommended_algorithms: [
          {
            name: 'Gradient Boosting Regressor',
            confidence: 0.90,
            reasoning: 'Captures non-linear relationships, handles feature interactions well',
            hyperparameters: {
              n_estimators: 150,
              learning_rate: 0.05,
              max_depth: 7
            }
          },
          {
            name: 'Random Forest Regressor',
            confidence: 0.85,
            reasoning: 'Robust to outliers, provides feature importance',
            hyperparameters: {
              n_estimators: 100,
              max_depth: 15
            }
          },
          {
            name: 'Linear Regression with Polynomial Features',
            confidence: 0.72,
            reasoning: 'Simple baseline, fast training, with polynomial features to capture interactions'
          }
        ],
        data_quality_issues: [
          {
            issue: 'High cardinality categorical feature (location: 50 unique values)',
            severity: 'medium',
            recommendation: 'Use target encoding instead of one-hot encoding to avoid creating 50 new features'
          }
        ]
      },

      'time_series': {
        problem_type: 'time_series',
        recommended_transformations: [
          {
            type: 'date_decomposition',
            columns: ['date'],
            reasoning: 'Extract temporal features: year, month, day_of_week, day_of_month',
            parameters: {
              features: ['year', 'month', 'day_of_week', 'day_of_month', 'is_weekend']
            }
          },
          {
            type: 'lag_features',
            columns: ['sales'],
            reasoning: 'Create lag features (t-1, t-7, t-30) to capture temporal dependencies',
            parameters: {
              lags: [1, 7, 30]
            }
          },
          {
            type: 'rolling_statistics',
            columns: ['sales', 'temperature'],
            reasoning: 'Add rolling mean and std (7-day and 30-day windows)',
            parameters: {
              windows: [7, 30],
              statistics: ['mean', 'std']
            }
          }
        ],
        recommended_algorithms: [
          {
            name: 'ARIMA',
            confidence: 0.82,
            reasoning: 'Classic time series method, handles seasonality and trends',
            hyperparameters: {
              order: [1, 1, 1],
              seasonal_order: [1, 1, 1, 7]
            }
          },
          {
            name: 'Gradient Boosting with Lag Features',
            confidence: 0.85,
            reasoning: 'Combines feature engineering with ML to capture complex patterns',
            hyperparameters: {
              n_estimators: 100,
              learning_rate: 0.1
            }
          }
        ],
        data_quality_issues: [
          {
            issue: 'Seasonal patterns detected (Nov-Dec spike)',
            severity: 'low',
            recommendation: 'Use seasonal decomposition or add month-of-year features'
          }
        ]
      },

      'clustering': {
        problem_type: 'unsupervised_clustering',
        recommended_transformations: [
          {
            type: 'standard_scaling',
            columns: ['age', 'income', 'purchase_frequency', 'avg_order_value', 'customer_lifetime_value'],
            reasoning: 'Scale all features to same range for distance-based clustering'
          },
          {
            type: 'pca',
            columns: ['age', 'income', 'purchase_frequency', 'avg_order_value', 'customer_lifetime_value'],
            reasoning: 'Reduce dimensionality to 3 components for visualization',
            parameters: {
              n_components: 3,
              whiten: true
            }
          }
        ],
        recommended_algorithms: [
          {
            name: 'K-Means',
            confidence: 0.88,
            reasoning: 'Efficient clustering for customer segmentation, interpretable centroids',
            hyperparameters: {
              n_clusters: 3,
              init: 'k-means++',
              n_init: 10
            }
          },
          {
            name: 'DBSCAN',
            confidence: 0.75,
            reasoning: 'Handles outliers well, finds clusters of arbitrary shape',
            hyperparameters: {
              eps: 0.5,
              min_samples: 5
            }
          }
        ]
      }
    };

    return recommendations[datasetType] || recommendations['binary_classification'];
  }

  /**
   * Get metrics for problem type
   */
  private getMetricsForProblemType(problemType: string): string[] {
    const metricsMap: Record<string, string[]> = {
      'binary_classification': ['accuracy', 'precision', 'recall', 'f1_score', 'auc_roc'],
      'multiclass_classification': ['accuracy', 'macro_f1', 'micro_f1', 'weighted_f1'],
      'regression': ['mae', 'mse', 'rmse', 'r2_score', 'mape'],
      'time_series': ['mae', 'mse', 'rmse', 'mape'],
      'unsupervised_clustering': ['silhouette_score', 'davies_bouldin_index', 'calinski_harabasz_score']
    };

    return metricsMap[problemType] || ['accuracy'];
  }

  /**
   * Get algorithm recommendations for problem type
   */
  private getAlgorithmRecommendations(problemType: string) {
    const recommendation = this.getMockedRecommendation(problemType);
    return recommendation.recommended_algorithms;
  }

  /**
   * Simulate AI timeout (for testing timeout handling)
   */
  async mockAITimeout(page: Page, timeoutMs: number = 150000) {
    if (!this.useMock) return;

    await page.route('**/api/v1/ai/**', async (route) => {
      // Don't respond until timeout
      await new Promise(resolve => setTimeout(resolve, timeoutMs));
      await route.abort('timedout');
    });
  }

  /**
   * Clear all AI mocks
   */
  async clearMocks(page: Page) {
    await page.unroute('**/api/v1/ai/**');
    await page.unroute('**/api/v1/models/recommend-algorithm');
  }
}
