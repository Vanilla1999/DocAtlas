"""Unresolved Gate A obligations; intentional behavioral Reds, not acceptance."""
from tests.docs.test_gate_a_contract_candidate import candidate


def test_code_window_cannot_drop_following_applicability_restriction():
    question = 'storage retention behavior'
    prefix = ('Configure storage retention behavior with this command:\n\n'
              '```sh\nretention --current\n```\n')
    raw = prefix + '\nThis command must only be run against the test instance.\n'
    assert candidate.decide_structural_window(question, raw, 0, len(raw)).state == 'allowed'
    assert candidate.decide_structural_window(question, raw, 0, len(prefix)).state != 'allowed'


def test_legal_inventory_does_not_lose_all_feasible_context_to_solver_limit():
    # 15 candidates, two alternatives each: well below accepted inventory caps.
    # Every packet fits. No ranking replacement or best-so-far acceptance.
    order = tuple(f'candidate-{i:02}' for i in range(15))
    windows = [dict(source=f'{i:02}.md', candidate_id=order[i], start=0, end=end)
               for i in range(15) for end in (10, 20)]
    result = candidate.solve_packets(windows, candidate_order=order,
                                    packet_cost=lambda packet: 100)
    assert result.status == 'optimal_in_inventory'
    assert result.windows
