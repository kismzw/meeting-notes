from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib import parse, request


@dataclass
class PolishWebLLMConfig:
    enable_transcript_polish: bool = True
    backend: str = "ollama"
    model: str = "qwen2.5:14b-instruct"
    topic_hint: str = "general"
    auto_apply_threshold: float = 0.90
    review_threshold: float = 0.70
    apply_auto_only: bool = False
    max_search_queries: int = 12
    max_search_results_per_query: int = 5
    ollama_url: str = "http://127.0.0.1:11434/api/generate"


class DuckDuckGoSearch:
    def search(self, query: str, max_results: int) -> list[dict[str, str]]:
        url = f"https://duckduckgo.com/html/?q={parse.quote(query)}"
        req = request.Request(url, headers={"User-Agent": "meeting-notes/1.0"})
        try:
            with request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return []

        out: list[dict[str, str]] = []
        for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html):
            title = re.sub(r"<.*?>", "", m.group(2)).strip()
            if not title:
                continue
            out.append({"title": title, "snippet": "", "url": m.group(1)})
            if len(out) >= max_results:
                break
        return out


class OllamaClient:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def generate(self, model: str, prompt: str) -> dict[str, Any]:
        payload = {"model": model, "prompt": prompt, "stream": False, "format": "json"}
        req = request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))


