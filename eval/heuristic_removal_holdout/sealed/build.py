"""Independent hand-authored facts + literal byte pinning, no product imports or outputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = {
    "click": "corpus/click/docs/options.rst",
    "requests": "corpus/requests/docs/user/quickstart.rst",
    "pytest": "corpus/pytest/doc/en/how-to/skipping.rst",
    "tox": "corpus/tox/docs/config.rst",
}


def fact(statement, *alternatives):
    return {"statement": statement, "alternatives": alternatives}


# Statements and quotations authored independently from original pinned documents.
# No retrieval, selection, admission or assembly helper computes expectations.
ROWS = [
    ("click", "positive", "For Click 8.1.8, when no explicit type is supplied to a basic value option, how is its type chosen with versus without a default? Does the --n default=1 example establish that every option defaults to integer?", [
        fact("Type is inferred from supplied default; absent default implies STRING.", ("If no type is provided, the type of the default\nvalue is used.  If no default value is provided, the type is assumed to be\n:data:`STRING`.",)),
        fact("INT is the example's inferred type because its default is an integer, not the universal default.", ("In this case the option is of type :data:`INT` because the default value\nis an integer.",)),
    ], [], ["All basic value options default to integer."]),
    ("click", "positive", "In Click 8.1.8, how do I collect all repetitions of --message, rather than only the last, and what happens if a multiple=True default is a plain string rather than a list or tuple?", [
        fact("multiple collects all repeated values.", ("parameter being provided multiple times and have all the values recorded --\nnot just the last one.", "@click.option('--message', '-m', multiple=True)")),
        fact("The default must be list/tuple, otherwise it becomes individual characters.", ("When passing a ``default`` with ``multiple=True``, the default value\nmust be a list or tuple, otherwise it will be interpreted as a list of\nsingle characters.",)),
    ], [], ["Plain string default is treated as one complete value."]),
    ("requests", "positive", "For Requests 2.32.3, does timeout bound the entire download or socket inactivity, what happens with no explicit timeout, and is 0.001 the library default or merely the shown example?", [
        fact("timeout bounds inactivity, not whole download; unspecified timeout does not time out.", ("``timeout`` is not a time limit on the entire response download;\n    rather, an exception is raised if the server has not issued a\n    response for ``timeout`` seconds (more precisely, if no bytes have been\n    received on the underlying socket for ``timeout`` seconds). If no timeout is specified explicitly, requests do\n    not time out.",)),
        fact("0.001 is an explicit example argument, not default.", ("requests.get('https://github.com/', timeout=0.001)",)),
    ], [], ["Requests defaults to timeout=0.001.", "timeout is an overall download deadline."]),
    ("requests", "positive", "Requests 2.32.3: does successful r.json() prove HTTP success, what should I check instead, and what exception results for a 204 No Content or invalid JSON?", [
        fact("Successful JSON decoding does not prove HTTP success; use raise_for_status or expected status_code.", ("It should be noted that the success of the call to ``r.json()`` does **not**\nindicate the success of the response.", "``r.raise_for_status()`` or check ``r.status_code`` is what you expect.")),
        fact("204 or invalid JSON causes requests.exceptions.JSONDecodeError.", ("In case the JSON decoding fails, ``r.json()`` raises an exception. For example, if\nthe response gets a 204 (No Content), or if the response contains invalid JSON,\nattempting ``r.json()`` raises ``requests.exceptions.JSONDecodeError``.",)),
    ], [], ["r.json() success proves HTTP success."]),
    ("pytest", "positive", "In pytest 8.3.5, do XFAIL and XPASS fail the suite by default, what changes for XPASS with strict=True, and which ini option changes the strict default?", [
        fact("Neither fails by default.", ("Both ``XFAIL`` and ``XPASS`` don't fail the test suite by default.",)),
        fact("strict=True turns XPASS into suite failure.", ("@pytest.mark.xfail(strict=True)", "This will make ``XPASS`` (\"unexpectedly passing\") results from this test to fail the test suite.")),
        fact("xfail_strict changes the strict default.", ("You can change the default value of the ``strict`` parameter using the\n``xfail_strict`` ini option:",)),
    ], [], ["XPASS always fails by default."]),
    ("pytest", "positive", "In pytest 8.3.5's skipif Python example, which comparison operator skips versions earlier than 3.10, when is the condition evaluated, and if several skipif decorators are applied must all conditions be true?", [
        fact("Example uses < (3,10), evaluated True during collection.", ("@pytest.mark.skipif(sys.version_info < (3, 10), reason=\"requires python3.10 or higher\")", "If the condition evaluates to ``True`` during collection, the test function will be skipped,")),
        fact("Any condition true suffices; not all.", ("If multiple ``skipif`` decorators are applied to a test function, it\nwill be skipped if any of the skip conditions is true.",)),
    ], [], ["Skip requires all decorators true.", "Example uses >= (3, 10) to skip earlier versions."]),
    ("tox", "positive", "For tox 4.24.1, are commands run after commands_pre fails, are commands_post still run, and how does a leading dash differ from ignore_errors=True with respect to failure status?", [
        fact("commands only execute after commands_pre succeeds.", ("The commands to be called for testing. Only execute if :ref:`commands_pre` succeed.",)),
        fact("commands_post executes regardless of commands and commands_pre outcomes.", ("Commands to run after running the :ref:`commands`. Execute regardless of the outcome of both :ref:`commands` and\n   :ref:`commands_pre`.",)),
        fact("Leading dash ignores failure status of that command.", ("The exit code of a command may be ignored (meaning they are always considered successful) by\n   prefixing the command with a dash (``-``)",)),
        fact("ignore_errors keeps going but overall failed status/nonzero is retained.", ("When executing the commands keep going even if a sub-command exits with non-zero exit code. The overall status will\n   be \"commands failed\", i.e. tox will exit non-zero in case any command failed.",)),
    ], [], ["ignore_errors makes failed commands successful.", "commands_post is skipped after commands_pre failure."]),
    ("tox", "positive", "tox 4.24.1: what is skip_missing_interpreters' declared default, what does true do if an interpreter is missing, and which wins if the command line switch is also passed?", [
        fact("Declared default is config.", (":keys: skip_missing_interpreters\n   :default: config",)),
        fact("true allows success for missing environments; CLI overrides config.", ("Setting this to ``true`` will force ``tox`` to return success even if some of the specified environments were\n   missing.", "the command line switch always overrides this setting if passed on the invocation. Setting it to ``config`` means\n   that the value is read from the config file.")),
    ], [], ["Declared default is true.", "Config always overrides command line."]),
    ("click", "partial", "For Click 8.1.8, how does --shout/--no-shout create a boolean flag, and what exact maximum option-name byte length does this options guide guarantee?", [
        fact("Slash separates enabling/disabling forms and implicitly sets is_flag=True.", ("accomplished by defining two flags in one go separated by a slash (``/``)\nfor enabling or disabling the option.  (If a slash is in an option string,\nClick automatically knows that it's a boolean flag and will pass\n``is_flag=True`` implicitly.)",)),
    ], ["Exact maximum option-name byte length guaranteed by the guide."], ["A numeric option-name byte limit is documented here."]),
    ("click", "partial", "For Click 8.1.8, under what condition is a single boolean flag's default hidden in help, and what guaranteed help-rendering latency in milliseconds does this guide specify?", [
        fact("Single-option boolean default False remains hidden.", ("For single option boolean flags, the default remains hidden if the default\nvalue is False.",)),
    ], ["Guaranteed help-rendering latency in milliseconds."], ["The guide supplies a guaranteed help latency."]),
    ("requests", "partial", "For Requests 2.32.3, which verb does not follow redirects by default, how can I enable it, and what numeric redirect-hop limit is guaranteed by this quickstart?", [
        fact("HEAD is the default exception; enable with allow_redirects=True.", ("By default Requests will perform location redirection for all verbs except\nHEAD.", "requests.head('http://github.com/', allow_redirects=True)")),
    ], ["Numeric redirect-hop limit guaranteed by the quickstart."], ["The quickstart provides a numeric maximum redirect-hop limit."]),
    ("requests", "partial", "In Requests 2.32.3, what order is Response.history in, and what guaranteed disk-retention duration for redirect history does the quickstart state?", [
        fact("Response.history is ordered oldest to most recent response.", ("The list is sorted from the oldest to the most recent\nresponse.",)),
    ], ["Guaranteed disk-retention duration of redirect history."], ["History is documented as persisted on disk for a fixed duration."]),
    ("pytest", "partial", "For pytest 8.3.5, what effect does --runxfail have on xfail markers and pytest.xfail calls, and what production database backup-retention duration is specified by this skipping guide?", [
        fact("--runxfail ignores marker and makes pytest.xfail ineffective.", ("pytest --runxfail", "you can force the running and reporting of an ``xfail`` marked test\nas if it weren't marked at all. This also causes :func:`pytest.xfail` to produce no effect.")),
    ], ["Production database backup-retention duration."], ["The skipping guide specifies a database backup retention policy."]),
    ("tox", "partial", "tox 4.24.1: what is allowlist_externals' default and how does * differ from the rm example, and what cryptographic signature verification algorithm for external commands is specified?", [
        fact("Default external-command allowlist is empty.", (":keys: allowlist_externals\n   :default: <empty list>",)),
        fact("rm is a named example; * matches every command and is not recommended.", ("list ``allowlist_externals=rm`` or ``allowlist_externals=/usr/bin/rm``. If you want to allow all external\n   commands you can use ``allowlist_externals=*`` which will match all commands (not recommended).",)),
    ], ["Cryptographic signature verification algorithm for external commands."], ["The allowlist performs a documented cryptographic signature check."]),
    ("click", "negative", "What exact option-parser heap-memory ceiling in bytes is guaranteed for Click 8.1.8 by the supplied options guide?", [], ["Guaranteed parser heap-memory ceiling in bytes."], ["A heap-memory ceiling is documented."]),
    ("requests", "negative", "Which encryption algorithm and key-rotation interval does the Requests 2.32.3 quickstart prescribe for storing Response.history on disk?", [], ["Encryption algorithm and key-rotation interval for on-disk history."], ["On-disk history encryption and key rotation are specified."]),
    ("requests", "negative", "What guaranteed maximum DNS retry count and exponential-backoff base does the Requests 2.32.3 quickstart specify for ConnectionError?", [], ["Guaranteed DNS retry count and backoff base."], ["The quickstart documents automatic retries and numeric backoff parameters."]),
    ("pytest", "negative", "What database transaction isolation level does pytest 8.3.5's skipping guide guarantee for pytest.importorskip?", [], ["Database transaction isolation level for importorskip."], ["importorskip guarantees a database isolation level."]),
    ("tox", "negative", "What container-image signing algorithm and key-rotation schedule does tox 4.24.1's configuration reference prescribe for allowlist_externals?", [], ["Container-image signing algorithm and key rotation for external-command allowlist."], ["The reference prescribes container signing or key rotation for allowlist_externals."]),
    ("tox", "negative", "What exact automatic rollback and filesystem snapshot-retention guarantee does tox 4.24.1 specify when commands_post fails?", [], ["Automatic rollback and filesystem snapshot retention on commands_post failure."], ["commands_post failure triggers documented rollback and snapshot retention."]),
]


def main():
    questions, oracle, audit = [], [], []
    for number, (family, kind, question, facts, unavailable, forbidden) in enumerate(ROWS, 1):
        case_id = f"NEW{number:02d}"
        questions.append(dict(id=case_id, project_group=family, family=family,
                              question=question, answerability=kind, split="NEW20", source_kind="project"))
        path = PATHS[family]
        raw = (ROOT / path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        required = []
        for index, value in enumerate(facts, 1):
            sets = []
            for alternative in value["alternatives"]:
                witnesses = []
                for text in alternative:
                    needle = text.encode("utf-8")
                    start = raw.index(needle)
                    end = start + len(needle)
                    witnesses.append(dict(path=path, sha256=digest, text=text,
                                          start_byte=start, end_byte=end,
                                          start_line=raw[:start].count(b"\n") + 1,
                                          end_line=raw[:end].count(b"\n") + 1))
                    audit.append(dict(case_id=case_id, fact_id=f"F{index}", path=path,
                                      sha256=digest, start_byte=start, end_byte=end,
                                      exact=raw[start:end] == needle))
                sets.append(witnesses)
            required.append(dict(id=f"F{index}", statement=value["statement"], witness_sets=sets))
        oracle.append(dict(id=case_id, required_facts=required, unavailable_obligations=unavailable,
                           forbidden_claims=forbidden, negative_empty_sources=kind == "negative"))
    for name, data in [("questions.json", dict(schema_version=1, dataset_id="NEW20-20261013", cases=questions)),
                       ("oracle.json", dict(schema_version=1, dataset_id="NEW20-20261013", offset_unit="UTF-8 byte half-open", cases=oracle)),
                       ("witness-audit.json", dict(schema_version=1, boundary="data-only; no product calls", witnesses=audit))]:
        (ROOT / "sealed" / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
