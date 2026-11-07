# is_non_us(location) — is a job posting's location clearly outside the United States?

Returns true only when the location is clearly outside the U.S.; false otherwise (including empty, "Remote", or places it cannot tell).

1. A location string may list several places, separated by ";", "|", "/" (without a following space), a line break, "•",
   two or more spaces, " or ", " and ". Each place is judged on its own.
2. A place is U.S. when it names "United States" / "USA" / "U.S." / "US", a U.S. state (full name, e.g. "Texas", or a
   two-letter state code after a comma, e.g. "Austin, TX"), or a major U.S. city (New York, Chicago, Seattle, SF, Bay Area …).
3. A place is foreign when it names a foreign country (any country — e.g. New Zealand, Canada, Mexico, Vietnam, South Africa,
   Peru), a foreign city (e.g. Auckland, Toronto, Bangalore, Berlin, Kuala Lumpur, São Paulo, Ho Chi Minh City), a Canadian
   province, or a region outside the U.S. (Europe, EMEA, APAC, LATAM, Asia, Middle East).
4. A two-letter code that is also a U.S. state code does not make an unambiguous foreign city U.S.: "Bangalore, IN",
   "Toronto, CA", "Berlin, DE" are foreign.
5. City names that also exist in the U.S. (London, Paris, Dublin, Vancouver, Melbourne, Rome, Athens, Lima, Geneva, Vienna,
   Warsaw, Ontario, Brisbane, Moscow …) are U.S. when the same place carries a U.S. state ("Dublin, CA", "Paris, TX",
   "Vancouver, WA", "Vienna, VA", "Moscow, Idaho"); without one ("London", "Dublin, Ireland", "Vancouver, BC") they are foreign.
6. "New Mexico" and "New England" are U.S., not Mexico / England.
7. The whole location is non-U.S. (true) only when at least one place is foreign and no place is U.S.
   "New York, NY; London, UK" → false. "London; Hybrid" → true. "Remote - Canada" → true. "Remote" → false.
   "Remote, Americas" → false (cannot tell). Anywhere in the string "United States" / "USA" / "U.S." / "Remote US" → false.
