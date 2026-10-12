import { MarkerType, type Edge } from '@xyflow/react';
import type { PipelineStep } from '@/lib/services/pipelineApi';
import type { TransformationFlowNode, TransformationNodeData } from './TransformationNode';

function label(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/** A recipe's steps as a top-to-bottom chain of pipeline nodes, each linked to the next. */
export function recipeFlow(steps: PipelineStep[]): { nodes: TransformationFlowNode[]; edges: Edge[] } {
  const nodes: TransformationFlowNode[] = steps.map((step, index) => ({
    id: `node-${index + 1}`,
    type: 'transformation',
    position: { x: 250, y: 100 + index * 150 },
    data: {
      type: step.type,
      label: label(step.type),
      parameters: step.parameters as TransformationNodeData['parameters'],
    },
  }));
  const edges: Edge[] = nodes.slice(0, -1).map((node, index) => ({
    id: `edge-${index}`,
    source: node.id,
    target: nodes[index + 1].id,
    markerEnd: { type: MarkerType.ArrowClosed },
  }));
  return { nodes, edges };
}
