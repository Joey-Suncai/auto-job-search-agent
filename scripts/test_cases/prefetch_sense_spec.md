# Prefetch: two wordings share one saved answer only when they ask the same thing (JSA-281)

The morning prefetch groups form questions that different companies word differently, so the candidate answers each
group once and the answer is saved for every wording in it. A language model proposes the groups. Before a group is
used, wordings in it are split apart when they differ in what decides the answer. Two wordings stay together ("same")
only when they agree on every one of these:
- when the education is meant: AFTER graduation ("once you've graduated", "upon graduation", "expected degree", "will
  have / hold / earn"), NOW ("currently pursuing / enrolled", "pursuing", "in progress"), or COMPLETED ("highest",
  "completed", "attained", "earned", "obtained") — each of these three is a separate mark; a wording may carry several;
- whether it names a bachelor's / undergraduate degree; whether it names a master's / graduate degree / PhD;
- whether it is about a second / secondary / double major or a minor;
- whether it is about a crime (convicted, felony, criminal record, pleaded guilty);
- whether it is about authorization for any / all employers or without restriction;
- whether it is a yes/no question (starts with are / is / do / does / did / will / would / can / could / have / has /
  had / were / was) or an open one (what / which / please …).
Capitals, punctuation, curly vs straight apostrophes and other words do not matter.
