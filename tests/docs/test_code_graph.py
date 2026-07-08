from __future__ import annotations

import json

from docmancer.docs.domain.code_graph import (
    CodeGraph,
    CodeGraphEdge,
    CodeGraphNode,
    confidence_score_for,
    make_edge_id,
    make_file_node_id,
    make_symbol_node_id,
)


def test_make_file_node_id_normalizes_windows_separators():
    assert make_file_node_id("lib\\a.dart") == "file:lib/a.dart"


def test_make_symbol_node_id_includes_path_line_and_symbol():
    assert make_symbol_node_id("lib\\a.dart", "TicketService", 12) == "symbol:lib/a.dart:12:TicketService"
    assert make_symbol_node_id("lib/a.dart", "TicketService") == "symbol:lib/a.dart:0:TicketService"


def test_make_edge_id_is_stable_and_changes_when_identity_changes():
    first = make_edge_id("contains", "file:lib/a.dart", "symbol:lib/a.dart:1:A")
    second = make_edge_id("contains", "file:lib/a.dart", "symbol:lib/a.dart:1:A")
    changed_kind = make_edge_id("references", "file:lib/a.dart", "symbol:lib/a.dart:1:A")
    changed_target = make_edge_id("contains", "file:lib/a.dart", "symbol:lib/a.dart:2:B")

    assert first == second
    assert first.startswith("edge:")
    assert len(first) == len("edge:") + 16
    assert first != changed_kind
    assert first != changed_target


def test_code_graph_to_context_dict_is_json_serializable():
    file_node = CodeGraphNode(
        id=make_file_node_id("lib/a.dart"),
        kind="file",
        name="a.dart",
        path="lib/a.dart",
        language="dart",
    )
    symbol_node = CodeGraphNode(
        id=make_symbol_node_id("lib/a.dart", "TicketService", 3),
        kind="symbol",
        name="TicketService",
        path="lib/a.dart",
        language="dart",
        line_start=3,
        line_end=5,
    )
    edge = CodeGraphEdge(
        id=make_edge_id("contains", file_node.id, symbol_node.id, symbol="TicketService", line_start=3),
        kind="contains",
        from_node_id=file_node.id,
        to_node_id=symbol_node.id,
        from_path="lib/a.dart",
        to_path="lib/a.dart",
        symbol="TicketService",
        line_start=3,
        confidence="exact",
        confidence_score=confidence_score_for("exact"),
        evidence="class TicketService",
    )
    graph = CodeGraph(
        nodes=[file_node, symbol_node],
        edges=[edge],
        diagnostics={"node_count": 2, "edge_count": 1},
    )

    payload = graph.to_context_dict()

    assert payload["nodes"][0]["id"] == "file:lib/a.dart"
    assert payload["edges"][0]["confidence"] == "exact"
    assert payload["diagnostics"] == {"node_count": 2, "edge_count": 1}
    json.dumps(payload)


def test_code_graph_lookup_helpers_group_by_id_and_source():
    file_node = CodeGraphNode(id="file:lib/a.dart", kind="file", name="a.dart", path="lib/a.dart")
    edge = CodeGraphEdge(id="edge:abc", kind="unresolved_reference", from_node_id=file_node.id, symbol="MissingApi")
    graph = CodeGraph(nodes=[file_node], edges=[edge])

    assert graph.node_by_id() == {file_node.id: file_node}
    assert graph.edges_by_from() == {file_node.id: [edge]}


def test_confidence_score_for_known_and_unknown_values():
    assert confidence_score_for("exact") == 1.0
    assert confidence_score_for("parser") == 0.9
    assert confidence_score_for("regex") == 0.7
    assert confidence_score_for("heuristic") == 0.45
    assert confidence_score_for("unresolved") == 0.1
    assert confidence_score_for("future") == 0.45


def test_mutable_metadata_defaults_are_not_shared():
    first_node = CodeGraphNode(id="file:a.py", kind="file", name="a.py", path="a.py")
    second_node = CodeGraphNode(id="file:b.py", kind="file", name="b.py", path="b.py")
    first_edge = CodeGraphEdge(id="edge:a", kind="references", from_node_id="file:a.py")
    second_edge = CodeGraphEdge(id="edge:b", kind="references", from_node_id="file:b.py")
    first_graph = CodeGraph(nodes=[], edges=[])
    second_graph = CodeGraph(nodes=[], edges=[])

    first_node.metadata["changed"] = True
    first_edge.metadata["changed"] = True
    first_graph.diagnostics["changed"] = True

    assert second_node.metadata == {}
    assert second_edge.metadata == {}
    assert second_graph.diagnostics == {}
