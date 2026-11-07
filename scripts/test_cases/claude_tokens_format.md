Return a JSON array of test cases. Each case:
{"name": "unique_snake_case", "msgs": [...], "results": [...],
 "expect": {"workday": {"submitted": 1, "direct_median": [100, 10], "direct_sum": [100, 10], "overhead": [0, 0], "all_in_per_app": [100, 10]}, "_unallocated": [0, 0]}}
Only list the platforms that appear in results, plus "_unallocated". Keep numbers small and hand-checkable.
Cover: reply inside a run window; overlapping run windows (split); reply between two runs of the same folder (span);
overhead split across two platforms on one day; overhead on a day with no runs; a folder that never submitted;
even-count median; secs missing (treat as 0).
