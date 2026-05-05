from __future__ import annotations

import json

from application.services.polish_web_llm import PolishWebLLMConfig, PolishWebLLMService


class FakeSearch:
    def __init__(self, results):
        self.results = results

    def search(self, query, max_results):
        return self.results[:max_results]


class FakeOllama:
    def __init__(self, response_obj):
        self.response_obj = response_obj
        self.last_prompt = ""

    def generate(self, model, prompt):
        self.last_prompt = prompt
        return {"response": json.dumps(self.response_obj, ensure_ascii=False)}


def _run(tmp_path, text, search_results, llm_corrections):
    llm = FakeOllama({"topic": {"main_topic": "horse_racing", "confidence": 0.95}, "corrections": llm_corrections})
    svc = PolishWebLLMService(search_client=FakeSearch(search_results), ollama_client=llm)
    out = svc.run(text, str(tmp_path), PolishWebLLMConfig(model="qwen3:8b", topic_hint="horse_racing"))
    return out, llm


def test_kurowa_not_auto_replace(tmp_path):
    text = "クロワが強い"
    search = [{"title": "クロワデュノール 天皇賞春", "snippet": "", "url": "u"}]
    out, _ = _run(tmp_path, text, search, [{"original": "クロワ", "replacement": "クロワデュノール", "confidence": 0.96, "apply_mode": "auto", "correction_type": "full_name_correction", "reason": "x", "evidence_from_context": []}])
    c = out["corrections"][0]
    assert c["apply_mode"] in {"review", "reject"}


def test_kurowa_abbreviation_link(tmp_path):
    text = "クロワが強い"
    search = [{"title": "クロワデュノール 天皇賞春", "snippet": "", "url": "u"}]
    out, _ = _run(tmp_path, text, search, [{"original": "クロワ", "replacement": "クロワデュノール", "confidence": 0.85, "apply_mode": "review", "correction_type": "abbreviation_link", "reason": "abbr", "evidence_from_context": []}])
    c = out["corrections"][0]
    assert c["correction_type"] == "abbreviation_link"
    assert c["canonical_entity"] == "クロワデュノール"


def test_kuroha_nyunoru_can_be_fullname(tmp_path):
    text = "黒はニュノール"
    search = [{"title": "クロワデュノール 天皇賞春", "snippet": "", "url": "u"}]
    out, _ = _run(tmp_path, text, search, [{"original": "黒はニュノール", "replacement": "クロワデュノール", "confidence": 0.93, "apply_mode": "auto", "correction_type": "full_name_correction", "reason": "x", "evidence_from_context": []}])
    assert out["corrections"][0]["apply_mode"] in {"auto", "review"}


def test_nyunoru_alone_not_auto_without_expansion(tmp_path):
    text = "ニュノール"
    search = [{"title": "クロワデュノール 天皇賞春", "snippet": "", "url": "u"}]
    out, _ = _run(tmp_path, text, search, [{"original": "ニュノール", "replacement": "クロワデュノール", "confidence": 0.95, "apply_mode": "auto", "correction_type": "full_name_correction", "reason": "x", "evidence_from_context": []}])
    assert out["corrections"][0]["apply_mode"] != "auto"


def test_shunten_abbreviation_link(tmp_path):
    text = "春天で勝った"
    search = [{"title": "天皇賞春 クロワデュノール", "snippet": "", "url": "u"}]
    out, _ = _run(tmp_path, text, search, [{"original": "春天", "replacement": "天皇賞春", "confidence": 0.90, "apply_mode": "auto", "correction_type": "abbreviation_link", "reason": "abbr", "evidence_from_context": []}])
    c = out["corrections"][0]
    assert c["correction_type"] == "abbreviation_link"
    assert c["apply_mode"] == "review"


def test_harukoba3kan_can_be_correction(tmp_path):
    text = "ハルコバ3冠リーチ"
    search = [{"title": "春古馬三冠にリーチ", "snippet": "", "url": "u"}]
    out, _ = _run(tmp_path, text, search, [{"original": "ハルコバ3冠", "replacement": "春古馬三冠", "confidence": 0.88, "apply_mode": "review", "correction_type": "typo_correction", "reason": "x", "evidence_from_context": []}])
    assert out["corrections"][0]["apply_mode"] == "review"


def test_pass2_search_generated_from_central_terms(tmp_path):
    text = "黒はニュノール 北村優一機種 斉藤忠教師"
    search = [{"title": "クロワデュノール 天皇賞春 北村友一騎手 斉藤崇史調教師", "snippet": "", "url": "u"}]
    out, _ = _run(tmp_path, text, search, [])
    pass2 = json.loads((tmp_path / "search" / "pass2_search_queries.json").read_text(encoding="utf-8"))
    assert len(pass2) >= 1
    assert any("クロワデュノール" in q or "天皇賞春" in q for q in pass2)


def test_topic_vocabulary_includes_related_terms_from_pass2(tmp_path):
    text = "黒はニュノール 北村優一機種 斉藤忠教師"
    search = [
        {"title": "クロワデュノール天皇賞春制覇", "snippet": "", "url": "u1"},
        {"title": "鞍上・北村友一騎手", "snippet": "", "url": "u2"},
        {"title": "斉藤崇史調教師の管理馬クロワデュノール", "snippet": "", "url": "u3"},
        {"title": "春古馬三冠にリーチ", "snippet": "", "url": "u4"},
    ]
    _run(tmp_path, text, search, [])
    vocab = json.loads((tmp_path / "vocabulary" / "topic_vocabulary.json").read_text(encoding="utf-8"))
    canonicals = {v["canonical"] for v in vocab}
    assert "クロワデュノール" in canonicals
    assert "天皇賞春" in canonicals
    assert "北村友一騎手" in canonicals
