# role_category(title): which kind of role a job title is (scoring v2, Joey's categories)

Matching is on the title only, case-insensitive, whole words. The first rule that applies wins:
1. ai_pm — the title has a PM word AND an AI word.
2. data_analysis — the title has a strong analysis word (data analyst, business analyst, business intelligence, BI analyst /
   developer / engineer, Power BI, Tableau, reporting / insights / marketing / operations / strategy / product / growth
   analyst, product analytics, analytics intern); OR it has "analytics" / "data analytics" / "business analytics" /
   "data visualization" and no engineering word (engineer, software engineer, developer, SDE, SWE).
3. pm — a PM word: product manager, product management, APM, associate product manager, product owner, product intern,
   product strategy, product operations, product ops, product solutions, (technical) program manager / management.
4. AI word present (AI, machine learning, ML, LLM, GenAI, generative, agent(s), agentic, NLP, deep learning, computer
   vision, applied AI, MLOps, foundation model, applied scientist):
   - ai_engineering if the title has an engineering word: engineer, engineering, developer, SDE, SWE, software, scientist,
     research, researcher, machine learning, ML, NLP, deep learning, computer vision, MLOps, "center of excellence",
     architect, architecture, VLSI, CAD, firmware, hardware, embedded, silicon, chip;
   - otherwise ai_nonengineering (a generic "AI Intern", AI strategy, AI analyst, AI operations, AI marketing…).
5. data — data science / scientist, data engineer(ing), analytics engineer, "data" (but not "data center"), quantitative,
   quant, statistics / statistical, decision science, ETL, database.
6. other — none of the above.
