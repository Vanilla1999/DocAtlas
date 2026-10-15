FROM python:3.12-slim
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    TIKTOKEN_CACHE_DIR=/opt/tokenizer-cache \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false
WORKDIR /repo
COPY . .
RUN pip install --no-cache-dir uv==0.9.25 \
 && uv sync --frozen --no-dev --no-install-project \
 && uv build --wheel --out-dir /wheels \
 && uv pip install --python /opt/venv/bin/python --no-deps /wheels/*.whl \
 && /opt/venv/bin/python -c 'import tiktoken; tiktoken.get_encoding("o200k_base")' \
 && /opt/venv/bin/python -m docmancer.docs.application.section_model /model
ENTRYPOINT ["/opt/venv/bin/python", "-I", "/repo/eval/minilm_sections_integration.py"]
