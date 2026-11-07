# Digits to type into a Workday date box

A Workday date box is either MM/DD/YYYY (has a day part) or MM/YYYY (no day part). The function takes an answer text
and whether the box has a day part, and returns only the digits to type, in box order:
- Answer with month, day and year ("06/14/2027", "6/14/2027"): day box → MMDDYYYY ("06142027"); month-year box → MMYYYY ("062027").
- Answer with only month and year ("12/2027", "December 2027", "Dec 2027", "12-2027"): day box → the first day of the month,
  MM01YYYY ("12012027"); month-year box → MMYYYY ("122027").
- Month names (full or 3-letter, any case) become month numbers. Month and day are always two digits, year four.
