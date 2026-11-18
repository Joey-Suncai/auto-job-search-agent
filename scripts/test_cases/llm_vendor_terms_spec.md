# LLM vendor terms are separate keywords (JSA-278)

The role library's lexicon (competency "agents") has two keyword groups for LLM products, matched case-insensitively on
word boundaries in a job description:
- group "Claude": spellings Claude, Anthropic.
- group "ChatGPT": spellings ChatGPT, OpenAI, GPT.
`vendor_hits(text)` returns the sorted list of these two groups' canonical terms ("ChatGPT", "Claude") that match the text.
A text that names only OpenAI / GPT / ChatGPT (e.g. "experience with the OpenAI API", "GPT-4 prompts", "ChatGPT plugins")
hits "ChatGPT" only — never "Claude". A text naming Claude or Anthropic hits "Claude" only ("Claude Code", "Anthropic's API").
A text naming both hits both. Other model names (Gemini, Llama, Mistral, "LLM", "generative AI") hit neither. A word
boundary is required: "GPTs" does not match GPT (a letter follows), "OpenAIs" does not match, "claudeish" does not match;
"GPT-4" matches (a hyphen is a boundary); "Claude's" matches; "OpenAI/Anthropic" matches both ("/" directly before a term
blocks a match, e.g. "x/Claude" does not match Claude, but "OpenAI/Anthropic" — the "/" sits before Anthropic — does NOT
match Anthropic either, only OpenAI).
