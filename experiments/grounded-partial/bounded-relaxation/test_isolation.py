"""Prevent a fourth, unregistered heading-ratio relaxation in every lane."""
import pytest
from test_relaxation import fixture, check


@pytest.mark.parametrize('mode', ['catalog','spelling','one_anchor','combined'])
def test_no_rescue_without_an_enabled_feature(mode):
    text='Tasks run.'
    f=fixture(mode,'# Execution Procedure Workflow Policy\n'+text,text,
              'tasks run execution procedure workflow policy unrelated',
              ['tasks','run','execution','procedure','workflow','policy','unrelated'],[])
    result,proof=check(f)
    assert not result.qualified and proof is None
