A JSON array of 16 cases: {"name": str, "html": "<a small HTML document with one <form>>", "plan": [{"key": str, "sel": "#..."}], "expect": [ids]}.
Cover: a required file upload with "*" in its label div not in the plan (reported), the resume upload in the plan (not
reported), an optional file upload (no star / "required" word → not reported), required text inputs covered / not
covered, key prefix matches (question_1_text covered by key question_1), disabled and hidden inputs, controls outside the
form, ids starting with country / react-select / iti, aria-required.
