import React from 'react';
import { Eye, EyeOff, Shield } from 'lucide-react';
import type { PIIReport } from '@/lib/types/api';

const SHOWN_DETECTIONS = 5;

function PIISummary(props: { report: PIIReport }) {
  const { report } = props;
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
      <div className="text-center">
        <div className="text-2xl font-bold text-amber-600">{report.total_pii_columns}</div>
        <div className="text-sm text-muted-foreground">Columns With PII</div>
      </div>
      <div className="text-center">
        <div className="text-2xl font-bold text-red-600">{report.risk_level.toUpperCase()}</div>
        <div className="text-sm text-muted-foreground">Risk Level</div>
      </div>
      <div className="text-center">
        <div className="text-2xl font-bold text-blue-600">{report.high_risk_columns}</div>
        <div className="text-sm text-muted-foreground">High-Risk Columns</div>
      </div>
    </div>
  );
}

function PIIDetections(props: { detections: PIIReport['detections'] }) {
  const { detections } = props;
  if (detections.length === 0) return null;
  const hidden = detections.length - SHOWN_DETECTIONS;
  return (
    <div>
      <h4 className="font-medium text-foreground mb-2">Detected Sensitive Information:</h4>
      <div className="space-y-2">
        {detections.slice(0, SHOWN_DETECTIONS).map((detection, index) => (
          <div key={index} className="flex items-center justify-between bg-muted p-2 rounded">
            <span className="text-sm font-medium text-foreground">{detection.column}</span>
            <div className="flex items-center space-x-2">
              <span className="text-xs bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200 px-2 py-1 rounded">
                {detection.type}
              </span>
              <span className="text-xs text-muted-foreground">
                {Math.round(detection.confidence * 100)}% confidence
              </span>
            </div>
          </div>
        ))}
        {hidden > 0 && (
          <div className="text-sm text-muted-foreground italic">
            ... and {hidden} more
          </div>
        )}
      </div>
    </div>
  );
}

const MASKED_IDLE = 'bg-green-600 hover:bg-green-700';
const MASKED_BUSY = 'bg-green-400 cursor-wait';
const ORIGINAL_IDLE = 'bg-orange-100 dark:bg-orange-900/40 hover:bg-orange-200 dark:hover:bg-orange-900/60 text-orange-800 dark:text-orange-200';
const ORIGINAL_BUSY = 'bg-orange-400 cursor-wait text-white';

interface ChoiceProps {
  confirming: boolean;
  onConfirm(maskPII: boolean): void;
  onCancel: VoidFunction;
}

function PIIChoices(props: ChoiceProps) {
  const { confirming, onConfirm, onCancel } = props;
  const uploadMasked = () => onConfirm(true);
  const uploadOriginal = () => onConfirm(false);
  const masked = confirming ? MASKED_BUSY : MASKED_IDLE;
  const original = confirming ? ORIGINAL_BUSY : ORIGINAL_IDLE;
  const maskedLabel = confirming ? 'Processing...' : 'Upload with Data Masking';
  const originalLabel = confirming ? 'Processing...' : 'Upload Original Data';
  return (
    <div className="flex flex-col sm:flex-row gap-3">
      <button
        onClick={uploadMasked}
        disabled={confirming}
        className={`flex-1 px-4 py-3 rounded-md text-white font-medium transition-colors flex items-center justify-center space-x-2 ${masked}`}
      >
        <Shield size={16} />
        <span>{maskedLabel}</span>
        <EyeOff size={16} />
      </button>
      <button
        onClick={uploadOriginal}
        disabled={confirming}
        className={`flex-1 px-4 py-3 rounded-md font-medium transition-colors flex items-center justify-center space-x-2 ${original}`}
      >
        <Eye size={16} />
        <span>{originalLabel}</span>
      </button>
      <button
        onClick={onCancel}
        className="px-4 py-3 rounded-md border border-border text-foreground hover:bg-muted transition-colors"
      >
        Cancel Upload
      </button>
    </div>
  );
}

/** The high-risk PII warning: nothing is stored until the user picks one of its choices. */
interface WarningProps extends ChoiceProps {
  show: boolean;
  report: PIIReport | null;
}

export default function PIIWarning(props: WarningProps) {
  const { show, report, confirming, onConfirm, onCancel } = props;
  if (!show || !report) return null;
  return (
    <div className="mb-6 p-6 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 rounded-lg" role="status" aria-live="polite">
      <div className="flex items-center mb-4">
        <Shield className="text-amber-500 mr-3" size={24} />
        <div>
          <h3 className="font-bold text-amber-800 dark:text-amber-200 text-lg">Sensitive Data Detected</h3>
          <p className="text-amber-700 dark:text-amber-300">
            We&apos;ve detected potentially sensitive information in your file that may require special handling.
          </p>
        </div>
      </div>

      <div className="bg-card rounded-md p-4 mb-4">
        <PIISummary report={report} />
        <PIIDetections detections={report.detections} />
      </div>

      <PIIChoices confirming={confirming} onConfirm={onConfirm} onCancel={onCancel} />

      <div className="mt-4 text-xs text-muted-foreground">
        <p>
          <strong>Data Masking:</strong> Sensitive information will be replaced with placeholder values (e.g., ***@***.com for emails).
          <br />
          <strong>Original Data:</strong> Keep sensitive information as-is. Ensure you have proper authorization for handling this data.
        </p>
      </div>
    </div>
  );
}
