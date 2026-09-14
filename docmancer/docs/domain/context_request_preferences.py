"""Small request-shape preferences for compact context selection; never proof."""
from __future__ import annotations

import re
from typing import FrozenSet

_CODE_REQUEST_RE = re.compile(r"\b(?:code|example|snippet|runnable)\b", re.I)
_SIGNATURE_REQUEST_RE = re.compile(r"\b(?:signature|declaration)\b", re.I)
_FENCE_RE = re.compile(r"^\s*(```|~~~)", re.M)
_SIGNATURE_RE = re.compile(
    r"(?:`[^`\n]*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*\([^\n)]*\)"
    r"(?:\s*->\s*[^`\n]+)?`|\b(?:def|class)\s+[A-Za-z_]\w*\s*\()",
    re.I,
)
_DURATION_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ms|milliseconds?|s|sec(?:ond)?s?|minutes?|mins?)\b",
    re.I,
)
_EXCEPTION_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:Exception|Error|Timeout)\b")
_TIMEOUT_KINDS = ("connect", "pool", "read", "write")


def recognized_request_parts(question: str) -> FrozenSet[str]:
    """Return only narrowly recognized requested parts.

    Empty means the free-form request has no selection-completeness shortcut.
    The result is not a public completeness proof and must not drive ``checked``.
    """
    q = question.casefold()
    parts: set[str] = set()
    if _CODE_REQUEST_RE.search(question):
        parts.add("code_example")
    if _SIGNATURE_REQUEST_RE.search(question):
        parts.add("signature")
    if "timeout" in q and "default" in q:
        parts.add("default_timeout")
        if re.search(r"\b(?:how\s+long|duration|seconds?|minutes?|time)\b", q):
            parts.add("timeout_duration")
        if re.search(r"\b(?:which\s+exception|exception|error)\b", q):
            parts.add("timeout_exception")
    for kind in _TIMEOUT_KINDS:
        if re.search(rf"\b{kind}\b", q) and "timeout" in q:
            parts.add(f"timeout_kind:{kind}")
    # Common comparison wording where the same operation is contrasted across
    # two explicitly named input/origin contexts: "from JSON and from Python".
    origins = re.findall(r"\bfrom\s+([A-Za-z][A-Za-z0-9_.-]*)\b", question, re.I)
    if len({origin.casefold() for origin in origins}) >= 2 and re.search(
        r"\b(?:same\s+way|differ|difference|compare|versus|vs\.?|unlike)\b", q
    ):
        parts.add("origin_comparison")
        for origin in dict.fromkeys(origin.casefold() for origin in origins):
            parts.add(f"origin:{origin}")
    return frozenset(parts)


