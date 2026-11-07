Return {"cases": [...]}. Each case: {"name": str, "fn": "pick_button", "args": [[{"id": str, "text": str}, ...]], "expect": {"id": str, "text": str} | null, "spec": "quote"}
Write 16 cases only for pick_button, centred on the new "later" exclusion: "Finish Later" before "Submit" (Submit wins), "Save and Finish Later" alone (null),
"Finish" alone (kept), "Later" inside another word ("Collateral Next" — whole word only), mixed with social buttons, Back, Next, Save & Continue, and order.
