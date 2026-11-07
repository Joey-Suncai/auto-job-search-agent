Return {"cases": [...]}. Each case is one application run:
{"name": "<unique short name>",
 "mode": "submit" | "dry-run",
 "already_submitted": true|false,
 "materials_ok": true|false,            // folder materials + tailored resume check passes
 "approved": true|false,                // folder is in an approved batch
 "presses_inside": true|false,          // this platform presses the button inside its own page loop
 "platform": {"status": "dry-run"|"needs-user"|"captcha"|"blocked"|"closed",   // what the page work ended with BEFORE any press
              "problems": ["..."], "unknown": ["..."],
              "fields_ok": true|false,  // every field read back correctly
              "no_fields": true|false,  // no field was read at all
              "canon_mismatch": true|false},  // a sponsorship / work-authorization field holds the wrong answer
 "press_outcome": "submitted" | "unconfirmed" | null,   // what happens if the button IS pressed
 "expect": {"results_lines": 0|1,
            "status": "<final status in the results line, or null if no line>",
            "stopped_at": "common_gate" | "platform_page" | null,
            "pressed": true|false,
            "queued": 0|1,             // queue lines for Joey
            "pushed": true|false,       // push to Joey about an unconfirmed submit
            "synced": true|false,       // tracker row written
            "form_opened": true|false},
 "spec_quote": "<sentence>", "ambiguous": false}
Notes: when platform.status is not "dry-run" the page work itself stopped (a platform problem). press_outcome only matters
when the button is pressed. Write ~30 cases covering every rule, including clean runs.
