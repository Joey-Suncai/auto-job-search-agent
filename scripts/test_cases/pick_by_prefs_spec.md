# pick_by_prefs(options, prefs)

A Workday form has a "Field of Study" picker with a long list of options. The candidate's preferences are an ordered
list, e.g. ["Data Science", "Applied Data Science", "Data Analytics", "Computer Science", "Information Systems",
"Applied Statistics", "Statistics"]. The function picks exactly one option from the list, or None.

Rules (comparison is case-insensitive and ignores repeated spaces and a trailing period):
1. Go through the preferences in order. The FIRST preference that matches any option decides; a later preference may
   never win while an earlier one matches something.
2. For one preference, try in this order:
   a. an option equal to the preference;
   b. an option that contains the preference as a substring ("Computer Science" matches "Computer Science and Engineering");
      also an option whose own text is contained in the preference, but ONLY when that option has at least two words
      after removing the words and/of/the/a/an/or/in/for ("Data Analytics" matches the preference "Data Analytics and
      Visualization"); a one-word option such as "Science", "Data" or "Analytics" never matches this way;
   c. an option that contains every word of the preference (ignoring and/of/the/a/an/or/in/for): "Computer Science"
      matches "Computer and Information Science"; "Information Systems" matches "Management Information Systems".
   Within one step, the first option in list order wins.
3. Preferences shorter than 4 characters only use step a. The preference "Other" (and empty strings) are ignored.
4. Nothing matches → None.

Return the chosen option exactly as written in the list.
