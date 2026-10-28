FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive UV_PROJECT_ENVIRONMENT=/opt/venv \
    TIKTOKEN_CACHE_DIR=/opt/tokenizer-cache PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv python3-pip ca-certificates libgomp1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
COPY . .
RUN python3 -m pip install --break-system-packages --no-cache-dir uv==0.9.25 \
 && uv sync --frozen --no-dev --no-install-project \
 && uv build --wheel --out-dir /wheels \
 && uv pip install --python /opt/venv/bin/python --no-deps /wheels/*.whl \
 && /opt/venv/bin/python -c 'import tiktoken; tiktoken.get_encoding("o200k_base")' \
 && /opt/venv/bin/python -m docmancer.docs.application.section_model /model
# Serving binary and tiny weights are mounted read-only only for tiny arms.
ENTRYPOINT ["/opt/venv/bin/python", "-I", "/repo/eval/lowmem_selection/entry.py"]
