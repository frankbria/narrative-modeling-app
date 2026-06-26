'use client';

import React, { useEffect, useRef, useState } from 'react';
import { modelService } from '@/lib/services/model';
import type { SdkInfo } from '@/lib/services/model';
import { Copy, Download, Check, Code } from 'lucide-react';

/**
 * Per-deployment SDK panel (issue #86).
 *
 * Surfaces the auto-generated client SDKs (Python / TypeScript / JavaScript /
 * cURL) for a deployed model, plus a downloadable Postman collection. Each SDK
 * targets the real production serving contract (`POST {endpoint}/predict` with an
 * `X-API-Key` header) and is built from the model's actual feature names.
 */

const FILE_EXT: Record<string, string> = {
  python: 'py',
  typescript: 'ts',
  javascript: 'js',
  curl: 'sh',
};

const LABELS: Record<string, string> = {
  python: 'Python',
  typescript: 'TypeScript',
  javascript: 'JavaScript',
  curl: 'cURL',
};

function download(filename: string, content: string, type = 'text/plain') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function SdkPanel({ modelId }: { modelId: string }) {
  const [info, setInfo] = useState<SdkInfo | null>(null);
  const [language, setLanguage] = useState('python');
  const [sources, setSources] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  // Tracks which languages have been requested so the fetch effect doesn't
  // re-run every time `sources` changes (it only depends on modelId+language).
  const requested = useRef<Set<string>>(new Set());

  useEffect(() => {
    let active = true;
    modelService
      .getSdkInfo(modelId)
      .then((data) => {
        if (active) setInfo(data);
      })
      .catch(() => {
        if (active) setError('Could not load SDK info for this model.');
      });
    return () => {
      active = false;
    };
  }, [modelId]);

  useEffect(() => {
    const key = `${modelId}:${language}`;
    if (requested.current.has(key)) return;
    requested.current.add(key);
    let active = true;
    modelService
      .getSdk(modelId, language)
      .then((src) => {
        if (active) setSources((prev) => ({ ...prev, [language]: src }));
      })
      .catch(() => {
        requested.current.delete(key); // allow a retry on next mount/select
        if (active) setError(`Could not load the ${language} SDK.`);
      });
    return () => {
      active = false;
    };
  }, [modelId, language]);

  const source = sources[language];

  const handleCopy = async () => {
    if (!source) return;
    await navigator.clipboard.writeText(source);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleDownloadPostman = async () => {
    try {
      const collection = await modelService.getSdkPostman(modelId);
      download(
        `${modelId}-postman-collection.json`,
        JSON.stringify(collection, null, 2),
        'application/json'
      );
    } catch {
      setError('Could not download the Postman collection.');
    }
  };

  if (error) {
    return (
      <div className="bg-gray-50 rounded-lg p-6">
        <h3 className="font-semibold mb-2 flex items-center gap-2">
          <Code className="w-5 h-5" /> Client SDKs
        </h3>
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  const languages = info?.languages ?? ['python', 'typescript', 'javascript', 'curl'];

  return (
    <div className="bg-gray-50 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold flex items-center gap-2">
          <Code className="w-5 h-5" /> Client SDKs
        </h3>
        <button
          type="button"
          onClick={handleDownloadPostman}
          className="inline-flex items-center gap-1 text-sm text-blue-700 hover:underline"
        >
          <Download className="w-4 h-4" />
          Postman collection
        </button>
      </div>

      <div className="flex gap-2 mb-3" role="tablist" aria-label="SDK language">
        {languages.map((lang) => (
          <button
            key={lang}
            type="button"
            role="tab"
            aria-selected={language === lang}
            onClick={() => setLanguage(lang)}
            className={`px-3 py-1.5 rounded text-sm font-medium ${
              language === lang
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-100 border'
            }`}
          >
            {LABELS[lang] ?? lang}
          </button>
        ))}
      </div>

      <div className="relative">
        <div className="absolute right-2 top-2 flex gap-1">
          <button
            type="button"
            onClick={handleCopy}
            aria-label="Copy SDK source"
            disabled={!source}
            className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded text-white disabled:opacity-50"
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
          </button>
          <button
            type="button"
            onClick={() =>
              source &&
              download(`${modelId}-client.${FILE_EXT[language] ?? 'txt'}`, source)
            }
            aria-label="Download SDK source"
            disabled={!source}
            className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded text-white disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
        <pre className="bg-gray-800 text-gray-100 p-4 rounded overflow-x-auto text-sm max-h-96">
          {source ?? 'Loading…'}
        </pre>
      </div>

      <p className="text-xs text-gray-500 mt-2">
        Each SDK calls the production endpoint with your{' '}
        <code className="font-mono">X-API-Key</code>. Generate a key from your
        account settings.
      </p>
    </div>
  );
}
