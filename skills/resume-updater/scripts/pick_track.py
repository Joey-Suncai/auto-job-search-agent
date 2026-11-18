#!/usr/bin/env python3
"""Base resume track chosen by rules, not by DeepSeek (JSA-194, spec runner-apply-self-optimization step 9).

    pick_track(title, jd) -> {'track': <one of TRACKS or None>, 'confident': bool, 'reason': str, 'scores': {track: n}}

1. The job TITLE decides when it names a function (first match wins; order matters — "AI Product Manager" is a product
   job, "Data Engineer, AI" is a data-engineering job):
   product manager / product management / product analyst / APM / "product intern" → Product_Manager;
   data engineer / ETL / data pipeline / analytics engineer / data platform → Data_Engineer;
   data analyst / business analyst / BI / analytics / insights / reporting → Data_Analyst;
   AI / ML / machine learning / LLM / agent(ic) / GenAI / generative / prompt / NLP / deep learning → AI_Agentic_Engineer.
2. Otherwise the JD body: each track has weighted keywords (whole words); the best track is chosen when it has ≥ 4 points
   and at least twice the runner-up. Anything else → confident = False and the caller asks DeepSeek (which only picks,
   never decides alone when a rule is sure).
Pure; tested by scripts/test_pick_track.py (cases from real titles / JD wording in the store).
"""
import re

TRACKS = ["Data_Engineer", "Data_Analyst", "Product_Manager", "AI_Agentic_Engineer"]
TITLE_RULES = [  # (track, pattern) — first match wins; only titles that name the function outright (weak words are left to the JD)
    ("Product_Manager", r"\bproduct (?:manage(?:r|ment)|analyst|owner)\b|\bAPM\b|\bTPM\b|\btechnical program manager\b"),
    ("Data_Engineer", r"\bdata engineer\w*|\bETL\b|\bdata pipelines?\b|\banalytics engineer\w*|\bdata platform\b|\bdatabase engineer\w*|\bbig data\b"),
    ("Data_Analyst", r"\bdata analy\w+|\bbusiness (?:intelligence|analy\w+)|\bBI (?:analyst|developer|intern)\b|\banalytics (?:analyst|intern|associate)\b|\b\w+ analytics intern\b|\bdata scien\w+|\bstatistic\w* (?:analyst|intern)\b"),
    ("AI_Agentic_Engineer", r"\b(?:AI|ML|machine learning|LLM|GenAI|generative AI|NLP|deep learning|agentic)\b[^,]*\b(?:engineer\w*|scientist|researcher|developer|intern(?:ship)?)\b|\b(?:engineer\w*|scientist|researcher|developer|intern(?:ship)?)\b[^,]*\b(?:AI|ML|machine learning|LLM|GenAI|generative AI|NLP|deep learning)\b|\bAI agents?\b"),
]
BODY = {
    "Data_Engineer": [(r"\betl\b|\belt\b", 3), (r"data pipelines?", 3), (r"\bairflow\b|\bdbt\b|\bspark\b|\bkafka\b|\bsnowflake\b|\bdatabricks\b", 2),
                      (r"data warehouse|data lake|data model(?:l)?ing", 2), (r"\bsql\b", 1)],
    "Data_Analyst": [(r"dashboards?", 2), (r"\btableau\b|\bpower bi\b|\blooker\b", 3), (r"business intelligence", 3),
                     (r"\bkpis?\b|\bmetrics\b", 1), (r"\bexcel\b", 1), (r"\bsql\b", 1), (r"stakeholders?", 1), (r"ad[- ]hoc", 1)],
    "Product_Manager": [(r"product roadmap|roadmaps?", 3), (r"product requirements?|\bprds?\b|user stories", 3), (r"product strategy|go[- ]to[- ]market", 3),
                        (r"customer (?:needs|discovery|research)|user research", 2), (r"cross[- ]functional", 1), (r"\bprioriti[sz]\w+", 1)],
    "AI_Agentic_Engineer": [(r"\bllms?\b|large language models?", 3), (r"\bagents?\b|\bagentic\b", 3), (r"generative ai|\bgenai\b", 3),
                            (r"\brag\b|retrieval[- ]augmented|prompt engineering|\bprompts?\b", 2), (r"machine learning|deep learning|\bml\b|\bnlp\b", 1),
                            (r"fine[- ]tun\w+|\bembeddings?\b|vector (?:db|database|store)", 2)],
}


def pick_track(title, jd):
    t = title or ""
    for track, rx in TITLE_RULES:
        if re.search(rx, t, re.I):
            return {"track": track, "confident": True, "reason": f"title names the function ({track}): {t.strip()[:80]}", "scores": {}}
    body = (jd or "").lower()
    scores = {k: sum(min(len(re.findall(rx, body, re.I)), 3) * w for rx, w in rules) for k, rules in BODY.items()}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], TRACKS.index(kv[0])))
    (best, top), (_, second) = ranked[0], ranked[1]
    if top >= 4 and top >= 2 * second:
        return {"track": best, "confident": True, "reason": f"JD keywords point to {best} ({top} vs {second})", "scores": scores}
    return {"track": None, "confident": False, "reason": f"title and JD do not settle it (best {best} {top} vs {second})", "scores": scores}


if __name__ == "__main__":
    import sys, json
    print(json.dumps(pick_track(sys.argv[1], open(sys.argv[2]).read() if len(sys.argv) > 2 else ""), ensure_ascii=False))
