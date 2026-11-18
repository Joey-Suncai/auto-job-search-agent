A JSON array of 30 cases of three kinds.
Kind 1: {"name": "<unique snake_case>", "fn": "norm_step", "value": <string or null>, "expect": "<string>"}.
Kind 2: {"name": "...", "fn": "checkpoint_update", "cp": <dict or null>, "step": "<name>", "at": "<ISO>", "expect": {"done": [...], "at": "<ISO>"}}.
Kind 3: {"name": "...", "fn": "resume_target", "done": [...], "bar": [...], "expect": "<bar entry>" | null}.
Make 8 of kind 1, 8 of kind 2, 14 of kind 3. Use the real Workday bars: ["My Information", "My Experience", "Application Questions", "Voluntary Disclosures", "Self Identify", "Review"], ["Create Account/Sign In", "My Information", "My Experience", "Application Questions", "Review"], and screen-reader forms like "current step 3 of 6 Application Questions". Cover: the Vanguard stop (My Information and My Experience saved → target Application Questions), nothing saved → null, everything saved → null, sign-in steps skipped, case and spacing differences, duplicates, input not mutated.
