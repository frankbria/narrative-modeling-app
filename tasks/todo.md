# Issue #718: the AI summary's masked frame leaks a silhouette of each value

## Problem
`_summary_frame` masks the frame bound for OpenAI with the storage masks. Those keep
part of the value on purpose, for a user who wants the stored copy readable:
`_mask_generic` keeps the first and last character and the length (`"J******e"`),
`_mask_sensitive` the last four digits of an SSN or card, `_mask_email` the first
character and the domain, `_mask_phone` the area code and last two digits. The issue
names the first; the summary path has all four.

## Plan
- [ ] RED: tests in `tests/test_api/test_ai_summary_safe.py` and one assertion in the
      `/upload/secure` payload test.
- [ ] `_summary_frame` replaces every flagged column's values with numbered tokens
      (`[redacted 1]`, `[redacted 2]`, …). Distinct values stay distinct and missing ones
      stay missing, so the summary's counts for the column remain true; nothing of a
      value's length or characters is left.
- [ ] `mask_pii` loses `min_confidence`, which only the summary passed. Its body is cc 7,
      so the edit is also a split (a mask-per-type lookup).
- [ ] CLAUDE.md (the #490/#679 paragraph), gate, review, demo, PR.
