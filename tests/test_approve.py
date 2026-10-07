import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from add_posts import problems_of  # noqa: E402
from approve import drop, edit, go  # noqa: E402


def queue():
    return [
        {"id": "a1", "text": "平面図のPDFを1枚入れたら、家が3Dで建った", "category": "作品紹介",
         "sources": ["https://madori-presentation.vercel.app"], "status": "draft"},
        {"id": "b2", "text": "仕事でいちばん面倒な書類って何ですか？", "category": "問いかけ", "status": "draft"},
        {"id": "c3", "text": "投稿済み", "status": "posted"},
    ]


def test_go_moves_only_named_draft_to_queued():
    q = queue()
    go(q, ["a1"])
    assert [p["status"] for p in q] == ["queued", "draft", "posted"]
    assert "approved_at" in q[0]


def test_go_all_skips_non_drafts():
    q = queue()
    go(q, ["all"])
    assert [p["status"] for p in q] == ["queued", "queued", "posted"]


def test_unknown_or_posted_id_is_refused():
    with pytest.raises(SystemExit):
        go(queue(), ["c3"])


def test_drop_marks_rejected():
    q = queue()
    drop(q, ["b2"])
    assert q[1]["status"] == "rejected"


def test_edit_rejects_ai_phrasing():
    with pytest.raises(SystemExit):
        edit(queue(), "a1", "マドリ3Dについて解説します")


def test_edit_keeps_draft_status():
    q = queue()
    edit(q, "a1", "図面1枚で、家が建った。")
    assert q[0]["text"] == "図面1枚で、家が建った。" and q[0]["status"] == "draft"


def test_murmur_needs_no_source():
    assert problems_of({"text": "今日はAIと壁打ちしてた", "category": "つぶやき"}) == []


def test_edit_works_on_posts_with_rendered_images():
    q = [{"id": "i1", "text": "旧", "category": "作品紹介", "sources": ["https://x"], "status": "draft",
          "image": "queue/images/i1.png", "image_spec": {"kind": "checklist", "title": "t", "items": ["a"]}}]
    edit(q, "i1", "新しい本文")
    assert q[0]["text"] == "新しい本文"
