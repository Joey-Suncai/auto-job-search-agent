# sf_route(url) -> bool
True when the URL is a SuccessFactors career-site job page: it has "ats=successfactors" as a query parameter, or the host
contains ".successfactors.com"/".successfactors.eu", or "career<digits>.sapsf.", or it is "jobs.sap.com/job/…", or the path is
"/job/<slug>/<7+ digits>" (optionally "/" then end / "?" / "#") — BUT never for job boards whose links look alike:
builtin.com, linkedin.com, indeed.com, glassdoor.* (case-insensitive) → False for those even when the path matches.
