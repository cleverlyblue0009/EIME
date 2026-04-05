import dagre from "dagre";
import type { Edge, Node } from "reactflow";

type LayoutOptions = {
  direction?: "TB" | "LR";
  nodeWidth?: number;
  nodeHeight?: number;
  rankSep?: number;
  nodeSep?: number;
};

const defaultOptions: Required<LayoutOptions> = {
  direction: "TB",
  nodeWidth: 240,
  nodeHeight: 92,
  rankSep: 90,
  nodeSep: 60,
};

export function layoutGraph<T = any>(
  nodes: Array<Node<T>>,
  edges: Array<Edge>,
  options?: LayoutOptions
) {
  const settings = { ...defaultOptions, ...options };
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: settings.direction,
    ranksep: settings.rankSep,
    nodesep: settings.nodeSep,
  });

  nodes.forEach((node) => {
    const width =
      typeof node.width === "number" ? node.width : settings.nodeWidth;
    const height =
      typeof node.height === "number" ? node.height : settings.nodeHeight;
    graph.setNode(node.id, { width, height });
  });

  edges.forEach((edge) => {
    graph.setEdge(edge.source, edge.target);
  });

  dagre.layout(graph);

  return nodes.map((node) => {
    const layoutNode = graph.node(node.id);
    if (!layoutNode) {
      return node;
    }
    const width =
      typeof node.width === "number" ? node.width : settings.nodeWidth;
    const height =
      typeof node.height === "number" ? node.height : settings.nodeHeight;
    return {
      ...node,
      position: {
        x: layoutNode.x - width / 2,
        y: layoutNode.y - height / 2,
      },
    };
  });
}
