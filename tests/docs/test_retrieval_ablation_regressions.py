"""Counter/accounting guards and a real native-product paired repeat."""
import json
from pathlib import Path
import subprocess

import pytest

from experiments.retrieval_ablation.regressions import junit_cases, repeat_pair
from experiments.retrieval_ablation.run import ROOT


def test_junit_does_not_hide_changed_failure_reasons(tmp_path):
    path = tmp_path / 'results.xml'
    path.write_text('<testsuite><testcase classname="t" name="first"><failure message="read_next empty"/>'
                    '</testcase><testcase classname="t" name="second"/></testsuite>')
    cases = junit_cases(path)
    assert cases['t::first'] == {'status': 'failure', 'message': 'read_next empty'}
    assert cases['t::second']['status'] == 'passed'


def test_duplicate_junit_identity_is_an_error(tmp_path):
    path = tmp_path / 'results.xml'
    path.write_text('<testsuite><testcase classname="t" name="same"/><testcase classname="t" name="same"/></testsuite>')
    with pytest.raises(ValueError, match='duplicate'):
        junit_cases(path)


def test_real_repeat_has_same_checkout_and_fixture_path_and_no_hidden_waivers(tmp_path):
    targets = ('tests/test_sqlite_ranking_truth.py::test_equal_feature_candidates_use_stable_identity_not_insertion_order',)
    result = repeat_pair(ROOT, base='55637eb4d29a0d06c01714ee647a5b486a5be725', head='HEAD',
                         output=tmp_path / 'paired', repeats=1, full_collection=False, targets=targets)
    records = result['records']
    assert result['planned'] == len(records) == 2
    assert len({r['cwd'] for r in records}) == len({r['basetemp'] for r in records}) == 1
    assert all(r['execution_status'] == 'EXECUTED' for r in records)
    assert all(r['counts'] == {'passed': 1} and r['returncode'] == 0 for r in records)
    assert len(result['comparisons'][0]['common_ids']) == 1
    assert result['comparisons'][0]['differences'] == {}
    assert not Path(records[0]['cwd']).exists()


def test_timeout_kills_descendants_holding_the_output_pipe(tmp_path):
    import os
    import sys
    import time
    from experiments.retrieval_ablation.regressions import run_command
    started = time.monotonic()
    code, log = run_command([sys.executable, '-c',
        "import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); print('spawned', flush=True)"],
        cwd=tmp_path, env=dict(os.environ), timeout=1)
    assert code == 124
    assert 'spawned' in log
    assert time.monotonic() - started < 5


def test_timeout_also_bounds_capture_when_a_child_detaches(tmp_path):
    import os
    import signal
    import sys
    import time
    from experiments.retrieval_ablation.regressions import run_command
    pid_file = tmp_path / 'owned-child.pid'
    child = "import time; time.sleep(12)"
    script = ("import subprocess,sys,pathlib; p=subprocess.Popen([sys.executable,'-c',"
              + repr(child) + "],start_new_session=True); pathlib.Path("
              + repr(str(pid_file)) + ").write_text(str(p.pid)); print('detached',flush=True)")
    started = time.monotonic()
    try:
        code, log = run_command([sys.executable, '-c', script], cwd=tmp_path,
                                env=dict(os.environ), timeout=1)
        assert code == 124
        assert 'detached' in log
        assert time.monotonic() - started < 7
    finally:
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
