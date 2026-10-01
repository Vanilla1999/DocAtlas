"""Explicit measurement revision; the frozen cases/protocol remain unchanged."""
from copy import deepcopy


def revised_case(case: dict) -> dict:
    result = deepcopy(case)
    if result['id'] == 'uv-06':
        # The question asks for default isolation and the missing-dependency
        # escape hatch, not a particular biopython installation example.
        part = result['required_claims'][0]['witness_sets'][0]['parts'][0]
        prefix, marker, example = part['text'].partition('\n\n```shell\n')
        if not marker or example != 'uv pip install wheel && uv pip install --no-build-isolation biopython==1.77':
            raise ValueError('uv-06 frozen annotation changed; re-review correction')
        part['text'] = prefix
        part['line_end'] = part['line_start'] + prefix.count('\n')
    return result
