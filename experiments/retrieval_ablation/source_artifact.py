"""Original/canonical provenance for experimental HTML and native Markdown.

Converted evidence coordinates are canonical Markdown, never original HTML.
No URL fetch, ownership inference or product metadata promotion occurs here.
"""
from dataclasses import dataclass
import hashlib
import inspect
import json
from pathlib import Path


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SourceArtifact:
    original: bytes
    canonical: bytes
    source_format: str
    converter: str
    converter_sha256: str

    def provenance(self):
        return {'schema_version': 1, 'source_format': self.source_format,
                'original_sha256': _digest(self.original),
                'canonical_sha256': _digest(self.canonical),
                'converter': self.converter, 'converter_sha256': self.converter_sha256,
                'evidence_coordinate_space': 'canonical_utf8_markdown',
                'original_coordinate_mapping': 'NOT_PROVIDED'}

    def quote(self, start, end):
        text = self.canonical.decode('utf-8')
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise ValueError('invalid canonical span')
        return {'text': text[start:end], 'canonical_char_span': [start, end],
                'canonical_byte_span': [len(text[:start].encode()), len(text[:end].encode())],
                'provenance': self.provenance()}


def canonicalize(raw: bytes, *, source_format: str):
    text = raw.decode('utf-8')
    if source_format == 'markdown':
        return SourceArtifact(raw, raw, source_format, 'identity', _digest(b'identity-v1'))
    if source_format != 'html':
        raise ValueError('unsupported source format; no implicit Markdown conversion')
    from docmancer.connectors.fetchers.pipeline import extraction
    canonical = extraction.extract_content(text).encode('utf-8')
    if not canonical.strip():
        raise ValueError('HTML extraction produced no canonical evidence')
    code = Path(inspect.getfile(extraction)).read_bytes()
    return SourceArtifact(raw, canonical, source_format,
                          'production.extract_content', _digest(code))


def save_artifact(artifact, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    (output / 'original.bin').write_bytes(artifact.original)
    (output / 'canonical.md').write_bytes(artifact.canonical)
    (output / 'provenance.json').write_text(json.dumps(artifact.provenance(), indent=2))


def load_artifact(root):
    root = Path(root)
    names = ('original.bin', 'canonical.md', 'provenance.json')
    if any((root / name).is_symlink() for name in names):
        raise ValueError('artifact symlinks are not allowed')
    provenance = json.loads((root / 'provenance.json').read_text())
    artifact = SourceArtifact((root / 'original.bin').read_bytes(),
        (root / 'canonical.md').read_bytes(), provenance['source_format'],
        provenance['converter'], provenance['converter_sha256'])
    if artifact.provenance() != provenance:
        raise ValueError('original/canonical provenance mismatch')
    if artifact.source_format not in ('html', 'markdown'):
        raise ValueError('unsupported source provenance')
    if artifact.source_format == 'markdown' and artifact.original != artifact.canonical:
        raise ValueError('identity conversion changed Markdown bytes')
    if canonicalize(artifact.original, source_format=artifact.source_format) != artifact:
        raise ValueError('canonical conversion did not reproduce')
    return artifact


def bind_packet_provenance(result, artifacts):
    """Bind actual validated quotes to canonical artifacts, privately.

    Public DTOs are unchanged; these locators never claim original HTML spans.
    """
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    packet, snapshot = result['model_visible_packet'], result['packet_snapshot']
    if validate_model_visible_projection(packet, snapshot=snapshot, max_tokens=800):
        raise ValueError('invalid canonical packet')
    locators = {}
    for source in packet.get('sources', []):
        identity, path = source['evidence_id'], source['path_or_url']
        artifact = artifacts.get(path)
        if artifact is None:
            raise ValueError('missing source artifact')
        original = snapshot[identity]['source']
        if original['source_content_hash'] != _digest(artifact.canonical):
            raise ValueError('packet/artifact canonical hash mismatch')
        raw = artifact.canonical.decode('utf-8')
        start, end = original['char_start'], original['char_end']
        if not 0 <= start < end <= len(raw):
            raise ValueError('invalid source artifact window')
        snippet = source['snippet']
        window = raw[start:end]
        if not snippet or window.count(snippet) != 1:
            raise ValueError('quote is absent or ambiguous within verified window')
        offset = start + window.index(snippet)
        locators[identity] = {'canonical_path': path, **artifact.quote(offset, offset + len(snippet))}
    return locators
