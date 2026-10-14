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
  return { nodes, edges: chainEdges(nodes) };
}

/** One arrow from each step to the next: the canvas drawing of a listed order. */
export function chainEdges(nodes: { id: string }[]): Edge[] {
  return nodes.slice(0, -1).map((node, index) => ({
    id: `edge-${node.id}-${nodes[index + 1].id}`,
    source: node.id,
    target: nodes[index + 1].id,
    markerEnd: { type: MarkerType.ArrowClosed },
  }));
}

/** Why a recipe cannot be loaded, naming each step whose type the engine does not run
 * (#929): a recipe saved before #499 can hold one, and its preview then failed with a
 * message that named nothing. Null when every step runs, or when the types are unknown. */
export function unrunnableSteps(steps: PipelineStep[], types: { type: string }[] | null): string | null {
  if (!types?.length) return null;
  const runs = new Set(types.map((t) => t.type));
  const stale = steps.flatMap((step, index) => (runs.has(step.type) ? [] : [`step ${index + 1} (${label(step.type)})`]));
  if (!stale.length) return null;
  const one = stale.length === 1;
  return `This recipe cannot be loaded: ${stale.join(', ')} ${one ? 'is' : 'are'} no longer ${one ? 'a transformation' : 'transformations'} the pipeline runs. Remove ${one ? 'it' : 'them'} from the recipe and save it again.`;
}
