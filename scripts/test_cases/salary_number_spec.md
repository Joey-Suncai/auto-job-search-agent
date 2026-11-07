# Salary number for a digits-only salary box

Some application forms have a salary question whose input box keeps digits only. The candidate (a full-time student,
no job right now) decided on 2026-11-01: desired pay = 25 per hour, or 52000 per year; current salary = 0.
Given the question label, return the number to type as a string, or None when the label is not a pay question.
- Mentions current / present / most recent / previous / last salary, pay, wage or compensation → "0".
- Otherwise a desired / expected / requested pay question: if it asks per hour (hour, hourly, /hr, per hr) → "25";
  anything else (annual salary, total compensation, salary range, wage/salary range, desired pay, salary requirement) → "52000".
- Not about pay (e.g. "How many hours per week can you work?", "Years of experience", "Zip code", "Phone number") → None.
