from app.proposal_engine import detect_proposals, extract_blocks, sanitize_fragment


def test_extract_blocks_tracks_heading_context():
    blocks = extract_blocks("<h2>4.2 Emergency Procedures</h2><p>The operator shall report.</p>")
    assert blocks[1].section_number == "4.2"
    assert blocks[1].section_heading == "Emergency Procedures"
    assert blocks[1].text == "The operator shall report."


def test_detect_proposals_creates_one_proposal_per_atomic_change():
    proposals = detect_proposals(
        "<h2>4.2 Emergency Procedures</h2><p>The operator shall report.</p>",
        "<h2>4.2 Emergency Procedures</h2><p>The remote pilot shall report.</p>",
        base_version_id="VER-001",
    )
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["target_ref"].startswith("§4.2")
    assert proposal["original_text"] == "operator"
    assert proposal["proposed_text"] == "remote pilot"
    assert proposal["base_version_id"] == "VER-001"
    assert "<p>" in proposal["original_excerpt_html"]
    assert "<" not in proposal["original_text"]


def test_detect_proposals_tracks_inserted_section_content():
    proposals = detect_proposals(
        "<h2>4.2 Emergency Procedures</h2><p>Existing.</p>",
        "<h2>4.2 Emergency Procedures</h2><p>Existing.</p><p>New requirement.</p>",
        base_version_id="VER-002",
    )
    assert len(proposals) == 1
    assert proposals[0]["proposed_text"] == "New requirement."
    assert proposals[0]["original_text"] == ""


def test_detect_proposals_groups_full_paragraph_rewrite_into_one_proposal():
    original = "<h2>4.2 Emergency Procedures</h2><p>" + " ".join(f"word{i}" for i in range(45)) + "</p>"
    proposed = "<h2>4.2 Emergency Procedures</h2><p>" + " ".join(f"replacement{i}" for i in range(45)) + "</p>"
    proposals = detect_proposals(original, proposed, base_version_id="VER-004")
    assert len(proposals) == 1
    assert proposals[0]["proposal_type"] == "paragraph"
    assert proposals[0]["changed_token_count"] >= 10


def test_detect_proposals_keeps_far_apart_small_changes_separate():
    original = "<h2>4.2 Emergency Procedures</h2><p>one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty.</p>"
    proposed = "<h2>4.2 Emergency Procedures</h2><p>ONE two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen NINETEEN twenty.</p>"
    proposals = detect_proposals(original, proposed, base_version_id="VER-005")
    assert len(proposals) == 2
def test_detect_proposals_falls_back_to_document_tail_text_nodes():
    proposals = detect_proposals("<p>Existing</p>", "<p>Existing</p> appended", base_version_id="VER-003")
    assert proposals
    assert proposals[0]["target_ref"].endswith("document tail")


def test_sanitize_fragment_removes_scripts_and_attributes():
    output = sanitize_fragment('<p onclick="bad()">Safe <strong>text</strong></p><script>alert(1)</script>')
    assert output == "<p>Safe <strong>text</strong></p>"
