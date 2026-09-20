from tests.docs._reference_binding_fixtures import capture_reference_case, visible


def test_file_name_need_not_repeat_inside_its_body(tmp_path):
    cap = capture_reference_case(tmp_path, {
        "VeloraGuide.md": "# Installation\n\nInstallation command: run `velora prepare`.\n",
    }, "What installation command is documented in the file VeloraGuide?")
    assert "velora prepare" in visible(cap)
    assert {s["path_or_url"] for s in cap["public_payload"]["sources"]} == {"VeloraGuide.md"}


def test_implicit_named_document_does_not_create_a_body_subject(tmp_path):
    cap = capture_reference_case(tmp_path, {"VeloraGuide.md":
        "# Lumina\n\nLumina in three points:\n\n- Nested commands\n- Generated help\n- Lazy subcommands\n"
    }, "What three capabilities summarize Lumina in the VeloraGuide?")
    assert all(fact in visible(cap) for fact in ("Nested commands", "Generated help", "Lazy subcommands"))


def test_matching_file_name_is_not_code_identity_proof(tmp_path):
    cap = capture_reference_case(tmp_path, {"VeloraGuide.md":
        "# Returns\n\nThe other constant returns `73`.\n"
    }, "What does the constant `VeloraGuide` return?")
    assert "other constant returns" not in visible(cap)


def test_existing_file_does_not_prove_an_unrelated_fact(tmp_path):
    cap = capture_reference_case(tmp_path, {"VeloraGuide.md": "# Gardening\n\nWater the basil every evening.\n"},
        "What installation command is documented in the file VeloraGuide?")
    assert "Water the basil" not in visible(cap)


def test_other_file_cannot_replace_a_missing_locator(tmp_path):
    cap = capture_reference_case(tmp_path, {"OtherGuide.md": "# Installation\n\nInstallation command: run `velora prepare`.\n"},
        "What installation command is documented in the file VeloraGuide?")
    assert not cap["public_payload"].get("sources")


def test_resolved_locator_excludes_other_relevant_source(tmp_path):
    cap = capture_reference_case(tmp_path, {
        "VeloraGuide.md": "# Installation\n\nInstallation command: run `velora prepare`.\n",
        "Other.md": "# Installation\n\nInstallation command: run `other prepare`.\n",
    }, "What installation command is documented in the file VeloraGuide?")
    assert "velora prepare" in visible(cap) and "other prepare" not in visible(cap)


def test_unretrieved_catalog_collision_is_not_unique(tmp_path):
    cap = capture_reference_case(tmp_path, {
        "a/VeloraGuide.md": "# Installation\n\nInstallation command: run `velora prepare`.\n",
        "b/VeloraGuide.md": "# Gardening\n\nWater the basil.\n",
    }, "What installation command is documented in the file VeloraGuide?")
    assert not cap["public_payload"].get("sources")


def test_same_spelling_keeps_symbol_and_source_obligations(tmp_path):
    cap = capture_reference_case(tmp_path, {
        "ARGON.md": "# Constants\n\nThe constant ARGON returns `73`.\n",
        "Other.md": "# Constants\n\nThe constant ARGON returns `91`.\n",
    }, "What does the constant `ARGON` return in the file ARGON?")
    assert "73" in visible(cap) and "91" not in visible(cap)


def test_filename_cannot_discharge_same_spelling_symbol(tmp_path):
    cap = capture_reference_case(tmp_path, {"ARGON.md": "# Constants\n\nThe constant OTHER returns `73`.\n"},
        "What does the constant `ARGON` return in the file ARGON?")
    assert "73" not in visible(cap)


def test_verified_owner_supports_its_warning(tmp_path):
    cap = capture_reference_case(tmp_path, {"Tasks.md":
        "# QueueTasks\n\nQueueTasks groups task functions.\n\nTasks execute in order. If one raises an exception, later tasks stop.\n"
    }, "In the file Tasks, if one QueueTasks function raises an exception, what happens to later tasks and their ordering?")
    assert "execute in order" in visible(cap) and "later tasks stop" in visible(cap)


def test_other_semantic_owner_does_not_inherit_subject(tmp_path):
    cap = capture_reference_case(tmp_path, {"Tasks.md":
        "# QueueTasks\n\nQueueTasks groups task functions.\n\n## OtherTasks\n\nTasks execute in order. If one raises an exception, later tasks stop.\n"
    }, "In the file Tasks, if one QueueTasks function raises an exception, what happens to later tasks and their ordering?")
    assert "later tasks stop" not in visible(cap)
