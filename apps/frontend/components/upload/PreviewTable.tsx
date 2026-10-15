import React from 'react';
import { CheckCircle, Shield } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { PIIReport } from '@/lib/types/api';
import type { PreviewCell, PreviewData } from './uploadFlow';

function PIIBadge(props: { report: PIIReport | undefined }) {
  const { report } = props;
  if (!report) return null;
  return (
    <div className="flex items-center space-x-2">
      {report.has_pii ? <PIIRisk level={report.risk_level} /> : NO_PII}
    </div>
  );
}

function PIIRisk(props: { level: string }) {
  const { level } = props;
  return (
    <>
      <Shield className="text-amber-500" size={16} />
      <span className="text-sm text-amber-700 dark:text-amber-300 font-medium">
        PII {level.toUpperCase()} RISK
      </span>
    </>
  );
}

const NO_PII = (
  <>
    <CheckCircle className="text-green-500" size={16} />
    <span className="text-sm text-green-700 dark:text-green-300 font-medium">NO PII DETECTED</span>
  </>
);

function cellText(cell: PreviewCell | undefined): string {
  return cell !== null && cell !== undefined ? String(cell) : '';
}

function rowColour(rowIndex: number): string {
  return rowIndex % 2 === 0 ? 'bg-card' : 'bg-muted';
}

export default function PreviewTable(props: { preview: PreviewData | null }) {
  const { preview } = props;
  if (!preview) return null;
  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Preview Data</h2>
        <PIIBadge report={preview.pii_report} />
      </div>
      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-800">
              {preview.headers.map((header, index) => (
                <TableHead key={index} className="text-white font-semibold">{header}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {preview.previewData.map((row, rowIndex) => (
              <TableRow key={rowIndex} className={rowColour(rowIndex)}>
                {row.map((cell, cellIndex) => (
                  <TableCell key={cellIndex} className="text-foreground">
                    {cellText(cell)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
