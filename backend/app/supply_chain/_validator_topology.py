from collections import defaultdict, deque
from collections.abc import Iterable

from app.supply_chain.schemas import GraphDraft, GraphEdgeDraft, GraphNodeDraft

_LAYER_ORDER = {"upstream": 0, "core": 1, "downstream": 2}


def deduplicate_edges(
    edges: list[GraphEdgeDraft],
) -> tuple[list[GraphEdgeDraft], list[GraphEdgeDraft]]:
    retained: list[GraphEdgeDraft] = []
    discarded: list[GraphEdgeDraft] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in sorted(edges, key=_edge_rank):
        identity = (
            edge.source_node_key,
            edge.target_node_key,
            edge.relationship_type,
        )
        target = discarded if identity in seen else retained
        target.append(edge)
        seen.add(identity)
    return retained, discarded


def remove_cycles(
    edges: list[GraphEdgeDraft],
) -> tuple[list[GraphEdgeDraft], list[GraphEdgeDraft]]:
    retained = list(edges)
    removed: list[GraphEdgeDraft] = []
    while cycle_edges := _cyclic_edges(retained):
        loser = min(cycle_edges, key=_edge_quality)
        retained.remove(loser)
        removed.append(loser)
    return retained, removed


def select_public_topology(
    *,
    draft: GraphDraft,
    edges: list[GraphEdgeDraft],
    max_nodes: int,
) -> tuple[list[GraphNodeDraft], list[GraphEdgeDraft], list[str]]:
    reasons: list[str] = []
    node_map = {node.node_key: node for node in draft.nodes}
    component = _component(draft.focus_node_key, edges)
    if len(component) <= 1:
        reasons.append("FOCUS_DISCONNECTED")
    if component != set(node_map):
        reasons.append("ORPHAN_NODES_PRUNED")
    node_map = {key: node_map[key] for key in component if key in node_map}
    directed = _adjacency(edges, directed=True)
    upstream_path = _best_layer_path(
        nodes=node_map.values(),
        layer="upstream",
        start_at_layer=True,
        focus=draft.focus_node_key,
        adjacency=directed,
    )
    downstream_path = _best_layer_path(
        nodes=node_map.values(),
        layer="downstream",
        start_at_layer=False,
        focus=draft.focus_node_key,
        adjacency=directed,
    )
    if upstream_path is None:
        reasons.append("UPSTREAM_PATH_MISSING")
    if downstream_path is None:
        reasons.append("DOWNSTREAM_PATH_MISSING")
    required = {draft.focus_node_key}
    required.update(upstream_path or ())
    required.update(downstream_path or ())
    if len(required) > max_nodes:
        reasons.append("NODE_BUDGET_UNSATISFIED")
        required = {draft.focus_node_key}
    selected = set(required)
    undirected = _adjacency(edges, directed=False)
    ranked_nodes = sorted(
        node_map.values(),
        key=lambda node: _node_rank(node, edges, draft.focus_node_key),
    )
    for node in ranked_nodes:
        path = _shortest_path(draft.focus_node_key, node.node_key, undirected)
        if path is not None and len(selected | set(path)) <= max_nodes:
            selected.update(path)
    selected_edges = [
        edge
        for edge in edges
        if {edge.source_node_key, edge.target_node_key} <= selected
    ]
    nodes = sorted(
        (node_map[key] for key in selected if key in node_map),
        key=lambda node: (_LAYER_ORDER[node.layer], node.rank, node.node_key),
    )
    return nodes, selected_edges, reasons


def _cyclic_edges(edges: list[GraphEdgeDraft]) -> list[GraphEdgeDraft]:
    adjacency = _adjacency(edges, directed=True)
    return [
        edge
        for edge in edges
        if _path_exists(edge.target_node_key, edge.source_node_key, adjacency)
    ]


def _path_exists(
    start: str,
    target: str,
    adjacency: dict[str, set[str]],
) -> bool:
    queue = deque([start])
    visited = {start}
    while queue:
        node = queue.popleft()
        if node == target:
            return True
        for neighbor in adjacency.get(node, set()) - visited:
            visited.add(neighbor)
            queue.append(neighbor)
    return False


def _best_layer_path(
    *,
    nodes: Iterable[GraphNodeDraft],
    layer: str,
    start_at_layer: bool,
    focus: str,
    adjacency: dict[str, set[str]],
) -> list[str] | None:
    paths = []
    for node in nodes:
        if node.layer != layer:
            continue
        start, target = (
            (node.node_key, focus) if start_at_layer else (focus, node.node_key)
        )
        path = _shortest_path(start, target, adjacency)
        if path is not None:
            paths.append(path)
    return min(paths, key=lambda path: (len(path), path)) if paths else None


def _shortest_path(
    start: str,
    target: str,
    adjacency: dict[str, set[str]],
) -> list[str] | None:
    queue = deque([(start, [start])])
    visited = {start}
    while queue:
        node, path = queue.popleft()
        if node == target:
            return path
        for neighbor in sorted(adjacency.get(node, set())):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, [*path, neighbor]))
    return None


def _component(focus: str, edges: list[GraphEdgeDraft]) -> set[str]:
    adjacency = _adjacency(edges, directed=False)
    visited = {focus}
    queue = deque([focus])
    while queue:
        node = queue.popleft()
        for neighbor in adjacency.get(node, set()) - visited:
            visited.add(neighbor)
            queue.append(neighbor)
    return visited


def _adjacency(
    edges: list[GraphEdgeDraft],
    *,
    directed: bool,
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        result[edge.source_node_key].add(edge.target_node_key)
        if not directed:
            result[edge.target_node_key].add(edge.source_node_key)
    return result


def _node_rank(
    node: GraphNodeDraft,
    edges: list[GraphEdgeDraft],
    focus: str,
) -> tuple[float, float, float, float, str]:
    verified = [
        edge
        for edge in edges
        if edge.evidence_status == "verified"
        and node.node_key in {edge.source_node_key, edge.target_node_key}
    ]
    evidence_quality = max((edge.confidence for edge in verified), default=0.0)
    return (
        -float(node.node_key == focus),
        -float(len(verified)),
        -evidence_quality,
        -node.importance,
        node.node_key,
    )


def _edge_rank(edge: GraphEdgeDraft) -> tuple[float, float, float, str]:
    return (
        -float(edge.evidence_status == "verified"),
        -edge.confidence,
        -edge.importance,
        edge.edge_key,
    )


def _edge_quality(edge: GraphEdgeDraft) -> tuple[float, float, float, str]:
    return (
        float(edge.evidence_status == "verified"),
        edge.confidence,
        edge.importance,
        edge.edge_key,
    )
