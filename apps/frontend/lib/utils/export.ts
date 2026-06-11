/**
 * Evaluation report exports (issue #79): CSV and PDF downloads for the
 * model evaluation dashboard. The build* functions are pure so tests can
 * assert output without touching DOM downloads.
 */

import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import {
  isClassificationMetrics,
  type ModelEvaluationResponse
} from '@/lib/types/evaluation'

/** Escape a CSV field per RFC 4180 (SelectedFeatureSet precedent). */
function escapeCsvField(field: string): string {
  if (field.includes(',') || field.includes('"') || field.includes('\n')) {
    return `"${field.replace(/"/g, '""')}"`
  }
  return field
}

function csvRow(fields: Array<string | number>): string {
  return fields.map((field) => escapeCsvField(String(field))).join(',')
}

/** Scalar metric name/value pairs for the Metrics section. */
function scalarMetricRows(evaluation: ModelEvaluationResponse): Array<[string, number]> {
  const { metrics } = evaluation
  if (!metrics) {
    return Object.entries(evaluation.stored_metrics)
  }
  if (isClassificationMetrics(metrics)) {
    const rows: Array<[string, number]> = [
      ['accuracy', metrics.accuracy],
      ['precision_macro', metrics.precision_macro],
      ['precision_weighted', metrics.precision_weighted],
      ['recall_macro', metrics.recall_macro],
      ['recall_weighted', metrics.recall_weighted],
      ['f1_macro', metrics.f1_macro],
      ['f1_weighted', metrics.f1_weighted]
    ]
    if (metrics.roc_auc !== null) rows.push(['roc_auc', metrics.roc_auc])
    if (metrics.log_loss !== null) rows.push(['log_loss', metrics.log_loss])
    return rows
  }
  const rows: Array<[string, number]> = [
    ['mae', metrics.mae],
    ['mse', metrics.mse],
    ['rmse', metrics.rmse],
    ['r2', metrics.r2]
  ]
  if (metrics.mape !== null) rows.push(['mape', metrics.mape])
  return rows
}

/** Feature importances sorted descending. */
function sortedFeatureImportance(
  featureImportance: Record<string, number>
): Array<[string, number]> {
  return Object.entries(featureImportance).sort(([, a], [, b]) => b - a)
}

/** Build the full evaluation report as a CSV string (pure; no DOM). */
export function buildEvaluationCSV(evaluation: ModelEvaluationResponse): string {
  const lines: string[] = []

  // Model Info
  lines.push('Model Info')
  lines.push(csvRow(['Field', 'Value']))
  lines.push(csvRow(['Model ID', evaluation.model_id]))
  lines.push(csvRow(['Name', evaluation.model_name ?? '']))
  lines.push(csvRow(['Algorithm', evaluation.algorithm ?? '']))
  lines.push(csvRow(['Problem Type', evaluation.problem_type]))
  lines.push(csvRow(['Evaluated At', evaluation.evaluated_at]))

  // Metrics
  lines.push('')
  lines.push('Metrics')
  lines.push(csvRow(['Metric', 'Value']))
  scalarMetricRows(evaluation).forEach(([name, value]) => {
    lines.push(csvRow([name, value]))
  })

  // Per-class metrics (classification only)
  const { metrics } = evaluation
  if (metrics && isClassificationMetrics(metrics)) {
    lines.push('')
    lines.push('Per-Class Metrics')
    lines.push(csvRow(['Class', 'Precision', 'Recall', 'F1', 'Support']))
    Object.entries(metrics.per_class_metrics).forEach(([label, perClass]) => {
      lines.push(
        csvRow([label, perClass.precision, perClass.recall, perClass.f1, perClass.support])
      )
    })
  }

  // Confusion matrix (classification only)
  if (evaluation.confusion_matrix) {
    const { labels, matrix } = evaluation.confusion_matrix
    lines.push('')
    lines.push('Confusion Matrix')
    lines.push(csvRow(['Actual \\ Predicted', ...labels]))
    matrix.forEach((row, i) => {
      lines.push(csvRow([labels[i], ...row]))
    })
  }

  // Feature importance
  if (evaluation.feature_importance) {
    lines.push('')
    lines.push('Feature Importance')
    lines.push(csvRow(['Feature', 'Importance']))
    sortedFeatureImportance(evaluation.feature_importance).forEach(([feature, value]) => {
      lines.push(csvRow([feature, value]))
    })
  }

  return lines.join('\n')
}

