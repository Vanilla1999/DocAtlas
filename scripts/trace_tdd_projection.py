#!/usr/bin/env python3
"""Offline in-process first-loss diagnosis; not a stdio or model-quality test.

The real public handler is invoked unchanged. The tracer observes executed
continue statements in the existing projector; it does not alter decisions.
Run the harness outside the indexed checkout. Full inputs are private CI
artifacts from a disposable public-repository fixture, never MCP payloads.
"""
from __future__ import annotations
import argparse
import ast
import copy
import dataclasses
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch


def encode(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unserializable diagnostic type: {type(value).__name__}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', default='N26')
    args = parser.parse_args()
    repo = args.repo.resolve()
    cases = json.loads((repo / 'eval/tdd_questions30/cases.json').read_text())
    case = next(row for row in cases if row['id'] == args.case)
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    report = {'commit': commit, 'boundary': 'in_process_public_handler', 'case': case, 'lanes': []}
    with tempfile.TemporaryDirectory(prefix='docatlas-first-loss-') as temporary:
        root = Path(temporary)
        home = root / 'home'; home.mkdir()
        # Isolate state before any DocAtlas imports; never inherit model keys.
        allowed = {'PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT', 'WINDIR', 'TMPDIR', 'TEMP', 'TMP'}
        saved_env = {key: value for key, value in os.environ.items() if key in allowed}
        os.environ.clear(); os.environ.update(saved_env)
        os.environ.update(HOME=str(home), USERPROFILE=str(home), DOCATLAS_HOME=str(home/'state'),
                          DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0', NO_PROXY='*')
        os.chdir(home)
        import docmancer
        if Path(docmancer.__file__).resolve() != repo/'docmancer/__init__.py':
            raise ValueError('Wrong editable source installation')
        from docmancer.docs.application import _docs_context_projection_core as core
        from docmancer.docs.application import docs_context_projection as facade
        from docmancer.docs.interfaces.mcp import context_tools
        from docmancer.mcp.docs_server import call_docs_tool_payload
        from docmancer.core.config_resolution import resolve_config
        from docmancer.docs.service import LibraryDocsService
        function = core.project_docs_context
        filename = inspect.getsourcefile(function)
        text = Path(filename).read_text()
        report['projector_blob_sha256'] = hashlib.sha256(text.encode()).hexdigest()
        line_text = text.splitlines()
        continue_lines = {node.lineno for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Continue)}
        # A separate clean index per lane, matching the earlier stdio harness.
        for lane in ('direct', 'assisted'):
            project = root / lane
            subprocess.run(['git', 'clone', '--no-hardlinks', '--quiet', '--', str(repo), str(project)], check=True, timeout=90)
            resolved = resolve_config()
            service = LibraryDocsService(config=resolved.config, config_source=resolved.source, config_path=resolved.path)
            prepared = call_docs_tool_payload('prepare_docs', {'action': 'sync_project_docs', 'project_path': str(project), 'with_vectors': False}, service)
            if prepared.get('status') != 'success':
                raise RuntimeError(f'Preparation failed: {prepared}')
            entry = {'lane': lane, 'core_attempts': [], 'events': [], 'events_omitted': 0}
            report['lanes'].append(entry)
            original_facade = context_tools.project_docs_context
            original_core = facade._core.project_docs_context
            def observe_core(**kwargs):
                attempt = {'input': copy.deepcopy(kwargs['retrieval'])}
                entry['core_attempts'].append(attempt)
                result = original_core(**kwargs)
                attempt['output'] = copy.deepcopy(result[0])
                attempt['diagnostics'] = copy.deepcopy(kwargs['retrieval'].get('retrieval_diagnostics'))
                return result
            def observe_facade(**kwargs):
                entry['projection_input'] = copy.deepcopy(kwargs['retrieval'])
                result = original_facade(**kwargs)
                entry['projection_output'] = copy.deepcopy(result[0])
                return result
            def trace(frame, event, arg):
                if frame.f_code is not function.__code__:
                    return None
                if event == 'line' and frame.f_lineno in continue_lines:
                    if len(entry['events']) >= 512:
                        entry['events_omitted'] += 1
                    else:
                        local = frame.f_locals
                        row = {'line': frame.f_lineno, 'guard': line_text[max(0, frame.f_lineno-4):frame.f_lineno],
                               'attempt': len(entry['core_attempts'])}
                        for key in ('candidate_id', 'existing_index', 'eligible_query_ids', 'qualified_ids', 'component_ids', 'new_components', 'selected_public_ids', 'selected_canonical_ids'):
                            if key in local:
                                row[key] = copy.deepcopy(local[key])
                        for key in ('original', 'variant', 'normalized'):
                            value = local.get(key)
                            if isinstance(value, dict):
                                row[key] = {k: copy.deepcopy(value[k]) for k in ('path', 'path_or_url', 'heading_path', 'section', 'line_start', 'line_end', 'snippet', 'content', 'retrieval_query_matches') if k in value}
                        entry['events'].append(row)
                return trace
            arguments = {'question': case['question'], 'project_path': str(project), 'scope': case['scope']}
            if lane == 'assisted':
                arguments['lookup_queries'] = case['lookup_queries']
            previous_trace = sys.gettrace()
            try:
                with patch.object(context_tools, 'project_docs_context', observe_facade), patch.object(facade._core, 'project_docs_context', observe_core):
                    sys.settrace(trace)
                    entry['payload'] = call_docs_tool_payload('get_docs_context', arguments, service)
            finally:
                sys.settrace(previous_trace)
            repeated = call_docs_tool_payload('get_docs_context', arguments, service)
            def visible(payload):
                return (payload.get('status'), payload.get('kind'),
                        [(s.get('path_or_url'), s.get('snippet')) for s in payload.get('sources', [])])
            entry['uninstrumented_visible_equal'] = visible(repeated) == visible(entry['payload'])
            if not entry['uninstrumented_visible_equal']:
                raise AssertionError('Instrumented and uninstrumented visible results differ')
            print(lane, entry['payload'].get('kind'), len(entry['events']), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, default=encode, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
