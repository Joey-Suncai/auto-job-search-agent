"""Features for job scoring v2 (JSA-096, docs/specs/pipeline-scoring-v2.md): role category, sponsorship level, green card.

role_category(title) → one of ROLES (first rule that matches wins):
  ai_pm         PM words + AI words
  data_analysis data / business analyst, BI, product analytics, analytics
  pm            PM words, product operations / solutions (Joey 2026-11-03: 「算普通PM」)
  ai_engineering     AI words + an engineering word (engineer, developer, software, scientist, research, machine learning,
                     ML, NLP, deep learning, computer vision, MLOps, center of excellence)
  ai_nonengineering  AI words otherwise (a generic "AI Intern", AI strategy / analyst / operations…)
  data          data science / engineering, quant, statistics, database
  other         none of the above
"""
import re

ROLES = ["ai_pm", "data_analysis", "pm", "ai_nonengineering", "ai_engineering", "data", "other"]
ROLE_LABEL = {"ai_pm": "AI PM", "data_analysis": "数据分析 / BI / 产品分析", "pm": "PM（含 Product Ops / Solutions）",
              "ai_nonengineering": "AI 相关（非工程）", "ai_engineering": "AI 相关（偏工程）", "data": "数据相关", "other": "其他"}
SPONSOR_LEVELS = ["offers", "strong", "some", "unknown", "blocked"]
SPONSOR_LABEL = {"offers": "职位写明提供担保", "strong": "公司 H-1B 很多", "some": "公司有一些 H-1B 记录",
                 "unknown": "担保情况未知", "blocked": "写明不担保 / 要求公民"}

_w = lambda *ws: re.compile(r"\b(" + "|".join(ws) + r")\b", re.I)
AI = _w("ai", r"a\.i\.", "artificial intelligence", "machine learning", "ml", "llms?", "genai", "gen ai", "generative",
        "agents?", "agentic", "nlp", "deep learning", "computer vision", "applied ai", "ai/ml", "mlops", "foundation models?",
        "conversational ai", "applied scientist", "applied science")
PM = _w("product manager", "product management", "apm", "associate product manager", "product owner", "product intern",
        "product strategy", "product operations", "product ops", "product solutions", "technical program manager",
        "technical program management", "program manager", "program management")
DA = _w("data analysts?", "data analytics", "business analysts?", "business analytics", "business intelligence",
        "bi analyst", "bi developer", "bi engineer", "power bi", "tableau", "analytics intern", "reporting analyst",
        "insights analyst", "marketing analyst", "operations analyst", "strategy analyst", r"data visuali[sz]ation",
        "product analysts?", "product analytics", "growth analyst", "analytics")
# AI roles count as engineering-heavy unless the title names a non-engineering function (Joey 2026-11-03: 工程位偏重的 AI 岗再扣)
NONENG = _w("strategy", "strategist", "consulting", "consultant", "analyst", "analytics", "operations", "business",
            "go-to-market", "gtm", "marketing", "sales", "policy", "governance", "evaluation", "trust", "safety",
            "product", "specialist", "associate", "solutions", "partnerships", "finance", "content", "design")
ENG_STRONG = _w("engineer", "engineering", "developer", "sde", "swe", "software", "scientist", "research", "researcher",
                "machine learning", "ml", "nlp", "deep learning", "computer vision", "mlops", "center of excellence",
                "architect", "architecture", "vlsi", "cad", "firmware", "hardware", "embedded", "silicon", "chip")
SWE_ANALYTICS = _w("software engineer", "software engineering", "software developer", "sde", "swe", "engineer")
DA_STRONG = _w("data analysts?", "business analysts?", "business intelligence", "bi analyst", "bi developer", "bi engineer",
               "power bi", "tableau", "reporting analyst", "insights analyst", "marketing analyst", "operations analyst",
               "strategy analyst", "product analysts?", "product analytics", "growth analyst", "analytics intern")
DATA = _w("data scientists?", "data science", "data engineer", "data engineering", "analytics engineer", r"data(?! center)",
          "quantitative", "quant", "statistics?", "statistical", "decision science", "etl", "database")


def role_category(title):
    t = title or ""
    ai, pm = bool(AI.search(t)), bool(PM.search(t))
    if pm and ai:
        return "ai_pm"
    # "analytics" alone in an engineering title (Software Engineer, Data Platform / Analytics) is data, not analysis
    if DA_STRONG.search(t) or (DA.search(t) and not SWE_ANALYTICS.search(t)):
        return "data_analysis"
    if pm:
        return "pm"
    if ai:
        # blind check 1 (2026-11-03): a generic "AI Intern" is not engineering-heavy; ML / NLP / CV titles are
        return "ai_engineering" if ENG_STRONG.search(t) else "ai_nonengineering"
    if DATA.search(t):
        return "data"
    return "other"


def sponsor_level(job):
    s = job.get("sponsorship") or ""
    if s.startswith("Blocked"):
        return "blocked"
    return {"Posting offers sponsorship": "offers", "Strong H-1B sponsor": "strong",
            "Some H-1B history": "some"}.get(s, "unknown")


def green_card(job):
    return (job.get("gc_sponsor") or "") == "Yes"


# value model v2 (2026-11-03, docs/specs/pipeline-scoring-v2.md "Results"): only the effects both elicitation methods
# agreed on — AI PM highest, PM next, engineering-heavy AI lowest; no company-size term
VALUE_TIERS = {"ai_pm": 3, "pm": 2, "data_analysis": 1, "data": 1, "ai_nonengineering": 1, "ai_engineering": 0, "other": 0}


def value_tier(title):
    return VALUE_TIERS[role_category(title)]
