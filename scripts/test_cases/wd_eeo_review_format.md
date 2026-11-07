Return {"cases": [...]}. Each case:
{"name": "unique_snake_case",
 "review_text": "the Review page text with \n line breaks (several questions per case is good; include ordinary answered questions too)",
 "free_text_labels": ["labels recorded as free-text boxes", ...],
 "expect": ["label returned", ...],   // [] when nothing blocks; labels without the trailing *, whitespace collapsed, page order
 "spec": "quoted spec sentence"}
