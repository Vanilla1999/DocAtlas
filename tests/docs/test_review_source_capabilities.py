"""Publication must not silently mutate an already registered source capability."""
import hashlib
from dataclasses import replace

import pytest

from docmancer.docs.application.source_continuation import SourceContinuationReader, SourceReference


class Gateway:
    def __init__(self, raw):
        self.raw = raw
        self.reads = 0

    def authorize(self, reference):
        return None

    def read_snapshot(self, reference):
        self.reads += 1
        return self.raw


@pytest.fixture
def capability():
    raw = b'# Resource\nIntro\nthird\nfourth\nfifth\n'
    gateway = Gateway(raw)
    now = [0.0]
    reader = SourceContinuationReader(gateway, clock=lambda: now[0])
    ref = SourceReference('/repo', 'project:test', 'docs/resource.md',
        'sha256:' + hashlib.sha256(raw).hexdigest(), 'catalog:1',
        'source_of_truth', 'project', None, 2)
    return reader, ref, now, gateway


def test_legacy_republication_cannot_rebind_an_existing_bounded_range(capability):
    reader, ref, _, gateway = capability
    uri = reader.uri_prefix + 'a' * 24
    assert reader.issue_range(ref, line_start=4, line_end=4, uri=uri) == uri
    assert reader.issue(ref, uri=uri) is None
    out = reader.read(uri)
    assert (out['line_start'], out['line_end'], out['snippet']) == (4, 4, 'fourth')
    assert gateway.reads == 1


def test_legacy_republication_does_not_extend_original_expiry(capability):
    reader, ref, now, gateway = capability
    uri = reader.uri_prefix + 'b' * 24
    assert reader.issue(ref, uri=uri) == uri
    now[0] = reader.retention_seconds - 1
    assert reader.issue(ref, uri=uri) == uri
    now[0] = reader.retention_seconds + 1
    out = reader.read(uri)
    assert out['status'] == 'source_unavailable'
    assert gateway.reads == 0


def test_idempotent_legacy_publication_keeps_the_original_forward_read(capability):
    reader, ref, now, gateway = capability
    uri = reader.uri_prefix + 'c' * 24
    assert reader.issue(ref, uri=uri) == uri
    now[0] += 2
    assert reader.issue(ref, uri=uri) == uri
    assert gateway.reads == 0
    out = reader.read(uri)
    assert (out['line_start'], out['line_end']) == (3, 5)
    assert out['snippet'] == 'third\nfourth\nfifth'


def test_range_publication_cannot_rebind_an_existing_legacy_cursor(capability):
    reader, ref, _, _ = capability
    uri = reader.uri_prefix + 'd' * 24
    assert reader.issue(ref, uri=uri) == uri
    assert reader.issue_range(ref, line_start=4, line_end=4, uri=uri) is None
    assert reader.read(uri)['line_start'] == 3


def test_range_republication_does_not_extend_original_expiry(capability):
    reader, ref, now, gateway = capability
    uri = reader.uri_prefix + 'e' * 24
    assert reader.issue_range(ref, line_start=4, line_end=4, uri=uri) == uri
    now[0] = reader.retention_seconds - 1
    assert reader.issue_range(ref, line_start=4, line_end=4, uri=uri) == uri
    now[0] += 2
    assert reader.read(uri)['status'] == 'source_unavailable'
    assert gateway.reads == 0


def test_different_reference_cannot_replace_issued_legacy_cursor(capability):
    reader, ref, _, _ = capability
    uri = reader.uri_prefix + 'f' * 24
    assert reader.issue(ref, uri=uri) == uri
    assert reader.issue(replace(ref, line_end=3), uri=uri) is None
    assert reader.read(uri)['line_start'] == 3
