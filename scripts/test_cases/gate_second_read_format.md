Return a JSON array of 24 cases:
{"name": "snake_case_unique",
 "rule": {"v": "Ineligible" | "Review" | "Eligible" | "Closed" | "Unverified", "c": "CODE,CODE"},
 "ds": null | {"eligible": "yes" | "no" | "unclear" | "maybe"},
 "expect": {"v": "<verdict after the second read>", "ds_code": true | false, "ds_attached": true | false}}
ds null = DeepSeek gave no answer. ds_code = DS_SECOND_READ is in the resulting codes.
Cover: each soft code alone and in combinations, soft + hard mixes, soft with plus/review codes, review rows, eligible /
closed / unverified rows, not-read codes, missing and invalid answers.
