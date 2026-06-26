'use client';

import React, { useEffect, useState } from 'react';
import { modelService } from '@/lib/services/model';
import type { ModelFeatureDescriptor } from '@/lib/services/model';
import { Play, AlertCircle, CheckCircle } from 'lucide-react';

/**
 * In-page tester for a deployed model's production REST endpoint (issue #84, AC4).
 *
 * Calls the real authenticated serving route
 * (`POST {endpoint}/predict` with an `X-API-Key` header) — the same contract
 * external callers use — so the user can verify their deployment end-to-end.
 * `endpoint` is the deployment endpoint surfaced on deploy (already the
 * `${API_URL}/production/v1/models/{id}` base); the predict URL is `${endpoint}/predict`.
 */
export function EndpointTester({ modelId, endpoint }: { modelId: string; endpoint: string }) {
  const [features, setFeatures] = useState<ModelFeatureDescriptor[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ prediction: unknown; confidence?: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    modelService
      .getModelFeatures(modelId)
      .then((data) => {
        if (active) setFeatures(data.features);
      })
      .catch(() => {
        if (active) setError('Could not load the model input schema.');
      });
    return () => {
      active = false;
    };
  }, [modelId]);

  const runTest = async () => {
    setError(null);
    setResult(null);
    if (!apiKey.trim()) {
      setError('Enter an API key to call the endpoint.');
      return;
    }
    setLoading(true);
    try {
      // Coerce numeric inputs so the model receives numbers, not strings.
      const record: Record<string, unknown> = {};
      for (const f of features) {
        const raw = values[f.name] ?? '';
        record[f.name] = f.type === 'number' && raw !== '' ? Number(raw) : raw;
      }
      const response = await fetch(`${endpoint}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey.trim() },
        body: JSON.stringify({ data: [record], include_probabilities: true }),
      });
      if (!response.ok) {
        const detail = await response.text();
        setError(`Request failed (${response.status}). ${detail.slice(0, 200)}`);
        return;
      }
      const data = await response.json();
      setResult({ prediction: data.predictions?.[0], confidence: data.confidence?.[0] });
    } catch (e) {
      setError(`Request error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6" data-testid="endpoint-tester">
      <h3 className="font-semibold mb-1">Test Your Endpoint</h3>
      <p className="text-sm text-gray-600 mb-4">
        Send a live request to your deployed model using an API key from your account settings.
      </p>

      <div className="mb-4">
        <label className="block text-sm font-medium mb-1" htmlFor="endpoint-tester-key">
          API Key
        </label>
        <input
          id="endpoint-tester-key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="sk_live_..."
          className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {features.length > 0 && (
        <div className="grid grid-cols-2 gap-4 mb-4">
          {features.map((feature) => (
            <div key={feature.name}>
              <label className="block text-sm font-medium mb-1" htmlFor={`tester-${feature.name}`}>
                {feature.name}
              </label>
              {feature.type === 'categorical' && feature.options?.length ? (
                <select
                  id={`tester-${feature.name}`}
                  data-feature={feature.name}
                  value={values[feature.name] ?? ''}
                  onChange={(e) => setValues((p) => ({ ...p, [feature.name]: e.target.value }))}
                  className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">—</option>
                  {feature.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={`tester-${feature.name}`}
                  data-feature={feature.name}
                  type={feature.type === 'number' ? 'number' : 'text'}
                  value={values[feature.name] ?? ''}
                  onChange={(e) => setValues((p) => ({ ...p, [feature.name]: e.target.value }))}
                  className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              )}
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={runTest}
        disabled={loading}
        data-testid="run-endpoint-test"
        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        <Play className="w-4 h-4" />
        {loading ? 'Sending...' : 'Send Test Request'}
      </button>

      {error && (
        <div
          data-testid="endpoint-tester-error"
          className="mt-4 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700"
        >
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div
          data-testid="endpoint-tester-result"
          className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg"
        >
          <div className="flex items-center gap-2 font-semibold text-green-700">
            <CheckCircle className="w-4 h-4" />
            Prediction
          </div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{String(result.prediction)}</div>
          {result.confidence != null && (
            <p className="text-sm text-gray-600 mt-1">
              Confidence: {(result.confidence * 100).toFixed(1)}%
            </p>
          )}
        </div>
      )}
    </div>
  );
}
