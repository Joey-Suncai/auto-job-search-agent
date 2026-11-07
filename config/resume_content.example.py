# EXAMPLE resume content of a fictional candidate (Alex Rivera) — copy to config/resume_content.py and replace every
# entry with your own, approved wording (JSA-077). One dict per target role in ROLES; the builders
# (skills/resume-updater/scripts/build_a.py, ds_materials.py) read it through skills/resume-updater/scripts/content.py.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import jsa_profile as _P  # noqa: E402
NAME = _P.get("name.full")
FILE_PREFIX = _P.get("name.file_prefix") or "Candidate"
CONTACT = " | ".join(x for x in (_P.get("contact.city_state"), _P.get("contact.phone"), _P.get("contact.email"),
                                 _P.get("contact.linkedin"), _P.get("contact.website")) if x)
# bullet-bank section code per experience / project (ds_materials.py)
BANK_SECTIONS = {"Acme Analytics": "AA", "Sales Forecast Dashboard": "SF", "Data Club": "DC"}
ORG_KEY = {"Acme Analytics": "AA", "Sales Forecast Dashboard": "SF"}

EDU = [
    dict(school="Example State University", loc="Springfield, IL",
         degree="M.S. in Data Science", detail="", date="Expected Dec 2027",
         courses="Data Engineering, Machine Learning"),
    dict(school="Sample College", loc="Springfield, IL",
         degree="B.S. in Statistics", detail=" | GPA: 3.60/4.0", date="May 2026",
         courses="Probability, Regression, Databases"),
]

LEAD = dict(org="Data Club", title="President", date="Sep 2023 – May 2025",
    bullets_full=["Organized monthly data workshops for 40+ members."],
    bullets_short=["Organized monthly data workshops for 40+ members."])

ROLES = {}
ROLES["Data_Analyst"] = dict(
    label="Data Analyst",
    summary=("M.S. Data Science student at Example State University (Dec 2027) who turns raw data into clear weekly reports. "
             "Seeking 2027 Data Analyst internships."),
    skills=[
        ("Programming", "Python (pandas), SQL"),
        ("Tools", "Excel, Tableau, Git"),
    ],
    projects=[
        dict(title="Sales Forecast Dashboard", tag="Course project", date="May 2026", bullets=[
            "Built a Tableau dashboard forecasting monthly sales for a fictional retailer from three years of data.",
        ]),
    ],
    exp=[
        dict(org="Acme Analytics", title="Data Analyst Intern", date="Jun 2025 – Aug 2025", bullets=[
            "Automated a weekly SQL sales report, saving the team two hours per week.",
            "Added a Python data-quality check that flags missing values before each report run.",
        ]),
    ],
)
