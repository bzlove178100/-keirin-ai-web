# note integration checkpoint

The user requested note integration alongside work that can proceed while a
data-provider reply is pending. This document separates the current Work browser
from the standalone agent. It is not an activation receipt.

## Observed in the Work browser, 2026-10-07

Update 2026-10-08: the authenticated note home loaded with the existing account
without another sign-in. Its visible new-post link again opened the editor, which
still displayed only a loading indicator. No additional reload/sign-in loop,
draft creation, save or publication was attempted. Console observations did not
identify the cause. This confirms another observed session reuse, not recovery
from explicit expiry. A focused search of the connected inquiry mailbox found no
matching provider reply; this is not proof that no reply exists outside that search.
Private observation and search-scope receipts are stored separately.

- Google sign-in reached the authenticated creator-contact form. A previously
  authorized inquiry was sent and the page displayed its completion message.
- A later fresh tab retained authenticated access to that form. This verifies
  reuse in the same browser session, not expiry recovery or unattended operation.
- The new-article route redirected to `https://editor.note.com/new` but remained
  on a loading indicator. One reload did not expose editor controls. No draft
  was entered or saved and no article was published. The cause is unknown;
  this is not proof of bot detection or a note-wide outage.
- The earlier signup error's cause remains unknown. Successful later sign-in
  does not establish why account creation failed in that browser.

Private receipts/screenshots belong outside this repository. Do not paste
account details, draft contents, credentials or authentication URLs into git.

## Existing-draft adapter

`agent_core.note_drafts.NoteDraftAdapter` declares `note.read_draft` and
`note.update_draft` with separate permissions. It is unbound by default. It has
no create-account, create-article, publish, message-send, purchase or login action.
Do not register it as a live connection without an authorized host backend.

The host implements `read_persisted_draft(url)` and
`update_existing_draft(url, title, body, expected_content_sha256)`:

1. Authenticate through the host's secure user-mediated authentication surface.
   A generic sign-in failure stops the flow; do not retry without changed
   conditions and a concrete hypothesis. No passwords/cookies enter task args.
2. Read the exact existing private draft and verify the signed-in account. Return
   `url`, `account_id`, `status: "draft"`, `persisted: true`, `title` and `body`.
   `persisted` must describe content read after reopening, not an editor buffer.
3. Before changing anything, compare the existing title/body digest against the
   expected digest. Enforce this check immediately before editing; a concurrent
   or uncertain change must stop, not overwrite the user's work.
4. Save only the existing draft. Reopen it and independently read persisted
   title/body and private status. The adapter verifies exact content equality.
5. If a save or readback fails, keep the outcome unresolved. The adapter turns
   provider exceptions into fixed blocked classifications; even a mistakenly
   retry-safe runner step cannot automatically repeat an uncertain save.

Already matching content produces a verified no-write receipt. Provider text,
extra response fields and exception messages are not copied into activity state.
The host remains responsible for permissions and trusted UI observations. Unit
tests use a synthetic backend and do not prove a real browser implementation.

## Remaining before standalone use

- Resolve the observed editor loading failure using new evidence. Do not restart
  Google authentication merely because the authenticated editor is unavailable.
- Complete a private save/reopen check in the actual UI, then bind a supported
  host browser transport and repeat the same task through the standalone runner.
- Test explicit auth expiry, interruption and reconciliation without duplicate
  side effects. No autonomous scheduler or production runtime is enabled here.

Official reference checked on 2026-10-07: note says it has no officially public
API, with no announced release plan. This adapter does not call private endpoints.
https://www.help-note.com/hc/ja/articles/46643492548121
