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
  // Defer revoke: in some browsers click() returns before the download starts,
  // so revoking immediately can abort it.
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

export function SdkPanel({ modelId }: { modelId: string }) {
  const [info, setInfo] = useState<SdkInfo | null>(null);
  const [language, setLanguage] = useState('python');
  const [sources, setSources] = useState<Record<string, string>>({});
  // Separate errors so a persistent info-load failure isn't silently dismissed
  // when the user switches language tabs (which only clears the source error).
  const [infoError, setInfoError] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState<string | null>(null);
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
        if (active) setInfoError('Could not load SDK info for this model.');
      });
    return () => {
      active = false;
    };
  }, [modelId]);

  useEffect(() => {
    const key = `${modelId}:${language}`;
    if (requested.current.has(key)) return;
    requested.current.add(key);
    setSourceError(null); // clear the prior language's source error on switch
    let active = true;
    modelService
      .getSdk(modelId, language)
      .then((src) => {
        if (active) setSources((prev) => ({ ...prev, [language]: src }));
      })
      .catch(() => {
        requested.current.delete(key); // allow a retry on next mount/select
        if (active) setSourceError(`Could not load the ${language} SDK.`);
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
      setSourceError('Could not download the Postman collection.');
    }
  };

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

      {/* Error is shown inline so the tab bar stays usable and the user can retry
          another language without reloading. */}
      {(infoError || sourceError) && (
        <div className="mb-3" role="alert" aria-live="polite">
          {infoError && <p className="text-sm text-red-600">{infoError}</p>}
          {sourceError && <p className="text-sm text-red-600">{sourceError}</p>}
        </div>
      )}

      <div className="flex gap-2 mb-3" role="tablist" aria-label="SDK language">
        {languages.map((lang) => (
          <button
            key={lang}
            id={`sdk-tab-${lang}`}
            type="button"
            role="tab"
            aria-selected={language === lang}
            aria-controls="sdk-panel-content"
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

      <div
        className="relative"
        role="tabpanel"
        id="sdk-panel-content"
        aria-labelledby={`sdk-tab-${language}`}
      >
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
          {source ??
            (sourceError ? '(Failed to load — see error above)' : 'Loading…')}
        </pre>
      </div>

      <p className="text-xs text-gray-500 mt-2">
        Each SDK calls the production endpoint with your{' '}
        <code className="font-mono">X-API-Key</code>. Generate a key from your
        account settings. Sample values are placeholders — categorical features
        need a real label (see the model&apos;s input schema) to avoid a 422.
      </p>

      {info?.readme && (
        <details className="mt-3">
          <summary className="text-sm font-medium cursor-pointer">
            SDK documentation (README)
          </summary>
          <pre className="mt-2 bg-white border p-4 rounded overflow-x-auto text-xs whitespace-pre-wrap">
            {info.readme}
          </pre>
        </details>
      )}
    </div>
  );
}
