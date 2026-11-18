A JSON array of objects. Two kinds:
{"name": "<snake_case>", "fn": "is_doc_file", "path": "...", "expect": true|false}
{"name": "<snake_case>", "fn": "identity_hits", "values": {"first": "Zed", "last": "Quill", "email": "zed.quill@example.org", "phone": "555-010-9999", "full": "Zed Quill"}, "text": "...", "expect": ["first", ...]}
For identity_hits always use exactly that fictional values dict (or a subset of it); expect is the sorted list of value names found.
Write about 14 is_doc_file cases and 16 identity_hits cases. Use only made-up Zed Quill data.
