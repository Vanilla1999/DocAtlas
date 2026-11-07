"""Make an explicitly disclosed delivery-only variant of the frozen harness.

Only two public server configuration values change. No production module,
retrieval, selection, source validation, oracle, question or gold is mocked.
This measures public stdio output, not a running OpenCode/GPT conversation.
"""
import hashlib
import json
import sys
from pathlib import Path
source=Path(sys.argv[1]);target=Path(sys.argv[2])
body=source.read_bytes()
assert hashlib.sha256(body).hexdigest()=='90177e2222edb98240f447442b7115843108b7e9a244d74249a3f6025a73b56f'
old=b"DOCATLAS_MCP_MODEL_VIEW='1',DOCATLAS_SECTION_WIRE_FORMAT='adaptive-v2'"
new=b"DOCATLAS_MCP_MODEL_VIEW='off',DOCATLAS_SECTION_WIRE_FORMAT='v1'"
assert body.count(old)==1
updated=body.replace(old,new)
target.write_bytes(updated)
print(json.dumps({'profile':'stock-text-v1','original_harness_sha256':hashlib.sha256(body).hexdigest(),
 'delivery_harness_sha256':hashlib.sha256(updated).hexdigest(),
 'changed_configuration':{'DOCATLAS_MCP_MODEL_VIEW':'off','DOCATLAS_SECTION_WIRE_FORMAT':'v1'},
 'paid_model_calls':0,'actual_opencode_client_tested':False}))
