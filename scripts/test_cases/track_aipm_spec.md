# complete_jobs.track_of(title) — the AI Product Manager track (2026-11-03)

track_of lower-cases the title and returns the FIRST track (in this order) whose pattern matches anywhere in it, else
"Other". Words are whole words (\b boundaries).

1. "AI Product Manager": the title contains BOTH an AI word — ai, a.i., artificial intelligence, machine learning, ml,
   llm, genai, gen ai, generative, agent, agents, agentic, conversational — AND a PM word — product manager / product
   management / product managers (any word starting with "product manag"), product owner, apm, associate product,
   product lead, product intern, product strategy.
2. "AI Agentic Eng": ai, a.i., artificial intelligence, machine learning, ml, llm, genai, gen ai, generative, agent,
   agentic, nlp, deep learning, applied scien…, research engineer, ai/ml, computer vision, mlops.
3. "Data Engineer": data engineer(ing), analytics engineer, data platform, data infrastructure, etl, data pipeline,
   big data, data warehouse, database, data ops, dataops, data architect.
4. "Data Analyst": data analyst(s), data analytics, business analyst(s), business analytics, bi analyst, business
   intelligence, reporting analyst, insights analyst, marketing analyst, operations analyst, …
5. "Product Manager": product manager, product management, apm, associate product, product analyst, product owner,
   product operations, product strategy, technical program, program manager, product designer, product intern, product.
6. "Data Sci / Analytics": data scien…, data analy…, analytics, quantitative, quant, insights, statistic…, operations
   research, economist, research analyst, data intern, data.
