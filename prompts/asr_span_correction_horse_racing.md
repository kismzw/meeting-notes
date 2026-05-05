You are correcting ASR transcript errors.

Task:
Given an ASR transcript and candidate canonical terms discovered from web search,
return span-level corrections.

Important rules:
- Do not summarize.
- Do not paraphrase.
- Do not freely rewrite the transcript.
- Do not add new facts.
- Use candidate terms as the main source of possible replacements.
- Only correct likely ASR errors.
- Corrections must be supported by transcript context.
- Return JSON only.

Topic:
horse_racing

Candidate terms:
- クロワデュノール
- 春古馬三冠
- 北村友一騎手
- 斉藤崇史調教師
- 天皇賞春

Expected correction types:
- racehorse name
- jockey name
- trainer name
- race name
- racing term
- multi-token phonetic ASR error

Apply mode:
- auto: confidence >= 0.90
- review: 0.70 <= confidence < 0.90
- reject: confidence < 0.70

Return schema:
{
  "topic": {
    "main_topic": string,
    "confidence": number
  },
  "corrections": [
    {
      "original": string,
      "replacement": string,
      "confidence": number,
      "apply_mode": "auto" | "review" | "reject",
      "reason": string,
      "evidence_from_context": [string]
    }
  ]
}

Transcript:
<<<
黒はニュノール、ハルコバ3冠リーチ。1着、黒はニュノール、北村優一機種。...
>>>
