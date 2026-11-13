"""Export only the eight authorized sessions; replay checks offline by default."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    sessions = load(HERE / 'sessions.json')
    roster = {r['id']: r for r in load(HERE / 'manifest.json')['roster']}
    wrappers = {r['trial_id']: r['prompt'] for r in load(HERE / 'launch-handoff.json')}
    assert set(sessions) == set(roster) == set(wrappers) and len(set(sessions.values())) == 8
    rows = []
    for trial, sid in sessions.items():
        path = HERE / 'live/exports' / (trial + '.json')
        if args.export and not path.exists():
            raw = subprocess.check_output(['opencode', 'session', 'export', sid])
            data = json.loads(raw)
            assert data['info']['id'] == sid
            # Exported research transcripts only. No credentials/config retrieval.
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        data = load(path)
        assert data['info']['id'] == sid and data['info']['outcome'] == 'succeeded'
        messages = data['messages']
        users = [m for m in messages if m['type'] == 'user']
        assert len(users) == 1 and users[0]['text'] == 'You are a subagent spawned by another session.\n' + wrappers[trial]
        assistants = [m for m in messages if m['type'] == 'assistant']
        assert len(assistants) == 2
        tools = [(m, c) for m in assistants for c in m['content'] if c['type'] == 'tool']
        assert len(tools) == 1
        read_message, tool = tools[0]
        state = tool['state']
        expected_path = '/tmp/opencode/step16-generator-inputs/' + trial + '.txt'
        assert tool['name'] == 'read' and state['input'] == {'path': expected_path}
        assert state['status'] == 'completed' and state['metadata']['truncated'] is False
        text = '\n'.join(c['text'] for c in state['content'] if c['type'] == 'text')
        numbered = text.splitlines()[1:]
        decoded = []
        for index, line in enumerate(numbered, 1):
            match = re.fullmatch(r'(\d+): (.*)', line)
            assert match and int(match[1]) == index
            decoded.append(match[2])
        prepared = (HERE / roster[trial]['input']).read_text()
        assert decoded == prepared.splitlines(), trial
        assert hashlib.sha256(prepared.encode()).hexdigest() == roster[trial]['sha256']
        final = assistants[-1]
        assert final['finish'] == 'stop' and final['time']['created'] >= read_message['time']['completed']
        answer = '\n'.join(c['text'] for c in final['content'] if c['type'] == 'text')
        assert answer
        model = data['info']['model']
        assert model['id'] == 'gpt-6.1-terra' and model['providerID'] == 'openai'
        assert all(m['model'] == model for m in assistants)
        totals = {k: sum(m['tokens'][k] for m in assistants) for k in ['input', 'output', 'reasoning']}
        totals['cache'] = {k: sum(m['tokens']['cache'][k] for m in assistants) for k in ['read', 'write']}
        assert totals == data['info']['tokens']
        (HERE / 'live/answers').mkdir(exist_ok=True)
        (HERE / 'live/answers' / (trial + '.md')).write_text(answer + '\n')
        rows.append({'id': trial, 'case_id': roster[trial]['case_id'], 'arm': roster[trial]['arm'],
                     'session_id': sid, 'model': model, 'answer': answer,
                     'export_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'input_sha256': roster[trial]['sha256'],
                     'delivery': 'exact_full_numbered_read_result_in_harness_transcript_before_answer',
                     'raw_provider_body': None, 'read_message_id': read_message['id'],
                     'answer_message_id': final['id'], 'read_tool': tool,
                     'usage_provenance': 'opencode session export; assistant.tokens sum equals info.tokens',
                     'harness_reported_provider_usage': totals,
                     'assistant_metadata': [{k: m[k] for k in ['id','model','native','tokens','time','finish','cost']} for m in assistants]})
    save(HERE / 'live/results.json', rows)
    save(HERE / 'live/delivery-checks.json', {'sessions': 8, 'exact_read_results': 8,
         'one_read_then_answer': 8, 'assistant_messages': 16, 'usage_reconciled': 8,
         'same_reported_model_settings': len({json.dumps(r['model'],sort_keys=True) for r in rows}) == 1,
         'raw_provider_capture': False, 'new_generations_by_collector': 0})
    print('PASS: 8 exact read results, 8 final answers, 16 assistant messages, usage reconciled.')


if __name__ == '__main__':
    main()
