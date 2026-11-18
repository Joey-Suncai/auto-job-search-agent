#!/usr/bin/env python3
"""Cases for pick_track (JSA-194): real job titles from the store; expected tracks derived by hand from the rules in the module's
docstring (title names the function → that track; otherwise JD keywords with a clear margin; otherwise not confident).
    python3 scripts/test_pick_track.py   → "fails 0" """
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'resume-updater', 'scripts'))
from pick_track import pick_track

LLM_JD = "You will build LLM agents, prompt engineering and RAG pipelines for generative AI products. Agents call tools."
DE_JD = "Build ETL and data pipelines on Airflow, dbt and Spark; own the data warehouse in Snowflake. SQL required."
DA_JD = "Build dashboards in Tableau and Power BI; define KPIs; present to stakeholders. Excel and SQL."
PM_JD = "Own the product roadmap, write product requirements and user stories, define product strategy and go-to-market."
VAGUE = "Join our team this summer. You will learn, collaborate and contribute to real projects. Great mentorship."
CASES = [  # (name, title, jd, track, confident)
    ("title: AI engineering", "AI Engineering Intern - Summer 2027", "", "AI_Agentic_Engineer", True),
    ("title: data engineering beats AI in the same title", "Data Engineering Intern - AI & Analytics (Summer 2027)", "", "Data_Engineer", True),
    ("title: data engineer, AI platform", "Data Engineer, AI Platform", "", "Data_Engineer", True),
    ("title: AI product manager is a product job", "AI Product Manager Intern", "", "Product_Manager", True),
    ("title: product manager", "Product Manager Intern - Summer 2027", "", "Product_Manager", True),
    ("title: technical program manager", "2027 Technical Program Manager Intern", "", "Product_Manager", True),
    ("title: business analyst", "Business Analyst Intern", "", "Data_Analyst", True),
    ("title: marketing analytics", "Marketing Analytics Intern", "", "Data_Analyst", True),
    ("title: data scientist", "Data Scientist Intern", "", "Data_Analyst", True),
    ("title: ML in the title", "Software Engineering Intern - SWE/ML (Summer 2027)", "", "AI_Agentic_Engineer", True),
    ("title: product engineering is not product management", "Product Engineering Intern - Summer 2027", "", None, False),
    ("plain software engineer, vague JD → not confident", "Software Engineer Intern", VAGUE, None, False),
    ("plain intern title + LLM JD → AI", "Summer 2027 Intern", LLM_JD, "AI_Agentic_Engineer", True),
    ("plain intern title + pipeline JD → DE", "Summer 2027 Intern", DE_JD, "Data_Engineer", True),
    ("plain intern title + dashboard JD → DA", "Summer 2027 Intern", DA_JD, "Data_Analyst", True),
    ("plain intern title + roadmap JD → PM", "Summer 2027 Intern", PM_JD, "Product_Manager", True),
    ("mixed JD without a margin → not confident", "Summer 2027 Intern", DA_JD + " " + DE_JD, None, False),
    ("weak title words stay with the JD: ML engineer, Reporting", "Machine Learning Engineer, Reporting", "", "AI_Agentic_Engineer", True),
    ("bare 'Analytics Platform' software engineer → not decided by the title", "Software Engineer, Analytics Platform", VAGUE, None, False),
    ("Insights designer is not a data analyst", "Product Designer, Insights", VAGUE, None, False),
    ("Agent Support Specialist is not AI", "Agent Support Specialist", VAGUE, None, False),
    ("Real Estate Agent Analyst is not AI", "Real Estate Agent Analyst", VAGUE, None, False),
    ("Program Manager, AI is not an AI engineer by title", "Program Manager, AI", VAGUE, None, False),
    ("empty everything", "", "", None, False),
]
fails = 0
for name, title, jd, track, conf in CASES:
    r = pick_track(title, jd)
    if r["track"] != track or r["confident"] != conf:
        fails += 1; print("FAIL", name, "→", r["track"], r["confident"], r["scores"])
    else:
        print("ok  ", name)
print("fails", fails); sys.exit(1 if fails else 0)
