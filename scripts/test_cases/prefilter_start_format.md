Return a JSON array of 30 cases:
{"name": "snake_case_unique", "level": "Internship" | "New grad", "text": "a sentence or two of JD text", "intern_summer": 2027, "fulltime_from": "2028-01", "expect": true | false}
Use the author's values (2027 / "2028-01") for half the cases and other candidates for the rest (e.g. intern_summer 2026 or
2028; fulltime_from "2027-06", "2027-09", "2028-05"). Include near misses on each side of every boundary.
