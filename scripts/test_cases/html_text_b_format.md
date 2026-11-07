A JSON array of 14 cases: {"name": str, "html": "<html mail>", "expect": "<code>" or null}.
Test only the trigger words added on 2026-11-05 and how they interact with the rest of the spec: "passcode" (e.g.
"Please confirm your identity using the one-time passcode: 710027"), "pass code", "one-time password", "one time
password", "OTP", their upper / mixed case; a trigger inside a longer word does NOT count because only whole words
trigger ("passcodes", "OTPs", "zipcode" do not trigger); the code more than 200 characters after the trigger; a <style>
block that mentions "passcode" before the real sentence; a mail with none of the triggers.
