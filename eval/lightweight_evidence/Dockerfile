# Ubuntu matches the already pinned CPU runtime's glibc ABI. The workflow records
# the resolved image ID/digests; model and product revisions are recorded separately.
FROM ubuntu:24.04
ENV UV_PROJECT_ENVIRONMENT=/opt/venv TIKTOKEN_CACHE_DIR=/opt/tokenizer-cache \
    PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/bootstrap \
 && /opt/bootstrap/bin/pip install --no-cache-dir uv==0.9.25
WORKDIR /repo
COPY . .
RUN /opt/bootstrap/bin/uv sync --frozen --no-dev --no-install-project \
 && /opt/bootstrap/bin/uv build --wheel --out-dir /wheels \
 && /opt/bootstrap/bin/uv pip install --python /opt/venv/bin/python --no-deps /wheels/*.whl \
 && /opt/venv/bin/python -c 'import tiktoken; tiktoken.get_encoding("o200k_base")' \
 && /opt/venv/bin/python -m docmancer.docs.application.section_model /model
ENTRYPOINT ["/opt/venv/bin/python", "-I", "/repo/eval/lightweight_evidence/launch.py"]
