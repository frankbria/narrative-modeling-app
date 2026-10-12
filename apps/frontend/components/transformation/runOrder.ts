/**
 * The order a pipeline's steps run in (#862).
 *
 * One rule for both views: the arrows drawn on the canvas, when there are any, and the
 * order the steps are listed in when there are none. Preview and Apply used to send the
 * listed order whatever was drawn, so a user who wired C → A → B got A, B, C applied.
 * The engine runs one step after another, so the arrows have to make a single chain
 * through every step; anything else is refused with the reason, never guessed at.
 */

export interface OrderNode {
  id: string;
  data: { label: string };
}

export interface OrderEdge {
  source: string;
  target: string;
}

export class PipelineOrderError extends Error {
  constructor(reason: string) {
    super(
      `The steps on the canvas are not one chain: ${reason}. ` +
        'Connect them in the order they should run, or arrange them in the Chain view.',
    );
    this.name = 'PipelineOrderError';
  }
}

/** The arrows between steps that are still there; a deleted step can leave one behind. */
function drawn(nodes: OrderNode[], edges: OrderEdge[]): OrderEdge[] {
  const present = new Set(nodes.map((node) => node.id));
  return edges.filter((edge) => present.has(edge.source) && present.has(edge.target));
}

/** The ids that appear more than once. */
function repeated(ids: string[]): Set<string> {
  const seen = new Set<string>();
  const again = new Set<string>();
  for (const id of ids) (seen.has(id) ? again : seen).add(id);
  return again;
}

/** A step with two arrows out, or two in: the engine has one frame to pass along. */
function forkOrMerge(nodes: OrderNode[], edges: OrderEdge[]): string | null {
  const forks = repeated(edges.map((edge) => edge.source));
  const merges = repeated(edges.map((edge) => edge.target));
  const fork = nodes.find((node) => forks.has(node.id));
  if (fork) return `${fork.data.label} leads to more than one step`;
  const merge = nodes.find((node) => merges.has(node.id));
  return merge ? `more than one step leads to ${merge.data.label}` : null;
}

/** Follow the arrows from `head` to the end of its chain. */
function follow(head: OrderNode, next: Map<string, OrderNode | undefined>): OrderNode[] {
  const chain: OrderNode[] = [];
  for (let node: OrderNode | undefined = head; node; node = next.get(node.id)) chain.push(node);
  return chain;
}

function chained(nodes: OrderNode[], edges: OrderEdge[]): OrderNode[] {
  const fork = forkOrMerge(nodes, edges);
  if (fork) throw new PipelineOrderError(fork);
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const next = new Map(edges.map((edge) => [edge.source, byId.get(edge.target)]));
  const targets = new Set(edges.map((edge) => edge.target));
  // With no fork and no merge, every step is on a chain that starts at a step nothing
  // leads to, or on a loop, which has no such start and so is never reached.
  const chains = nodes.filter((node) => !targets.has(node.id)).map((head) => follow(head, next));
  if (chains.flat().length < nodes.length) throw new PipelineOrderError('the arrows make a loop');
  if (chains.length > 1) throw new PipelineOrderError(`${chains[1][0].data.label} is not connected to the rest`);
  return chains[0];
}

/**
 * The steps in the order they run. The nodes returned are the ones passed in.
 *
 * @throws PipelineOrderError when arrows are drawn and do not make one chain through
 *   every step: a fork, a merge, a loop, or a step left unconnected.
 */
export function runOrder(nodes: OrderNode[], edges: OrderEdge[]): OrderNode[] {
  const arrows = drawn(nodes, edges);
  return arrows.length === 0 ? nodes : chained(nodes, arrows);
}

export interface OrderPlan {
  nodes: OrderNode[];
  problem: string | null;
}

/** `runOrder` for rendering: the listed order and the reason when there is no run order. */
export function planOrder(nodes: OrderNode[], edges: OrderEdge[]): OrderPlan {
  try {
    return { nodes: runOrder(nodes, edges), problem: null };
  } catch (error) {
    return { nodes, problem: (error as Error).message };
  }
}
