"""Respectively binds two ordered source lists; no variable names in grammar."""
import pytest
from tests.docs.test_admission_relation_witnesses import qualify
from tests.docs._reference_binding_fixtures import capture_reference_case, visible
from tests.docs.test_admission_meaning import demand

EN = 'Which variables set routing for channel-a, channel-b and all channels?'
RU = 'Какие переменные задают routing для channel-a, channel-b и all channels?'
BODY = '`ROUTE_X`, `ROUTE_Y`, `ROUTE_ANY` set the routing to be used for `channel-a`, `channel-b`, or all channels respectively.'


def test_native_assignment_reaches_the_final_packet(tmp_path):
    cap = capture_reference_case(tmp_path, {'Guide.md': '# Routing\n\n'+BODY}, RU)
    assert 'ROUTE_X' in visible(cap) and 'ROUTE_Y' in visible(cap) and 'respectively' in visible(cap)

