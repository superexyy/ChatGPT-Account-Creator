# CODEX TODO

## Current Blocker

- OTP mail is not being delivered at all.
- Mailcow IMAP mailbox is empty during the waiting window, so the issue is upstream of IMAP polling.
- The resend POST response body is being written to a separate debug file for deeper inspection.

## What Was Already Changed

- Converted the Node.js reference flow into a modular Python backend.
- Removed the old external account API dependency.
- Switched OTP handling to the local Mailcow IMAP mailbox.
- Moved username and password settings into `.env`.
- Removed `ACCOUNT_PASSWORD` related code.
- Simplified the CLI flow.
- Changed output storage to save email only instead of `email\tname`.
- Removed banner text, separators, and special Unicode symbols from CLI output.
- Added continuous log creation on startup and reset the previous log file on each run.
- Increased logging detail around OTP polling and IMAP inspection.
- Added separate IMAP raw email dumps at `logs/latest-imap.eml`.
- Added separate resend POST analysis output at `logs/resend-post.log`.
- Included the currently processed email in the job progress view.

## Notes For The Next Retry

- Inspect `logs/resend-post.log` for resend response details.
- Inspect `logs/latest-imap.eml` only if a message actually reaches the mailbox later.
- Keep main job logs clean; deep analysis data should remain in the separate debug files.