def visible_request_parts(question: str, text: str) -> FrozenSet[str]:
    """Return recognized parts literally supported by one visible candidate."""
    requested = recognized_request_parts(question)
    if not requested:
        return frozenset()
    body = text.casefold()
    visible: set[str] = set()
    if "code_example" in requested and _complete_fence(text):
        visible.add("code_example")
    if "signature" in requested and _SIGNATURE_RE.search(text):
        visible.add("signature")
    if "default_timeout" in requested and "timeout" in body and "default" in body:
        visible.add("default_timeout")
    if "timeout_duration" in requested and _DURATION_RE.search(text):
        visible.add("timeout_duration")
    if "timeout_exception" in requested and _EXCEPTION_RE.search(text):
        visible.add("timeout_exception")
    for kind in _TIMEOUT_KINDS:
        part = f"timeout_kind:{kind}"
        if part in requested and re.search(rf"\b{kind}\b", body) and "timeout" in body:
            visible.add(part)
    origins = [part.split(":", 1)[1] for part in requested if part.startswith("origin:")]
    for origin in origins:
        if re.search(rf"(?<![\w.-]){re.escape(origin)}(?![\w.-])", body):
            visible.add(f"origin:{origin}")
    if "origin_comparison" in requested:
        has_all_origins = all(f"origin:{origin}" in visible for origin in orif[œÊBˆ\×Ü™[][ÛˆH›ÛÛ
™KœÙX\˜Ú
ˆˆ—ŠÎ˜]Ú\™X\ß[›ZÙ_ÛÜÙ\ŸÝšXÝ\ŸØ[Y_Y™™\ŸY™™\™[˜Ù_XØÙ\Y™Z™XÝY›Ý
Wˆ‹ˆ›ÙKˆ
JBˆYˆ\×Ø[ÛÜšYÚ[œÈ[™\×Ü™[][ÛŽ‚ˆš\ÚX›K˜Y
›ÜšYÚ[—ØÛÛ\\š\ÛÛˆŠBˆ™]\›ˆœ›Þ™[œÙ]
š\ÚX›JB‚‚™Yˆ\™XÝÙ]šY[˜ÙWÜ™Y™\™[˜ÙJ]Y\Ý[ÛŽˆÝ‹^ˆÝŠHOˆ\VÚ[[[[N‚ˆˆˆ“Ü™\ˆ[YÚX›H]šY[˜ÙHžH™\]Y\ÝY\Ë\™XÝ™\ÜÈ[™ÛÛ\XÝ™\ÜË‚‚ˆHš[˜[[[Y[\ÈÛ›HH›Ý[™YYKXœ™XZÈ[[Û™ÈØ[™Y]\È][™XYBˆ\ÜÈ]]Üš^˜][Û‹Ü]X[YšXØ][Û‹ˆ]\È›ÝHÛØ˜[ÚÜ\ÝYš\œÝ[K‚ˆˆˆ‚ˆ™\]Y\ÝYH™XÛÙÛš^™YÜ™\]Y\ÝÜ\Ê]Y\Ý[ÛŠBˆš\ÚX›HHš\ÚX›WÜ™\]Y\ÝÜ\Ê]Y\Ý[Û‹^
BˆÛÙWÜ™\]Y\ÝYH˜ÛÙWÙ^[\Hˆ[ˆ™\]Y\ÝYˆÛÛ\]WØÛÙHHØÛÛ\]WÙ™[˜ÙJ^
BˆÚYÛ˜]\™WÜ™\]Y\ÝYHœÚYÛ˜]\™Hˆ[ˆ™\]Y\ÝYˆÚYÛ˜]\™WÝš\ÚX›HHœÚYÛ˜]\™Hˆ[ˆš\ÚX›Bˆ\™XÝHˆYˆÛÙWÜ™\]Y\ÝY‚ˆ\™XÝH[
ÛÛ\]WØÛÙJBˆ[YˆÚYÛ˜]\™WÜ™\]Y\ÝY‚ˆ\™XÝH[
ÚYÛ˜]\™WÝš\ÚX›JBˆ[ÙN‚ˆ\™XÝH[
›ÝÛÛ\]WØÛÙJBˆ]Y\Ý[Û—ÙXÚÈH[
Û›Ü›X[^™Y
^
HOHÛ›Ü›X[^™Y
]Y\Ý[ÛŠJBˆ™]\›ˆ[Šš\ÚX›JK\™XÝ\]Y\Ý[Û—ÙXÚË[[Š^™[˜ÛÙJ]‹NŠJB‚‚™Yˆ™XÛÙÛš^™YÜ™\]Y\ÝÜØ]\ÙšYY
]Y\Ý[ÛŽˆÝ‹^ˆÝŠHOˆ›ÛÛ‚ˆˆˆ”Ù[XÝ[Û‹[Û›HX\›K\ÝÜ›ÜˆH[Hš\ÚX›H
œ™XÛÙÛš^™Y
ˆ™\]Y\ÝÚ\Kˆˆˆ‚ˆ™\]Y\ÝYH™XÛÙÛš^™YÜ™\]Y\ÝÜ\Ê]Y\Ý[ÛŠBˆ™]\›ˆ›ÛÛ
™\]Y\ÝY
H[™™\]Y\ÝYHš\ÚX›WÜ™\]Y\ÝÜ\Ê]Y\Ý[Û‹^
B‚‚™YˆØÛÛ\]WÙ™[˜ÙJ^ˆÝŠHOˆ›ÛÛ‚ˆÜ[š[™ÈHÑ‘SÑWÔ‘KœÙX\˜Ú
^
BˆYˆÜ[š[™È\È›Û™N‚ˆ™]\›ˆ˜[ÙBˆX\šÙ\ˆHÜ[š[™Ë™Ü›Ý\
JBˆ™]\›ˆ›ÛÛ
™KœÙX\˜Ú
ˆ™ˆ——ÊžÜ™K™\ØØ\JX\šÙ\Š_WÊ‰‹^ÛÜ[š[™Ë™[™

N—K™K“Kˆ
JB‚‚™YˆÛ›Ü›X[^™Y
^ˆÝŠHOˆÝŽ‚ˆ™]\›ˆˆ‹š›Ú[Š™K™š[™[
ˆ–ØK^ŒNWË‹WJÈ‹^˜Ø\ÙY›Û

JJB