/** Trigger a browser download of a Blob (SelectedFeatureSet precedent). */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/** Download the evaluation report as evaluation-{model_id}.csv. */
export function exportEvaluationCSV(evaluation: ModelEvaluationResponse): void {
  const csv = buildEvaluationCSV(evaluation)
  downloadBlob(new Blob([csv], { type: 'text/csv' }), `evaluation-${evaluation.model_id}.csv`)
}

interface AutoTableCursor {
  lastAutoTable?: { finalY: number }
}

/** Build the evaluation PDF (pure builder; callers decide how to save). */
export function buildEvaluationPDFDoc(evaluation: ModelEvaluationResponse): jsPDF {
  const doc = new jsPDF()
  const margin = 14
  const pageWidth = doc.internal.pageSize.getWidth()
  const textWidth = pageWidth - margin * 2
  let y = 20

  // Title
  doc.setFontSize(16)
  doc.setFont('helvetica', 'bold')
  doc.text('Model Evaluation Report', margin, y)
  y += 10

  // Model metadata
  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')
  const metadata = [
    `Model: ${evaluation.model_name ?? evaluation.model_id}`,
    `Algorithm: ${evaluation.algorithm ?? 'Unknown'}`,
    `Problem type: ${evaluation.problem_type}`,
    `Evaluated at: ${evaluation.evaluated_at}`
  ]
  metadata.forEach((line) => {
    doc.text(line, margin, y)
    y += 6
  })
  y += 4

  const finalY = (): number =>
    (doc as unknown as AutoTableCursor).lastAutoTable?.finalY ?? y

  // Metrics table
  doc.setFontSize(12)
  doc.setFont('helvetica', 'bold')
  doc.text('Metrics', margin, y)
  y += 4
  autoTable(doc, {
    startY: y,
    head: [['Metric', 'Value']],
    body: scalarMetricRows(evaluation).map(([name, value]) => [name, String(value)])
  })
  y = finalY() + 10

  const { metrics } = evaluation
  if (metrics && isClassificationMetrics(metrics)) {
    // Per-class metrics table
    doc.setFontSize(12)
    doc.text('Per-Class Metrics', margin, y)
    y += 4
    autoTable(doc, {
      startY: y,
      head: [['Class', 'Precision', 'Recall', 'F1', 'Support']],
      body: Object.entries(metrics.per_class_metrics).map(([label, perClass]) => [
        label,
        String(perClass.precision),
        String(perClass.recall),
        String(perClass.f1),
        String(perClass.support)
      ])
    })
    y = finalY() + 10
  }

  // AI explanation (wrapped text)
  if (evaluation.ai_explanation) {
    const explanation = evaluation.ai_explanation
    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Model Report Card', margin, y)
    y += 6
    doc.setFontSize(10)
    doc.setFont('helvetica', 'normal')

    const sections: Array<[string, string[]]> = [
      ['Assessment', [explanation.overall_assessment]],
      ['Strengths', explanation.strengths],
      ['Concerns', explanation.concerns],
      ['Recommendations', explanation.recommendations]
    ]
    sections.forEach(([heading, items]) => {
      if (items.length === 0) return
      doc.setFont('helvetica', 'bold')
      doc.text(heading, margin, y)
      y += 5
      doc.setFont('helvetica', 'normal')
      items.forEach((item) => {
        const wrapped = doc.splitTextToSize(item, textWidth) as string[]
        wrapped.forEach((line) => {
          if (y > doc.internal.pageSize.getHeight() - 20) {
            doc.addPage()
            y = 20
          }
          doc.text(line, margin, y)
          y += 5
        })
      })
      y += 3
    })
  }

  // Confusion matrix table (classification only)
  if (evaluation.confusion_matrix) {
    const { labels, matrix } = evaluation.confusion_matrix
    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Confusion Matrix', margin, y)
    y += 4
    autoTable(doc, {
      startY: y,
      head: [['Actual \\ Predicted', ...labels]],
      body: matrix.map((row, i) => [labels[i], ...row.map(String)])
    })
  }

  return doc
}

/** Download the evaluation report as evaluation-{model_id}.pdf. */
export function exportEvaluationPDF(evaluation: ModelEvaluationResponse): void {
  const doc = buildEvaluationPDFDoc(evaluation)
  doc.save(`evaluation-${evaluation.model_id}.pdf`)
}