class PolishWebLLMService:
    def __init__(self, search_client: Optional[DuckDuckGoSearch] = None, ollama_client: Optional[OllamaClient] = None):
        self.search_client = search_client or DuckDuckGoSearch()
        self.ollama_client = ollama_client

    def run(self, transcript: str, output_dir: str, config: PolishWebLLMConfig, glossary_terms: Optional[list[str]] = None) -> dict[str, Any]:
        out = Path(output_dir)
        for d in ["topic", "spans", "search", "vocabulary", "llm", "corrections", "transcript", "report"]:
            (out / d).mkdir(parents=True, exist_ok=True)

        topic = self._infer_topic(transcript, config.topic_hint)
        spans = self._detect_suspicious_spans(transcript)

        # Pass 1 search
        pass1_queries = self._generate_queries(topic["main_topic"], spans, config.max_search_queries)
        pass1_results: list[dict[str, str]] = []
        for q in pass1_queries:
            pass1_results.extend(self.search_client.search(q, config.max_search_results_per_query))
        raw_web_terms = self._extract_raw_web_terms(pass1_results)
        pass1_mentions = self._extract_entity_mentions(topic["main_topic"], raw_web_terms, pass1_results)

        # Central terms + Pass 2 search
        central_terms = self._select_central_terms(topic["main_topic"], pass1_mentions, transcript)
        pass2_queries = self._generate_pass2_queries(topic["main_topic"], central_terms, config.max_search_queries)
        pass2_results: list[dict[str, str]] = []
        for q in pass2_queries:
            pass2_results.extend(self.search_client.search(q, config.max_search_results_per_query))
        pass2_mentions = self._extract_entity_mentions(topic["main_topic"], self._extract_raw_web_terms(pass2_results), pass2_results)

        all_mentions = pass1_mentions + pass2_mentions
        candidate_terms = self._build_candidate_terms(all_mentions)
        merged_terms = sorted(set(candidate_terms + (glossary_terms or [])))
        abbreviation_links = self._build_abbreviation_links(merged_terms)
        topic_vocabulary = self._build_topic_vocabulary(all_mentions)

        prompt = self._build_prompt(topic["main_topic"], raw_web_terms + self._extract_raw_web_terms(pass2_results), merged_terms, abbreviation_links, transcript)
        (out / "llm" / "prompt.txt").write_text(prompt, encoding="utf-8")

        client = self.ollama_client or OllamaClient(config.ollama_url)
        raw: dict[str, Any] = {}
        llm_error: str | None = None
        try:
            raw = client.generate(config.model, prompt)
            (out / "llm" / "raw_response.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            (out / "llm" / "raw_response.txt").write_text(str(raw.get("response", "")), encoding="utf-8")
        except Exception as exc:
            llm_error = f"llm_call_error: {exc}"
            (out / "llm" / "raw_response.json").write_text(json.dumps({"error": llm_error}, ensure_ascii=False, indent=2), encoding="utf-8")
            (out / "llm" / "raw_response.txt").write_text("", encoding="utf-8")

        parsed, parse_error = self._parse_llm_response(raw)
        if llm_error:
            parse_error = f"{llm_error}\n{parse_error or ''}".strip()
        if parse_error:
            (out / "llm" / "parse_error.txt").write_text(parse_error, encoding="utf-8")

        corrections = self._validate_corrections(
            transcript=transcript,
            corrections=parsed.get("corrections", []),
            candidate_terms=merged_terms,
            topic_vocabulary=topic_vocabulary,
            abbreviation_links=abbreviation_links,
            auto_apply_threshold=config.auto_apply_threshold,
            review_threshold=config.review_threshold,
        )
        polished = self._apply_auto_corrections(transcript, corrections, config.apply_auto_only)

        self._save_json(out / "topic" / "topic.json", topic)
        self._save_json(out / "spans" / "suspicious_spans.json", spans)
        self._save_json(out / "search" / "search_queries.json", pass1_queries)
        self._save_json(out / "search" / "search_results.json", pass1_results)
        self._save_json(out / "search" / "pass1_search_queries.json", pass1_queries)
        self._save_json(out / "search" / "pass1_search_results.json", pass1_results)
        self._save_json(out / "search" / "pass2_search_queries.json", pass2_queries)
        self._save_json(out / "search" / "pass2_search_results.json", pass2_results)
        self._save_json(out / "vocabulary" / "raw_web_terms.json", raw_web_terms)
        self._save_json(out / "vocabulary" / "pass1_entity_mentions.json", pass1_mentions)
        self._save_json(out / "vocabulary" / "central_terms.json", central_terms)
        self._save_json(out / "vocabulary" / "pass2_entity_mentions.json", pass2_mentions)
        self._save_json(out / "vocabulary" / "entity_mentions.json", all_mentions)
        self._save_json(out / "vocabulary" / "candidate_terms.json", candidate_terms)
        self._save_json(out / "vocabulary" / "topic_vocabulary.json", topic_vocabulary)
        self._save_json(out / "vocabulary" / "abbreviation_links.json", abbreviation_links)
        self._save_json(out / "vocabulary" / "merged_terms.json", merged_terms)
        self._save_json(out / "vocabulary" / "web_terms.json", candidate_terms)
        self._save_json(out / "corrections" / "corrections.json", corrections)
        self._save_json(out / "transcript" / "polished_transcript.json", {"text": polished})

        report = "\n".join(
            [
                "# Polish Web+LLM Report",
                f"- topic: {topic['main_topic']}",
                f"- suspicious_spans: {len(spans)}",
                f"- pass1_queries: {len(pass1_queries)}",
                f"- pass1_results: {len(pass1_results)}",
                f"- pass2_queries: {len(pass2_queries)}",
                f"- pass2_results: {len(pass2_results)}",
                f"- candidate_terms: {len(candidate_terms)}",
                f"- corrections: {len(corrections)}",
                f"- changed: {polished != transcript}",
                "",
            ]
        )
        (out / "report" / "polish_report.md").write_text(report, encoding="utf-8")

        return {"topic": topic, "corrections": corrections, "polished_transcript": polished}

    @staticmethod
    def _infer_topic(transcript: str, hint: str) -> dict[str, Any]:
        if hint:
            return {"main_topic": hint, "confidence": 0.95}
        if any(k in transcript for k in ["競馬", "騎手", "調教師", "写真判定"]):
            return {"main_topic": "horse_racing", "confidence": 0.88}
        return {"main_topic": "general", "confidence": 0.6}

    @staticmethod
    def _detect_suspicious_spans(transcript: str) -> list[dict[str, Any]]:
        patterns = [r"[一-龯ぁ-んァ-ヴー]{2,}(機種|教師)", r"[一-龯ぁ-んァ-ヴー]{2,}\d+冠", r"[ァ-ヴー]{3,}[一-龯ぁ-んァ-ヴー0-9]{0,8}"]
        spans: list[dict[str, Any]] = []
        seen = set()
        for pat in patterns:
            for m in re.finditer(pat, transcript):
                s, e = m.span()
                if (s, e) in seen:
                    continue
                seen.add((s, e))
                spans.append({"start_char": s, "end_char": e, "text": transcript[s:e], "reason": "pattern_match", "surrounding_context": transcript[max(0, s - 20):min(len(transcript), e + 20)]})
        return spans

    @staticmethod
    def _generate_queries(topic: str, spans: list[dict[str, Any]], max_queries: int) -> list[str]:
        base = ["競馬 写真判定 騎手 調教師 1着 レース 三冠"] if topic == "horse_racing" else [topic]
        for s in spans[:8]:
            base.append(f"競馬 {s['text']} 写真判定 騎手 調教師")
        return _dedup(base)[:max_queries]

    @staticmethod
    def _extract_raw_web_terms(search_results: list[dict[str, str]]) -> list[str]:
        out = []
        for r in search_results:
            if r.get("title"):
                out.append(str(r["title"]).strip())
            if r.get("snippet"):
                out.append(str(r["snippet"]).strip())
        return out

    @staticmethod
    def _extract_entity_mentions(topic: str, raw_web_terms: list[str], search_results: list[dict[str, str]]) -> list[dict[str, Any]]:
        texts = list(raw_web_terms) + [str(x.get("title", "")) for x in search_results] + [str(x.get("snippet", "")) for x in search_results]
        out: list[dict[str, Any]] = []
        for txt in texts:
            for can, ttype, conf in PolishWebLLMService._extract_mentions_from_text(topic, txt):
                out.append({"mention_text": can, "canonical": can, "term_type": ttype, "source_raw_text": txt, "evidence": [txt], "confidence": conf})
        return out

    @staticmethod
    def _extract_mentions_from_text(topic: str, text: str) -> list[tuple[str, str, float]]:
        out: list[tuple[str, str, float]] = []
        if topic != "horse_racing" or not text:
            return out
        if "天皇賞春" in text or "天皇賞・春" in text:
            out.append(("天皇賞春", "race_name", 0.90))
            m = re.search(r"([ァ-ヴー]{4,16})天皇賞", text)
            if m:
                out.append((m.group(1), "racehorse", 0.90))
        for m in re.finditer(r"([一-龯ぁ-んァ-ヴー]{2,12}騎手)", text):
            out.append((m.group(1), "jockey", 0.92))
        for m in re.finditer(r"([一-龯ぁ-んァ-ヴー]{2,12}調教師)", text):
            out.append((m.group(1), "trainer", 0.92))
        for m in re.finditer(r"([一-龯ぁ-んァ-ヴー]{1,10}賞(?:・[春秋])?)", text):
            out.append((m.group(1).replace("・", ""), "race_name", 0.88))
        for m in re.finditer(r"([一-龯ぁ-んァ-ヴー]{1,10}三冠)", text):
            out.append((m.group(1), "racing_term", 0.90))
        if "写真判定" in text:
            out.append(("写真判定", "racing_term", 0.90))
        if "ハナ差" in text:
            out.append(("ハナ差", "racing_term", 0.85))
        for m in re.finditer(r"([ァ-ヴー]{4,16}|[一-龯]{1,3}[ァ-ヴー]{3,16})", text):
            tok = m.group(1)
            if tok in {"コメント", "競馬ラボ", "調教レポート", "競走馬データベース", "競馬データベース", "マイネ王"}:
                continue
            if "賞" in tok:
                continue
            out.append((tok, "racehorse", 0.80))
        for m in re.finditer(r"([一-龯ぁ-んァ-ヴー]{1,10}賞)・([一-龯ぁ-んァ-ヴー]{1,10})", text):
            out.append((m.group(1), "race_name", 0.88))
            out.append((m.group(2), "race_name", 0.85))
        return out

    @staticmethod
    def _select_central_terms(topic: str, entity_mentions: list[dict[str, Any]], transcript: str) -> list[dict[str, Any]]:
        counts = Counter([str(x.get("canonical", "")) for x in entity_mentions if x.get("canonical")])
        importance = {"racehorse": 1.0, "jockey": 0.9, "trainer": 0.9, "race_name": 0.8, "racing_term": 0.7}
        scored: list[dict[str, Any]] = []
        for term, freq in counts.items():
            mention = next((m for m in entity_mentions if m.get("canonical") == term), {})
            ttype = str(mention.get("term_type", ""))
            rec = transcript.count(term)
            co = 1.0 if any(k in transcript for k in ["競馬", "レース", "騎手", "調教師", "三冠"]) else 0.0
            score = freq * 0.5 + rec * 0.3 + co * 0.2 + importance.get(ttype, 0.2)
            scored.append({"canonical": term, "term_type": ttype, "frequency": freq, "recurrence_in_transcript": rec, "cooccurrence_score": co, "central_score": round(score, 4)})
        scored.sort(key=lambda x: x["central_score"], reverse=True)
        return scored[:8]

    @staticmethod
    def _generate_pass2_queries(topic: str, central_terms: list[dict[str, Any]], max_queries: int) -> list[str]:
        keys = [x["canonical"] for x in central_terms[:4]]
        if topic != "horse_racing" or not keys:
            return []
        q = []
        q.append(f"{' '.join(keys)}")
        q.append(f"{' '.join(keys[:2])} 春古馬三冠 宝塚記念 大阪杯")
        q.append(f"{' '.join(keys[:2])} 日本ダービー 天皇賞春 戦績")
        q.append(f"{' '.join(keys[:1])} キタサンブラック 凱旋門賞 JC 有馬記念")
        return _dedup(q)[:max_queries]

    @staticmethod
    def _build_candidate_terms(entity_mentions: list[dict[str, Any]]) -> list[str]:
        bad = {"コメント", "競馬ラボ", "調教レポート", "競走馬データベース", "競馬データベース", "マイネ王"}
        out: dict[str, float] = {}
        for m in entity_mentions:
            can = str(m.get("canonical", "")).replace("・", "").strip()
            if not can or can in bad:
                continue
            if len(can) < 2 or len(can) > 18:
                continue
            score = float(m.get("confidence", 0.0))
            if can not in out or score > out[can]:
                out[can] = score
        return sorted(out.keys())

    @staticmethod
    def _build_abbreviation_links(candidate_terms: list[str]) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        for t in candidate_terms:
            if len(t) >= 6:
                links.append({"abbreviation": t[:3], "canonical": t})
            if "天皇賞春" == t:
                links.append({"abbreviation": "春天", "canonical": t})
        return _dedup_dicts(links)

    @staticmethod
    def _build_topic_vocabulary(entity_mentions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_term: dict[str, dict[str, Any]] = {}
        for m in entity_mentions:
            can = str(m.get("canonical", "")).replace("・", "").strip()
            if not can:
                continue
            if can not in by_term:
                by_term[can] = {
                    "canonical": can,
                    "term_type": str(m.get("term_type", "")),
                    "readings": [can],
                    "aliases": [],
                    "abbreviations": [can[:3]] if len(can) >= 6 else [],
                    "source_evidence": [],
                    "frequency": 0,
                    "cooccurrence_score": 0.0,
                }
            by_term[can]["frequency"] += 1
            by_term[can]["source_evidence"].extend(m.get("evidence", []))
            by_term[can]["cooccurrence_score"] = 1.0 if by_term[can]["frequency"] >= 2 else 0.5
        return sorted(by_term.values(), key=lambda x: x["frequency"], reverse=True)

    @staticmethod
    def _build_prompt(topic: str, raw_web_evidence: list[str], allowed_candidates: list[str], abbreviation_links: list[dict[str, str]], transcript: str) -> str:
        evidence = "\n".join([f"- {x}" for x in raw_web_evidence[:80]]) or "- (none)"
        candidates = "\n".join([f"- {x}" for x in allowed_candidates]) or "- (none)"
        abbr = "\n".join([f"- {x['abbreviation']} -> {x['canonical']}" for x in abbreviation_links[:40]]) or "- (none)"
        return (
            "You are correcting ASR transcript errors.\n\n"
            "Task:\nGiven an ASR transcript and candidate canonical terms discovered from web search, return span-level corrections.\n\n"
            "Important rules:\n"
            "- Do not summarize.\n- Do not paraphrase.\n- Do not freely rewrite the transcript.\n- Do not add new facts.\n"
            "- Return JSON only.\n- Do not use markdown.\n- If unsure, return empty corrections.\n\n"
            f"Topic:\n{topic}\n\n"
            f"Raw web evidence:\n{evidence}\n\n"
            f"Allowed replacement candidates:\n{candidates}\n\n"
            f"Abbreviation links:\n{abbr}\n\n"
            "Rules:\n"
            "- Replacement must be exactly one of Allowed replacement candidates.\n"
            "- Do not use raw web evidence strings as replacements.\n"
            "- Do not invent new replacement strings.\n"
            "- Do not replace an abbreviation with a full name if observed span is much shorter than candidate.\n"
            "- If likely abbreviation, return correction_type=abbreviation_link and keep transcript unchanged.\n"
            "- Only replace if observed span is likely misrecognition of full term.\n"
            "- Use correction_type in: full_name_correction, abbreviation_link, partial_span_expansion, typo_correction.\n\n"
            "Return schema:\n"
            "{\n"
            "  \"topic\": {\"main_topic\": string, \"confidence\": number},\n"
            "  \"corrections\": [\n"
            "    {\n"
            "      \"original\": string,\n"
            "      \"replacement\": string,\n"
            "      \"confidence\": number,\n"
            "      \"apply_mode\": \"auto\" | \"review\" | \"reject\",\n"
            "      \"correction_type\": string,\n"
            "      \"reason\": string,\n"
            "      \"evidence_from_context\": [string]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Transcript:\n<<<\n{transcript}\n>>>\n"
        )

    @staticmethod
    def _parse_llm_response(raw: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        text = str(raw.get("response", "")).strip()
        if not text:
            return {"topic": {"main_topic": "unknown", "confidence": 0.0}, "corrections": []}, "empty response"
        clean = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.S).strip()
        try:
            return json.loads(clean), None
        except Exception as exc:
            return {"topic": {"main_topic": "unknown", "confidence": 0.0}, "corrections": []}, f"json parse error: {exc}\nraw:\n{text}"

    @staticmethod
    def _normalize_identity(text: str) -> str:
        return re.sub(r"[\s\u3000、。,.!?！？・\-]", "", text)

    @staticmethod
    def _estimate_mora_count(text: str) -> int:
        t = re.sub(r"[^ァ-ヴーぁ-ん一-龯A-Za-z0-9]", "", text)
        return max(1, len(t))

    @classmethod
    def _validate_corrections(cls, transcript: str, corrections: list[dict[str, Any]], candidate_terms: list[str], topic_vocabulary: list[dict[str, Any]], abbreviation_links: list[dict[str, str]], auto_apply_threshold: float, review_threshold: float) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        candidate_set = set(candidate_terms)
        topic_vocab_set = {x.get("canonical", "") for x in topic_vocabulary}
        abbr_map = {x["abbreviation"]: x["canonical"] for x in abbreviation_links}
        for c in corrections:
            original = str(c.get("original", ""))
            replacement = str(c.get("replacement", ""))
            confidence = float(c.get("confidence", 0.0))
            ctype = str(c.get("correction_type", "full_name_correction"))
            reason = str(c.get("reason", ""))
            evidence = c.get("evidence_from_context", [])
            if not original or not replacement or original not in transcript:
                continue
            if cls._normalize_identity(original) == cls._normalize_identity(replacement):
                continue

            observed_len = cls._estimate_mora_count(original)
            cand_len = cls._estimate_mora_count(replacement)
            ratio = observed_len / max(1, cand_len)

            if ctype == "abbreviation_link":
                apply_mode = "review"
            elif confidence >= auto_apply_threshold:
                apply_mode = "auto"
            elif confidence >= review_threshold:
                apply_mode = "review"
            else:
                apply_mode = "reject"

            # mora length-aware downgrade
            if ratio < 0.45:
                if original in abbr_map and abbr_map[original] == replacement:
                    ctype = "abbreviation_link"
                    apply_mode = "review"
                else:
                    apply_mode = "reject"
                    reason = f"{reason} | rejected:low_length_ratio".strip(" |")
            elif 0.45 <= ratio < 0.55:
                if apply_mode == "auto":
                    apply_mode = "review"
                if ctype == "full_name_correction":
                    ctype = "abbreviation_link"
            elif 0.55 <= ratio < 0.75:
                if apply_mode == "auto" and ctype not in {"partial_span_expansion", "typo_correction"}:
                    apply_mode = "review"

            if replacement not in candidate_set:
                if apply_mode == "auto":
                    apply_mode = "review"
                elif apply_mode == "review":
                    apply_mode = "reject"
                reason = f"{reason} | not_in_candidate_terms".strip(" |")

            if replacement not in topic_vocab_set:
                apply_mode = "reject"
                reason = f"{reason} | not_in_topic_vocabulary".strip(" |")

            if ctype == "abbreviation_link":
                apply_mode = "review"

            out.append(
                {
                    "original": original,
                    "replacement": replacement,
                    "confidence": confidence,
                    "apply_mode": apply_mode,
                    "correction_type": ctype,
                    "canonical_entity": replacement if ctype == "abbreviation_link" else "",
                    "mora": {"observed": observed_len, "candidate": cand_len, "length_ratio": round(ratio, 4)},
                    "reason": reason,
                    "evidence_from_context": evidence if isinstance(evidence, list) else [str(evidence)],
                    "scores": {"confidence": confidence},
                }
            )
        return out

    @staticmethod
    def _apply_auto_corrections(transcript: str, corrections: list[dict[str, Any]], apply_auto_only: bool) -> str:
        out = transcript
        autos = [c for c in corrections if c.get("apply_mode") == "auto" and c.get("correction_type") != "abbreviation_link"]
        for c in sorted(autos, key=lambda x: len(str(x.get("original", ""))), reverse=True):
            out = out.replace(str(c["original"]), str(c["replacement"]))
        return out

    @staticmethod
    def _save_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _dedup(xs: list[str]) -> list[str]:
    out = []
    seen = set()
    for x in xs:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _dedup_dicts(xs: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    seen = set()
    for x in xs:
        key = (x.get("abbreviation", ""), x.get("canonical", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out
