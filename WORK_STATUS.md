# Work status

## Disqualified crossing intake — 2026-10-09

PR #225 is merged at 62008f14da9a39552548421b027bf1379253dcc7; all six
main-push CI workflows succeeded. The private noon result checkpoint found
three complete result captures: two joined, one blocked by unclassified
disqualification. No fresh source request was needed to diagnose it.

The importer now recognizes exact disqualification with explicit valid crossing
order as a starter, separately from an awarded finish and retirement. Missing
evidence and contradictory rank/withdrawal/retirement remain blocked. The
original crossing value and raw blocks are retained; no rank is fabricated.

Validation: 150 historical tests plus 25 shared preparation tests pass. Saved
12 historical results/four-pair bridge and 12 pre-race cards replay unchanged.
The three noon result pairs now join against their immutable pre-race cards;
technical review covers 27 riders, while preparation excludes all three for
unconfirmed source use and missing source-use evidence. Training stays zero.
Prior observations/quarantine receipts remain unchanged; new derived records
have new hashes and reviews. Private evidence contains exact source receipts.

This checkpoint precedes PR CI/merge. Production, DB writes, continuous external
collection, learning and hosted execution remain OFF. Follow later results
against saved pre cards; await provider replies. Unknown DQ variants, broader
coverage, evaluation periods, note access and suspend-expiry gap remain open.

## Official JSON result capture bridge — 2026-10-09

PR #224 is merged at 293f1aced5b5c68821f5c62fcb986adac1365969; all five
main-push workflows succeeded. No open PRs were present on resume.

Fresh result/card HTML requests returned HTTP 500/EC0500E, while the public
schedule and page JavaScript remained readable. The schedule selection token
was unchanged. Inspection of the page's own controllers established its GET
JSJ001 header / JSJ012 result route. Both returned HTTP 200. The HTML failure's
server-side cause is unknown; no claim of repair, login or access bypass.

Added offline paired-JSON intake with independent byte/receipt checks, closed
request types/endpoint/query, equal selection tokens, header/scope matching,
chronology and publication checks. Normalization and pre-race joining reuse
existing HTML roster/status/tie/payout and review boundaries. Raw JSON blocks,
original capture hashes and scoped receipts are retained; no HTML is fabricated.
The composite source hash is explicitly labeled. See HISTORICAL_OFFICIAL_DETAIL.md.

Validation: 11 JSON tests, 133 existing historical tests and 25 agent preparation
tests pass. Saved 12-race HTML observations and the four-pair bridge are unchanged.
The first live 1R JSON capture was unpublished; the next contained payouts but
no finish rows and was correctly rejected as result_not_published. Private
receipts retain those changing states. Later capture outcomes belong in the
private follow-up receipt, not an assumed result at this commit checkpoint.

PR/CI/merge remain pending at this source checkpoint. Production, DB writes,
automatic collection, learning and hosted execution remain OFF. No approval or
training follows merely from obtaining official JSON. Source replies, continuous
coverage, note access and BLOCKED_SUSPEND_EXPIRY_GAP remain unresolved.

## Shared preparation stage accounting — 2026-10-09

PR #223 is merged at d7b03860c59fc0b97d8929b61a146241d5707624; all six
independent main-push workflows succeeded. No open PRs were present on resume.

Preparation receipts previously showed only records that reached preparation,
so upstream exclusions were invisible. The shared adapter now derives stage
entry counts from hash-checked arrays and reports converted, quarantined,
detail-quarantined and orphan entries separately from partitioned/excluded
preparation records. Missing optional arrays remain unknown; malformed arrays
block. Producer summary counters are not authoritative, overlapping stages are
not summed into a unique-race total, and private identifiers/reasons stay out of
receipt/activity data. Blocked runs do not claim completed accounting.

Persisted preparation bytes and task fingerprints are unchanged. A completed
resume returns counts without repeating the action or rewriting the report.
25 preparation tests and 133 historical tests pass. Saved four-pair evidence
produced three converted / one upstream quarantine / three preparation-excluded
/ zero partitioned records; a second invocation executed no action and preserved
the output bytes and modification time. The diagnostic used empty reviews and
existing diagnostic split dates; no evaluation period or approval was adopted.

PR/CI/merge are pending at this source checkpoint; consult the PR and private
receipt for final status. No new races or real training. Source replies, later
results, continuous coverage, note access and BLOCKED_SUSPEND_EXPIRY_GAP remain
unresolved. Production, DB writes, collection, learning and hosted execution OFF.

## Result-state consistency — 2026-10-09

PR #222 is merged at dca016068932d00bc6edd9c25c9f3d9d6e45bfcd; all six
independent main-push workflows succeeded. No open PRs were present on resume.

The detail importer accepted a finish rank together with an explicit retirement,
and accepted withdrawal and retirement on the same row. Such contradictions
could supply a confirmed starter count; ranked retirement could reach the
unapproved single-label review bridge. Blank status objects also concealed an
unclassified missing rank. Six synthetic tests reproduced 12 failing subcases.

The importer now flags those contradictions, leaves the confirmed starter count
unknown, and retains original fields. The bridge quarantines contradictory
captures via its existing issue gate. Ranked blank placeholders and separate
unranked withdrawals/retirements stay valid; unknown statuses are not interpreted.

Validation: 133 historical tests and 19 agent preparation tests pass. The saved
12-result replay, four-pair bridge and separate venue reconciliation are unchanged.
No new races, source approvals or real training resulted. PR/CI/merge are pending
at this source checkpoint; consult the PR and private receipt for final status.
Source replies, later results, continuous coverage, multilabel learning, note
access and BLOCKED_SUSPEND_EXPIRY_GAP remain separate unresolved work. Production,
DB writes, automatic collection, learning and hosted execution remain OFF.

## Tied finish/payout consistency — 2026-10-09

PR #220 is merged at ec63bc6ba7a88af53752eba82890786bf109a070; all five
independent main-push workflows succeeded. The pending checkpoint below is
superseded. There were no open PRs when this increment began.

Review found that the detail importer bypassed finish/payout reconciliation
whenever any repeated rank existed. Consistent prefixes across the two payout
tables alone could admit missing tied combinations, incorrect third-place cars,
or a wrong winner when a tie existed only below third place. Synthetic cases
reproduced nine failing assertions before the fix.

The importer now checks both ordered payout sets against bounded prefixes of
all observed competition-rank groups. Missing/extra/wrong combinations and
nonstandard rank gaps are flagged while retaining raw evidence. No payout amount
or training label is invented. See HISTORICAL_OFFICIAL_DETAIL.md for limits.

Local validation: 127 historical tests and 19 shared preparation tests passed.
The saved 12-race detailed-result replay, four-pair bridge and separate venue
reconciliation remain identical to the saved outputs; original bytes were not
changed. The bridge still has three unapproved records and one tied quarantine.
This is improved validation of existing observations, not new races or training.

This commit checkpoint precedes its PR/CI/merge; the PR and private receipt hold
final status. Source-use replies, continuous coverage, multilabel learning,
note editor access and BLOCKED_SUSPEND_EXPIRY_GAP remain unresolved. Production,
DB writes, hosted execution, automatic collection and learning remain OFF.

## Repeated interruption recovery follow-up — 2026-10-09

Verified base: PR #219 merged at 5aa4de7001108ef8c4f360328771a0908434f9e0.
All five PR and independent main workflows passed, including 28 regression jobs
on each side. This supersedes the pending CI checkpoint below.

Replayed the separately saved follow-up against current main. Its expanded tests
reproduced the second-interruption failure and acceptance of malformed attempt
counts before the fix (19 tests: four failures and two errors, including subcases).
The follow-up accepts only the launcher's exact saved reconciliation in pending
or running state, checks original report bytes again, and completes without a
new action or reconciliation. It rejects malformed attempt counts before the
legacy decoder can coerce them. Ordinary shared-runner decoding is unchanged.

After applying the saved implementation, all 19 preparation tests and eight
shared-core tests passed. Cases cover repeated interruption, output corruption,
missing/unrelated reconciliation, duplicate records, invalid counts and action
non-replay. This is scoped local recovery verification, not host qualification
or live training. Private reports and evidence remain outside this repository.

The earlier push-authorization blocker was resolved by the user's instruction;
GitHub connector delivery is used because terminal git push has no credentials.
CI/merge for this follow-up is pending at this commit checkpoint; consult its PR
and private receipt for the final result. Source-use replies, note editor access
and BLOCKED_SUSPEND_EXPIRY_GAP remain separate unresolved work. Production, DB
writes, hosted execution, autonomous collection and learning remain OFF.

## Verified local preparation recovery — 2026-10-09

Verified base: main 13940dcd7f689be501e78697d821997d95daea21 (PR #218).
A saved preparation report could survive interruption before its artifact/state
commit, leaving explicit reconciliation to a manual caller. The new opt-in
`--reconcile-verified-output` checks the exact task fingerprint, original input
hashes, chronology boundaries, sole interrupted step and recomputed report bytes
under the task lock, then restores the artifact record without rerunning the
preparation action. Default resume still blocks ambiguous interruption. Missing,
changed, symlink or unrelated failure evidence remains blocked. See
HISTORICAL_AGENT_PREPARATION.md for scope and caller storage assumptions.

Local tests: 15 preparation tests (five added recovery cases with rejection
subcases) and eight shared-core tests passed. A separate private diagnostic run
using the existing three technically reviewed records was intentionally stopped
after report creation. Ordinary resume blocked; CLI explicit recovery and its
repeat both completed with zero action replays and unchanged output bytes/mtime.
Original inputs and original completed run were preserved. All three remain
excluded for source-use evidence; real training is still zero. No new races.

A scoped mailbox search now succeeded and returned the note acknowledgement only;
no substantive reply was found in that query. This does not prove absence across
all mail. Three inquiries have been sent, including the official data-use contact;
no source-use permission is established. Private correspondence stays outside git.

This change does not resolve note editor loading or BLOCKED_SUSPEND_EXPIRY_GAP.
The latter still needs a suspend-inclusive kernel deadline or closed boundary;
ordinary userspace recovery cannot establish packet revocation during resume.
No unchanged host experiment was retried. Hosted execution, production prediction,
DB writes, automatic collection and learning remain OFF. Remote CI and merge are
pending at this commit checkpoint; consult this change's PR for their final state.
Next: qualify host suspend boundary separately, diagnose note using new support
evidence, join later results to immutable pre-race captures and resolve source-use.

## Nine-rider pre-race intake and scoped technical review — 2026-10-08

PR #217 is merged at 23bf9689bcbe7d053c813b057c73b35a011863e7.
Its six main workflows and 28 regression jobs passed. This supersedes the
pending checkpoint below; the private receipt preserves exact run identities.

A bounded next-day capture saved all 12 Yahiko races for 2026-10-09 before
start: 108 listed rider rows, all nine-rider fields. Each page passed the existing
strict capture/date/venue/race/roster checks. One pre-race roster contains an
additional-entry note, retained for later result reconciliation. Results are
not available in these pre-race captures. Unique observed races increase from
329 to 341; these are observations, not approved training examples or predictions.

The prior navigation mismatch is explained by the official page handlers:
the promotion's prmEnc is used by its result button, whereas its next-day
vote button uses venue/date. Do not treat that result token as a next-day card
link. The working read-only route is tomorrow's JSJ057 schedule followed by
its venue encPrm and returned per-race encParaR values. No login or vote action
was performed. Validate actual page identity after every navigation. This fixes
the operator's route selection; it does not claim a server-side repair.

Three existing pre/result records (20 active rows) received a scoped technical
review against exact saved bytes: capture chronology, identity, roster notes,
style and score mappings. The reviewed derivatives preserve the original hashes;
unknown S/H/B windows remain unmapped. Two additional entrants were already on
the saved pre-race roster; one withdrawal was known before start and confirmed
in the result. No source-use approval was created. Shared-agent preparation
now excludes these three only for unconfirmed training use / missing source-use
evidence, with zero learning runs. Completed resume executes no steps and checks
the saved report again. Continuous train/validation/test coverage is still absent;
removing record-level blockers alone would not establish adequate evaluation.

This increment changes handoff documentation only; application code and production,
DB, autonomous collection/learning and hosted gates remain unchanged/OFF. Private
captures, reviews, source references and replay scripts are saved separately.
CI/merge for this documentation checkpoint is pending here; consult its PR and
private receipt for final status. Next: preserve new pre-race originals, join later
results without changing features, resolve source-use scope, and extend continuous
coverage. note and BLOCKED_SUSPEND_EXPIRY_GAP remain unresolved; no unchanged retries.

## Completed venue results and pre/result review bridge — 2026-10-08

Verified base: PR #216 is merged at 344c5fb3ed6ff14a51b528cf8aa07f606ed1d047.
Its private receipt records all six main workflows and 28 regression jobs
successful; the remote main ref and merged PR were checked again this session.
This supersedes its pending checkpoint below.

New private captures at 22:00–22:02 JST fill 8–12R. All 12 detailed results
(84 listed rows, 82 confirmed starters, 80 ranked finishers) match the separate
venue payout list and the original paper identities. Earlier 1–7R payouts are
unchanged. 10R has two first-place finishers and two ordered outcomes; both are
retained. 12R confirms the withdrawal seen on the saved pre-race card. This adds
five detailed results to existing races, not five new unique observations;
cumulative unique observations remain 329.

`ml.historical_official_records` replays saved pre/result HTML and receipts,
checks cross-capture identity and every observed start, and emits hash-bound
historical review records accepted by the shared preparation runner. Only
observed style/score are mapped; unknown metric windows stay raw. A pre-known
withdrawal can be excluded from the candidate population without altering the
source; a later-only withdrawal, unknown classification or tied rank blocks the
single-label bridge. Private raw results, including all tied payouts, are retained.
See HISTORICAL_OFFICIAL_RECORDS.md.

Four saved pre-race cards produced three unapproved records (20 active rows),
with 10R quarantined for the separate multilabel contract. These are an alternate
representation of the same races; do not concatenate them with earlier paper
candidates as additional independent examples. Shared-agent preparation excludes
all three: source-use/definition/roster and final-record reviews are outstanding.
There are zero real training runs. Fixed, continuous evaluation data are still
needed. Historical tests: 120 passed, including 14 new bridge tests; shared-agent
preparation tests: 10 passed. This increment's remote CI/merge is pending at this
commit checkpoint; consult the PR and private implementation receipt.

The reply search failed with Gmail RATE_LIMIT_EXCEEDED/PERMISSION_DENIED. This
is not evidence of no reply. Do not repeat the unchanged request or send a new
inquiry. note editor access and BLOCKED_SUSPEND_EXPIRY_GAP remain unresolved and
were not retested here. Production, application DB writes, scheduled collection,
autonomous learning and hosted activation remain OFF. Next: resolve source-use
and feature definitions, review exact records, extend dated coverage and add a
proper multilabel contract while preserving the general-agent/note work.

## Official detailed intake and working access route — 2026-10-08

Verified base: PR #215 merge 87dfca07ff9a9562c297d4862b5cb8bf2f5e7719,
with all six PR workflows, all six main-push workflows and 28 regression jobs
in each successful. This supersedes its earlier pending checkpoint below.

The private venue-list capture at 18:31:58 JST joins 1–7R ordered results;
the preceding five values are unchanged. A later official top-page route
returned detailed pages with HTTP 200, using the same public race tokens that
had previously failed. The earlier EC0500E server-side cause remains unknown;
working access at this observation time is not a permanent service repair.

New offline `ml.historical_official_detail` retains entire header/card/result
blocks, pins capture bytes and identity, reconciles rider IDs, rejects late
pre-race captures, and preserves non-finishers and partial refunds. It supports
3–9 listed riders and separates listed riders, finishers and confirmed starters.
No unknown metric windows are silently mapped into training features.
See HISTORICAL_OFFICIAL_DETAIL.md.

Privately saved: seven detailed results (49 listed rows), plus four pre-race
cards for 9–12R (28 rows, all before listed starts). 1R includes a withdrawal
and partial refund; 2R includes a fall retirement; 12R's new pre-race card
includes a withdrawal. Earlier paper bytes remain unchanged. Later observations
must not be used to rewrite what was known at the earlier paper capture time.
These enrich existing races; cumulative unique observations remain 329.

Local historical tests: 106 passed including 15 new detail tests; shared-agent
historical preparation: 10 passed. This increment's remote CI/merge is pending
at this commit checkpoint; its PR and private implementation receipt carry
final status. Learning-eligible records and actual training runs remain zero.
Source-use/feature definitions, final-record reviews and continuous evaluation
coverage are unfinished. These captures are not paired prediction records.

note/provider reply search still found only note's prior acknowledgement in
its stated query scope. No new outgoing messages. The note editor issue and
BLOCKED_SUSPEND_EXPIRY_GAP are not fixed or revalidated by these data tests.
Production, application DB writes, automatic external collection and autonomous
learning remain OFF. No completion percentage or delivery date is inferred.

## Official source capture and offline result reconciliation — 2026-10-08

Verified base: PR #214 is merged at
08e3b82020e40f27d114aee37f7e53e8e814ce54. Its six independent main-push
workflows and all 28 regression jobs passed. This supersedes the pending
PR214 checkpoint below.

A separate private capture saved the current official program at 15:43:11 JST,
before the first listed start of 15:45: 12 races and 84 rider rows. Ten brief
rider-comment facts, one stated follow intention and bank dimensions were also
retained. These are pre-race source observations, not paired prediction records.
Cumulative unique observations are 329; no new races are counted by this join.

The official result list saved at 17:17:03 JST contains ordered payouts for
races 1–4 and blank cells for 5–12. The new offline importer pins source and
snapshot hashes, checks table shape/date/roster/chronology, excludes duplicate
mobile tables, preserves multiple outcomes, and quarantines ambiguous rows.
It produces separate result observations and unapproved historical review
candidates without changing the pre-race bytes. See HISTORICAL_OFFICIAL_RESULTS.md.

Applied privately: four joined summaries, eight pending at that capture time.
Existing preparation excludes all four candidates (0/0/0); full results/status,
style, source-use and final-record reviews remain incomplete. Local historical
checks: 91 passed, including 12 new tests. This increment's remote CI/merge
is pending at this checkpoint; consult its PR and private receipt for final state.

The linked KEIRIN.JP detail lookup returned HTTP 500. A separate GET reading
path returned the same status; the cause and repair are unverified. The source
list remains accessible. Do not infer full finish orders or retry unchanged
failed lookups. Next: confirm a working official detail path or subsequent
program results, reconcile result/status changes, and extend continuous input
coverage and reviewed training preparation. No background collector is running.

note's editor issue, provider inquiry and BLOCKED_SUSPEND_EXPIRY_GAP remain open.
No new messages or purchases; production, application DB writes, autonomous
learning and automatic collection remain OFF. Learning-eligible races and real
training runs remain zero. No completion percentage or delivery date inferred.

## Detailed historical intake alongside existing work — 2026-10-08

Verified base is PR #213 merge c36f9c5b5cf9f4f1938d31ce1b8543f7fd8fd151.
The user's new instruction explicitly asks for collection improvements alongside
existing work. This supersedes the earlier note-first pause for independent
collection development; it does not resolve the note failure or authorize
unbounded external collection, purchases, publication or messages.

`ml.historical_details` adds hash-pinned, lossless four-table CSV intake,
field-level coverage, duplicate/conflict handling and an explicit missing-data
backlog. It retains all 55 source column positions across the four schemas,
including unexpected columns, and connects eligible candidates to the existing
strict review converter. A separate hash-bound rate-feature bridge requires
confirmed definitions/window evidence; it never treats download time as a
historical cutoff. See HISTORICAL_DETAIL_COLLECTION.md for usage and limits.

Applied to the existing 11 files: 301 races, 6,451 unique rows, no conflicting
keys; 211 have all four tables, three of those have missing entrant cars. The
other 90 lack entrants. Converted review records remain 208. All 1,408 H cells
are blank; 90 race weather/wind values are absent in the 2026 sample. This is
more detailed organization/validation, not new external collection. Cumulative
unique observations 317; training-eligible 0; real-data training runs 0.

Local historical tests and existing shared-agent preparation tests pass.
This increment's remote PR/CI/merge is pending at this checkpoint; consult its
PR and private receipt for final status. No existing learner or production
feature contract is changed. Automatic collection, autonomous learning,
production predictions, application DB writes and hosted activation remain OFF.

note support has acknowledged an editor-loading inquiry; the root cause and
repair are unverified. Do not request repeated phone/login checks. The provider
use/time inquiry also remains awaiting a substantive reply. Keep both threads
and BLOCKED_SUSPEND_EXPIRY_GAP open. Next collection work is source/window
qualification and continuous-period acquisition, followed by reviewed features
and frozen evaluation partitions; do not report all details collected or a
completion percentage based on file/PR counts.

## Shared-agent historical preparation — 2026-10-08

PR #212 is merged at 734272e4a07c96c331cec1c3b31e995cb8e104c9,
tree 8cec984a3eb919cd52c7aa9374dddf6b06004d7a. Its six PR workflows
and six independent main-push workflows passed, with 28/28 regression jobs
on each. The previous private progress report is version 8.

The authenticated note home loaded this morning. Following its current new-post
link still left the editor on a loading indicator; no repeated login, new draft,
save or publication occurred. The cause remains unknown. Focused mailbox searches
for the provider/topic and note sender found no matching reply; do not generalize
this to all possible reply locations. Browser integration remains incomplete.

The new historical_preparation launcher connects existing reviewed-record
preparation to the shared AgentRunner and FileStateStore. It pins input hashes,
paths and explicit diagnostic boundaries, verifies persisted report bytes and
records a private activity ledger. Identical completed resumes do not repeat the
action; changed input, review, boundary, output or an interrupted attempt stops
for review. No train, fetch, DB, note write or scheduler action is exposed.
See HISTORICAL_AGENT_PREPARATION.md for usage and remaining work.

Applied to the same 208 converted records with empty reviews: the diagnostic
completed and excluded all 208, with train/validation/test 0/0/0. A second call
executed no steps and verified the same output hash. This is real-data execution
of preparation, not real-data training. Cumulative unique observations remain
317, training-eligible races 0, real training runs 0. The earlier 93 upstream
quarantines are unchanged. Private artifacts remain outside git.

Local verification: 10 new agent-preparation tests, 67 historical tests, 8 core
tests, 3 persistence-redaction tests and existing web/safety regression passed.
Current increment PR/merge/independent-main receipts must be read from its PR
and private progress record. No completion percentage or delivery date inferred.

Next: resolve note editor access using new evidence before binding a live host;
read any provider reply and attach supported use/time evidence to exact records;
review final hashes and establish continuous, fixed-period evaluation data.
BLOCKED_SUSPEND_EXPIRY_GAP remains unresolved. Production, DB writes, automatic
collection, autonomous learning and hosted runtime activation remain OFF.

## note draft adapter and historical review conversion — 2026-10-07

Current main before this increment is PR #211 merge
9ba315fa244df7352fa2a4b8e755d241cca4d8ed. All six independent main-push
workflows passed (UI 37602735819, ML 37602735943, AWS 37602735992,
PostgreSQL 37602735827, regression 37602735835 with 28/28 jobs,
runtime 37602735718). This supersedes earlier pending-PR211 receipts below.

A previously authorized provider inquiry has now been sent; the Work browser
showed completion. The reply is not yet verified. The private progress report
holds the exact message and screenshot. Earlier “unsent” statements are history.

The Work browser retained note authentication in a fresh tab. The article
editor remained on a loading indicator after one reload, so private draft
save/reopen is NOT verified. NOTE_INTEGRATION.md records this boundary.
The new NoteDraftAdapter handles existing private drafts through an injected
host backend: expected account/content, separate permissions, persisted readback,
and blocked ambiguous saves. It has no live browser backend by default and no
publication/message action. Synthetic tests are not standalone live integration.

ml.historical_records replays normalization from retained raw rows before mapping
entrant candidates to the historical training/review schema. Candidate lineage,
provider rider IDs, missing H/timestamps, DNS/DNF/DSQ, dead heat and refunds are
preserved. Final record hashes differ from upstream candidates; old reviews do
not transfer. The converter never creates use/time evidence or training approval.

Applied offline to the same 301 races: 208 converted review records (206 ordinary,
1 dead heat, 1 full refund), 93 upstream quarantines. Counts of 7/6/5 riders are
157/33/18. Existing training preparation with empty reviews excludes all 208;
train/validation/test remain 0/0/0. Diagnostic boundaries are not evaluation
partitions. Cumulative unique observations remain 317; real-data training 0.
Local tests: 67 historical tests and 8 note-adapter tests, including 17 new tests.
Current increment CI/merge receipts must be read from its PR/private progress.

Next: bind and verify a real authorized note browser backend only after editor
access works; review the provider reply; add supported source/time evidence to
converted records and review their final hashes; establish continuous coverage
and fixed chronological evaluation. General-agent BLOCKED_SUSPEND_EXPIRY_GAP
remains unresolved and was not retested. Production, DB writes, automatic
collection, autonomous learning and runtime activation remain OFF.

## Offline entrant import — 2026-10-07

This checkpoint supersedes the earlier pending-main receipt: PR #210 is merged
at 908952a046fd6c8d3b66e70ba1cf7c5d06f12847. All five applicable main-push
workflows passed: UI 37599957354, runtime 37599957359, PostgreSQL 37599957343,
AWS 37599957399, regression 37599957355 (28/28 jobs). ML was path-filtered.

`ml.historical_entrants` now imports private KeirinDB entrant CSVs into existing
payout candidates without network access. It joins exact race/car/provider ID,
cross-checks rider names and withdrawal status, retains raw rows and hashes,
and maps only Points, style, S, H and B. Blank numeric values remain missing.
It does not use current rider-master values or unreviewed aggregate-rate columns.
Missing cars are not reconstructed from results. Each changed record has a new
hash linked to its original payout candidate; old reviews cannot carry over.

Applied to the already acquired sample: 301 races, 1,408 entrant rows supplied;
208 races / 1,387 rider rows matched (2024: 96 / 659; 2025: 112 / 728).
Three races remain quarantined because withdrawn entrants have no car number;
90 races have no entrant file in the 2026 sample. All 1,387 matched H values
remain missing, while score/S/B are present. This is an input conversion result,
not a new collection count, independent source verification or training approval.
Observed matched rosters contain 5, 6 and 7 riders; synthetic coverage also
checks 3 and 9. No nine-rider real-data import is claimed in this sample.

Local historical tests: 58 passed, including 10 new entrant-import tests.
The private CLI report and evidence archive preserve reproducible inputs.
This implementation's PR/CI/merge is not complete at this document checkpoint;
read its PR and the private progress report for final receipts.

Primary provider research distinguishes a full-year KeirinDB CSV offer from
its three isolated-day free samples, a current-rider-only CSV, a third-party
Kdreams collection repository, and a vendor's betting APIs. None of these
checks established a newly qualified continuous training dataset. The private
source decision record retains URLs, missing evidence and an unsent inquiry.
No purchase or provider message was made. Next acquisition decision: confirm
historical card timing and the intended model-training use of an existing CSV
provider before paying or scaling intake; commercial use is a separate scope.

Unique historical observations remain 317; training-approved races 0;
real-data training runs 0. Feature/result-availability times are still unknown.
Conversion output still needs source/time evidence and a dedicated historical
review before training. General-agent BLOCKED_SUSPEND_EXPIRY_GAP was not
retested or resolved. Production, DB writes, automatic collection, autonomous
learning and runtime activation remain OFF. No overall percentage is asserted.

## Archived-card corroboration and source-use review — 2026-10-07

This checkpoint supersedes earlier current-status text. PR #209 is merged at
8e82619d40abcd331cef7b7e8ae9d478e66729f9, tree
ef78448fb990816fd77c4e7e371dac37f6dc2869. Five applicable PR workflows passed
(regression 28/28). Independent main-push checks also passed: AWS 37597251455,
PostgreSQL 37597251508, UI 37597251451, regression 37597251410 (28/28),
and runtime 37597251423. ML was not triggered by that documentation-only change.

Cumulative unique historical observations remain 317; this increment adds no
new races. Three archived race cards corroborate all 21 existing paper scores
and all 21 paper BK/archive B values. They also supply observed style and S
values for those 21 rows. Matching uses the same race/car plus name, age,
prefecture and term; it does not establish stable cross-race rider identities.
No stable IDs were resolved or current rider-master features imported.
Value agreement is not proof of independent upstream sources or of pre-race
publication. Feature/result-availability timestamps remain unset.

The private source-qualification report records source-specific scope:
KeirinDB explicitly describes AI-assisted analysis and prediction-logic use;
that statement is not treated as an explicit model-training, automated-fetch
or commercial-service license. Kdreams' site policy contains restrictions on
private use and unauthorized copying; its cards are not accepted as a training
source, and no further bulk collection is started. KEIRIN.JP's own policy does
not authorize another provider. Legal applicability has not been adjudicated.
No paid purchase, provider message or permission request was sent.

Existing training preparation was run on the three enriched candidates, with
no fabricated reviews: 0 train / 0 validation / 0 test; all remain excluded.
These diagnostic dates are not an adopted evaluation partition. Numeric H and
other optional fields may remain missing; stable IDs are needed specifically
for rider-history joins. Do not turn every enrichment into a universal gate.

Private artifacts: keirin_source_qualification_2026-10-07.json and
keirin_source_qualification_evidence_2026-10-07.zip. The bundle retains factual
extracts, original HTML hashes, the prior intake and an offline reconciliation
script; full archive HTML and editorial content are not bundled. The prior
paper-intake artifact remains an unchanged baseline. The progress JSON records
this new scope and final PR/CI receipts. Current documentation CI/merge is
pending here; read its PR or the private progress file for final receipts.

Next: prioritize a source that can substantiate learning-use scope and historical
input/result timing, rather than scaling a source that is not qualified. Keep
the separate general-agent work visible: BLOCKED_SUSPEND_EXPIRY_GAP was neither
retested nor resolved. No new product implementation in this increment.
Historical training-approved races 0; real-data training runs 0; accuracy and
return on stakes unmeasured. Production, DB writes, automatic collection,
autonomous learning and runtime activation remain OFF. No overall completion
percentage or deadline is established.

## Dated historical program intake — 2026-10-07

This checkpoint supersedes older current-status statements below. PR #208 is
merged at main 3d22089d2fe59b550709154cc1d3a1aac6a13b98,
tree 3e677359ffd5fd2d16453a8918301c2fe726fdfa. All six PR workflows passed;
independent main-push runs also passed: regression 37591972830 (28/28 jobs),
runtime 37591972844, PostgreSQL 37591972850, UI 37591972829,
ML 37591972919 and AWS 37591972825. Its earlier pending text is historical.

Private intake now contains 317 unique race observations: previous 314 plus
three bounded race-1 observations from the consecutive 2024-01-29/30/31 meeting.
Three dated official program PDFs (11 pages) were obtained. Only three races and
21 rider rows have been structured; untranscribed races in those PDFs are not
counted. Paper scores/BK, roster and scheduled starts were visually transcribed;
full finish orders and ordered payouts were checked against three result pages.
For two races, the next day's official program also agrees on the full order
and ordered payouts. This does not establish independent upstream data providers.
All originals, private records, SHA-256 hashes and reproduction script stay
outside this public repository.

The PDFs report creation on the preceding day, but that is not proof of public
availability before the race. HTTP modification dates postdate the meeting.
Historical feature and result-availability times remain unset. No stable rider-ID
join was inferred from names; no style/S/H was invented from results. BK is
retained literally, with its model-column mapping awaiting review. Scores/BK
were not independently checked against another archived card. Source automated,
training and commercial-use scope remains unconfirmed.

Existing offline intake and training-preparation code was run on the three new
records: all three remain excluded; train/validation/test counts are 0/0/0.
No new model implementation or real-data training occurred. Diagnostic split
dates are not an adopted evaluation period. Private detail artifact:
keirin_dated_program_intake_2026-10-07.json; raw evidence and reproduction script:
keirin_dated_program_evidence_2026-10-07.zip. The existing private progress JSON
records current counts and, after checks, the final documentation PR receipts.
This documentation increment has not passed CI or merged at this checkpoint;
its final receipts must be read from its PR or that private progress file.

Next: establish source use/time evidence and stable identities for a bounded
continuous period; approve feature mapping before expanding transcription or
training. Do not repeat unchanged failed source URLs or treat PDF metadata as
historical publication evidence. Preserve the separate general-agent goal:
BLOCKED_SUSPEND_EXPIRY_GAP remains unresolved and was not retested in this slice.
Approved historical training races: 0; real-data training runs: 0; accuracy and
return on stakes unmeasured. Production, DB writes, automatic collection,
autonomous learning and runtime activation remain OFF. Counts do not justify an
overall completion percentage or a delivery date.

## Historical payout normalization — 2026-10-07

This checkpoint supersedes older current-status statements below. PR #207 is
merged at main 4a3e18d0f75783d1ecd6d9342087a4a21b637f91,
tree 52b07e8a0bc364020ef4a244ba9dded81f3fb14d. All six PR workflows passed;
independent main-push runs also passed: regression 37588152057 (28/28 jobs),
runtime 37588151938, PostgreSQL 37588152013, UI 37588151987,
ML 37588151978 and AWS 37588152101. Earlier pending statements describe history.

Private intake now contains 314 unique race observations: earlier 13 plus 301 free
KeirinDB samples (2024-01-01: 98; 2025-01-01: 113; 2026-01-01: 90).
These are three individual dates, not complete years. Original downloads and the
source/quality checkpoint are saved privately; no real race data enters this repo.
Source automated/commercial-use scope and historical feature times are unresolved.
The 2026 sample has no entrant table; all 1,408 earlier entrant rows lack H, and the
2026-08-21 rider master has not been joined into earlier features.

Current branch codex/historical-payout-normalization adds ml.historical_payouts.
It preserves raw evidence, hashes and change reasons while accepting only known
ordered-payout date formats that agree with the complete supplied finish order.
Contradictions/unknown formats are quarantined; tied winning orders must be complete.
Refunds require explicit evidence and remain separate from ordinary winning labels.
DNS/DNF/DSQ remain distinct; a nonclassified fault abbreviation is recorded explicitly.
Output is an unapproved normalization candidate, not a training record.

Applied locally to 301 already-downloaded races: 301 internally consistent candidates;
604 payout-row transformations; trifecta outcomes 298 ordinary / 2 dead heats /
1 full refund; one explicit fault-status normalization. Four selected boundary
cases were cross-checked against result/notice pages with scoped, hash-bound evidence
in the private report. This does not verify all 301 records externally or establish
feature timing. No additional race acquisition occurred in this increment.
Local historical checks: 48 synthetic tests passed (15 new); no real-data training.
Current increment CI/merge pending; final receipts belong in its PR and the private
keirin_progress_and_data_quality_2026-10-07.json checkpoint. Do not confuse the prior
PR #207 receipts above with this candidate. The detailed normalization artifact is
keirin_payout_normalization_2026-10-07.json, also outside the public repository.

Next: establish usable point-in-time entry/feature/result evidence over a continuous
period, then review immutable records and freeze chronological evaluation partitions.
Approved real-data training races: 0; real-data training runs: 0; accuracy/ROI unmeasured.
No autonomous collector or learner runs. Production, DB write, external fetch and
runtime activation remain OFF. No overall completion percentage or deadline is
justified by these counts. General-agent blocker BLOCKED_SUSPEND_EXPIRY_GAP remains
unchanged and unqualified; this Keirin increment does not resolve it.

## Result-derived historical form — 2026-10-07

PR #206 is merged at main 2dcebb6dd3b78901ae3d515afa702ac4222564bb,
tree 2c64400069824a928353380eb876f8d1ce3d76c3. All six independent
main-push workflows passed: regression 37585873918, runtime 37585873893,
PostgreSQL 37585873964, UI 37585873906, AWS 37585873924, ML 37585873925.
Its earlier final-head workflows also passed (28 regression jobs). The private
intake snapshot dated 2026-10-07 contains 13 unique factual samples, including
one six-rider race; zero real-data training runs. These are recorded findings,
not new observations in the current slice.

Next implementation on `codex/historical-form-provenance` reconstructs custom
recent form from reviewed earlier results instead of assuming displayed archive
statistics were frozen before a race. It requires namespaced stable rider IDs,
pre-start target entry/cutoff evidence, and result-availability/use/identity
references. It joins identities, not car numbers or fuzzy names. It excludes
future/late/self results, conflicting duplicates and out-of-window races. No
result publication timestamp is inferred from the event date.

DNF/DSQ count in the started-race rate denominator; DNS does not. Mean finish
uses classified finishes only. Dead-heat ranks are retained for these history
features, while dead-heat target labels remain unsupported in training. Missing
history stays missing, with supplied-history coverage and contributing hashes
explicit. These custom window statistics are not claimed to equal an official
published score or complete career record. Candidates still require a separate
review before training; evidence strings do not authenticate source truth.

Historical model input now accepts the four reviewed recent-form fields and
three through nine riders; prospective seven-rider validation is unchanged.
Evaluation reports the test subset for each actual rider count separately.
Local checks: 33 synthetic unit tests passed; a synthetic 18-race form -> training
-> holdout run passed with 8 train / 3 validation / 7 test, including each rider
count from three through nine in test. CI and merge of this follow-up are pending.
No real-data learning, automatic collection, deployment or accuracy improvement
has occurred. The source/use/time/identity evidence for real records remains
unresolved. Next: obtain those inputs through a qualified source and preserve
provenance, then freeze evaluation periods and validate on untouched real data.
Existing suspend-expiry blocker and all production/DB/fetch gates are unchanged.

## Historical training follow-up — 2026-10-07

Added a separate `ml.historical_training` offline path on the development branch.
It requires record-hash-bound operator reviews with source-use, historical-feature
and result-availability evidence references. References are attestations, not an
automatic verification of source permission or truth. Explicit pre-race features
are separate from archived displayed statistics; no historical prediction capture
timestamp is invented. Seven/nine-rider ordinary finishes are supported; dead heats
remain quarantined pending a multi-label contract.

Chronological boundaries are explicit. Complete races stay together and labels
unavailable before the next partition are purged. Training uses train only;
early stopping uses validation; final metrics use the held-out test partition.
Do not repeatedly tune against that test period. This initial path populates
race_score/S/H/B/style only; other shared model features remain missing.

Local evidence: 19 synthetic unit tests pass; a synthetic 12-race mixed 7/9-rider
smoke executed LightGBM training with 8 train / 2 validation / 2 test races and
wrote temporary model artifacts. This demonstrates execution, NOT useful accuracy.
The four existing real samples remain excluded with no reviews and unknown feature
times: zero eligible real records, zero real-data training runs, no new retrieval.
Diagnostic real-sample split dates do not constitute an adopted evaluation period.
Remote main was read as c1cfd45a369c34d4102665579cc4e49842042cff on this turn.
CI workflow now includes these checks; no CI success or main merge claimed here.

Next: substantiate usable historical source access and feature-time evidence,
collect a bounded real dataset, choose and freeze evaluation periods before model
selection, then perform real-data training and evaluate untouched data. There is
no running collector or scheduled training. Production/DB/fetch gates remain OFF.
The separate agent suspend-expiry blocker below is unchanged.

## Planning update — 2026-10-06

Follow-up: historical-source research and offline intake audit implemented locally
on `codex/parallel-keirin-data-plan`. Six candidate sources reviewed to differing
depths; four unique factual sample races saved outside the public repo; all four
quarantined, zero training runs. Seven/nine riders and a dead heat retained.
Eight synthetic intake tests passed. No main merge, CI qualification, bulk crawl,
scheduled collection or model improvement is claimed. See PROSPECTIVE_COLLECTION.md.

Prepared a parallel real-race collection / periodic offline-training plan in
PROSPECTIVE_COLLECTION.md after the user's request. Existing dataset/training/
evaluation code is reusable, but source access, private storage, scheduled worker,
collector integration and operational acceptance remain unresolved. No activation
or actual learning run occurred. Existing production gates remain OFF.

Withdrawn reporting: PR #220–230 as completion forecast; 16.4% as overall progress.
The latter counted completed rows only and ignored partial work and unequal effort.
AGENTS.md now distinguishes implementation, scoped verification and operational
readiness, and requires evidence/assumptions for estimates. This is a planning
branch, not yet a merged implementation. Existing blocker details follow unchanged.

## Current slice: real guest packets across suspend with original kernel guard

Measured result: **BLOCKED_SUSPEND_EXPIRY_GAP**, not suspend qualification. Packet job `111764224176`, regression run `37310432870`, candidate `9846be0336da33b6d2f11781328b59a6a190ed17`, passed all nine experiment records on 2026-10-05 at 21:36:30 JST. The awake control denied all four old/new IPv4/IPv6 qualification probes while all four management probes survived. After actual S3, all four qualification probes still succeeded, without refresh or any preceding post-resume nft read/write. From original installation to first post-resume clock sampling, boottime advanced 11.145488332 seconds; all explicit probes completed within 0.295390938 monotonic seconds of installation. Suspend-window monotonic advanced 0.036644628 seconds and boottime 10.896148706 seconds. Original rules/handles and sentinel remained unchanged; later ordinary awake expiry denied all qualification probes while management survived. Both guest/peer/image/channel/process cleanups completed. Kernel `6.17.0-1022-azure` and QEMU binary/input hashes are in the job and PR #205. This is measured behavior of these exact inputs, not a claim about all kernels or live systems.

Next: preserve BLOCKED and investigate a kernel-enforced deadline or closed boundary that accounts for suspend before a live proposal. Userspace boottime admission alone cannot revoke packets already admitted by the surviving guard. Closed startup ordering and authenticated external management remain unqualified. Final-head five-workflow/28-job and independent main-push integration receipts belong in https://github.com/bzlove178100/-keirin-ai-web/pull/205 ; the measured candidate receipt above does not substitute for them. All activation gates remain OFF.

Updated 2026-10-05 (Asia/Tokyo). PR #204 completed at main `2d8d4718d5fbaa27cfc61bfed8cd333833d6fa7d`, tree `667ed1eddf40cb36ed58c486564bca92aa5ec3ed`. Independent main workflows all succeeded: regression `37305491702` (27/27 jobs), runtime `37305491722` (exact main SHA/push at 20:57:42 JST), UI `37305491697`, AWS `37305491687`, PostgreSQL `37305491681`. VM foundation job `111748042397` passed six records, with actual S3/wakeup and guest reboot/cleanup by 20:52:03 JST. Kernel 6.17.0-1022-azure and QEMU 8.2.2 inputs are hashed in https://github.com/bzlove178100/-keirin-ai-web/pull/204 . Older current-slice headings below are historical.

Add two fresh diskless QEMU guests, one awake and one actual ACPI S3. The emulator still has no NIC/backend, disk, shared filesystem, KVM or live connection. Only internal guest veth/network namespaces carry fixed documentation-address IPv4/IPv6 TCP echo probes. Copy trusted packaged Python/ip/nft/kmod runtime files and read-only matching kernel modules into a private bounded initramfs; use modprobe --show-depends on the host only to discover files, never load host modules. Compile a fixed guest-only PID 1 dispatch after the existing QEMU/opt-in/isolation checks. Keep the original foundation job unchanged and mandatory.

Each guest proves an empty initial ruleset and reachable endpoints before installing any policy: an explicitly OPEN startup negative control, not safe startup. Then install the existing exact eight-second qualification renderer once, retain its handles/rules and unrelated sentinel, and prove old/new qualification and management connections work. The awake case waits ten real seconds and must deny old/new IPv4/IPv6 TCP/443 while old/new TCP/22 echo survives. The S3 case requires real QMP suspend/state/wakeup plus a measured suspend-inclusive clock delta, then probes packets before any post-resume nft read or mutation. Qualification observations must finish before seven monotonic seconds from original installation, with at least ten boottime seconds elapsed. Mixed or late observations are insufficient and fail the experiment.

Report SUSPEND_EXPIRY_OBSERVED only if all four explicit post-resume qualification probes fail. If all four still succeed, report BLOCKED_SUSPEND_EXPIRY_GAP; a green diagnostic CI does not mean the guard qualifies for suspend. Both outcomes must preserve management and unchanged rules/handles, then demonstrate eventual ordinary awake expiry without refresh. Every result keeps activation_allowed=false. No background recovery worker runs in this experiment. Explicit probes are not a packet trace of the kernel's first instruction after resume, and TCP echo is not authenticated SSH.

Local seven packet-evidence/build-isolation + six VM-foundation tests passed (13), packet guest compiled with warnings as errors and refused ordinary host execution. Guest Python syntax checked. First packet CI job `111758239014` stopped before VM launch on standalone nft_counter discovery. The follow-up removes that unsupported standalone-module assumption, requires actual counter-bearing rule creation/readback, and includes dependency stderr on failure; packet/timing gates are unchanged. Second packet job `111759564417` built the image and booted the guest, then PID 1 exited with status 1 before packet evidence. The old parser discarded non-record stderr/console lines, so the underlying Python startup cause is NOT yet known. Preserve a bounded pre-failure console tail (32 lines/4000 characters), with a regression for preceding import errors. Local chroot reproduction was refused by this environment (operation not permitted), not treated as a guest result. The next changed CI must identify the startup cause before any success claim; packet and timing conditions are unchanged. Third job `111761887414` resolved the startup cause: `_Py_HashRandomization_Init` could not obtain random numbers before Python initialization. The initramfs omitted /dev/urandom; add fixed guest character nodes for urandom (1:9) and null (1:3), without copying host entropy or disabling Python hash randomization. These are synthetic experiment runtime inputs, not cryptographic-entropy qualification. Review also found that the peer inherited the original sysfs mount; use socket.if_nameindex() to inspect the actual current network namespace, retaining the exact lo/peer0 and lo/host0 assertions. Kernel sysfs-tagging documentation explains the mount-specific namespace view: https://cdn.kernel.org/doc/html/latest/networking/sysfs-tagging.html . Packet/S3/clock gates remain unchanged; actual packets remain pending. Fourth job `111763147950` now booted Python, loaded modules, isolated the peer, and measured all four unfiltered startup connections successfully. It then stopped at the first nft input transaction because nft -f - opens /dev/stdin, which the minimal image lacked. Add only the fixed guest /dev/stdin -> /proc/self/fd/0 symlink and verify its cpio payload; it resolves in the guest-mounted proc and exposes no host file. No guard was installed in this failed attempt, so it does not measure expiry. The next changed CI must pass the actual rule installation and subsequent packet controls. The corrected candidate subsequently measured the blocking suspend gap above. The new mandatory job requires nine packet experiment records and brings regression to 28 jobs. Require all five final-head workflows/all 28 jobs and independent main-push receipts; record exact observations and any failures/fixes in the PR. No local mocked test is a kernel acceptance receipt.

The measurement requires retaining BLOCKED and investigating a kernel mechanism that includes suspend before any live proposal. A closed-policy-before-link startup implementation, actual external management, privileged tampering, arbitrary endpoints and first live installation remain unqualified. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF. No production host suspend/reboot, packet policy or module change is performed. QEMU package scripts in disposable CI create service metadata; the experiment uses TCG and does not invoke that service or KVM. Do not claim package installation has no service side effects.

## Current slice: diskless disposable guest suspend and boot foundation

Updated 2026-10-05 (Asia/Tokyo). PR #203 completed at main `ea6a025eec07ff415b9c2f5a973ad2f3bb46c963`, tree `3ac83a3ba5ba361361c398cec8fdab8790e1186d`. Independent main workflows all succeeded: regression `37302439098` (26/26 jobs), runtime `37302439121` (exact main SHA/push at 20:29:35 JST), UI `37302439030`, AWS `37302439073`, PostgreSQL `37302439140`. Main lease job `111738110296` passed 65 records; its three clock cases cleaned up at 20:24:08 JST. Exact receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/203 . Older current-slice headings below are historical.

The userspace deadline change does not establish suspend-time kernel packet expiry. Source inspection of the retrieved upstream nf_tables.h found nft_set_elem_expired calling get_jiffies_64, not CLOCK_BOOTTIME. That moving upstream source is not a version-matched proof for the installed Ubuntu kernel, and does not establish its suspend behavior. Version-specific source and real packet observations are still required. Direct retrieval of the v6.17 source failed; do not silently substitute master as a pinned source.

Build a bounded unprivileged QEMU/TCG supervisor and a small static guest PID 1 in a private temporary directory. Reuse the installed disposable CI kernel as read-only input; record kernel/initramfs/QEMU hashes and QEMU version. The fixed command disables default devices, user config, networking, disks and filesystem passthrough; it uses local private serial/QMP sockets and the QEMU syscall sandbox. The guest has only loopback and a fresh private /run. No host service, kernel installation, KVM access, cloud instance, paid resource, live host suspend/reboot or activation is added.

Require actual guest ACPI S3 and QMP SUSPEND/status=suspended before twelve seconds of host elapsed time and system_wakeup/WAKEUP. Guest CLOCK_BOOTTIME must include at least ten seconds more than monotonic, with the same boot ID and private marker retained. Then an actual guest-initiated reboot must produce RESET guest=true, a new boot ID and a fresh empty private /run. A pause, skipped unsupported capability, mocked clock, preserved boot ID or missing event must fail. The host supervisor terminates/reaps only its own QEMU process and removes only its private files; its own boot/network context must remain unchanged. This first slice has no nft policy or recovery worker and cannot qualify packet expiry or fail-closed startup.

Local six supervisor/archive/evidence tests passed, static guest compilation passed with warnings as errors, and ordinary guest-binary execution refused before mounts or power operations. No actual VM was run locally (QEMU/kernel inputs are absent here). CI adds a mandatory separate job, bringing regression to 27 jobs. Require six VM-foundation PASS records, all five final-head workflows/all 27 jobs, then independent main-push receipts before reporting integration. Exact results go in the PR, avoiding documentation-only CI loops.

Next safe slice after this foundation succeeds: add fixed synthetic peer/network packet probes INSIDE the disposable guest, qualify the actual timed-set behavior before/during/after S3 and after boot, and test a deliberately absent startup policy as a negative control. Observe the first post-resume traffic before any userspace guard refresh or recovery action. Real host behavior, privileged guard tampering, external authenticated rescue and first live installation remain unqualified. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF.

## Current slice: suspend-aware admission and recovery deadlines

Updated 2026-10-05 (Asia/Tokyo). PR #202 is complete at main `90e77aca1d320e6abc0918d8e03ea45ca62bccc3`, tree `99ff1fad510bb6c59b951bb8afe1dc7bb17e285a`. Independent main workflows all succeeded: regression `37299274749` (26/26 jobs), runtime `37299274692` (exact main SHA/push verified at 19:59:42 JST), UI `37299274761`, AWS `37299274671`, PostgreSQL `37299274736`. Lease job `111727860100` passed 50 records, including actual worker restart rejection and same-worker SIGSTOP/SIGCONT recovery; cleanup completed at 19:54:10 JST. Exact receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/202 . Older current-slice headings below are historical.

The previous monotonic-only userspace deadlines did not account for host suspend. Bind every preparation/readiness/worker claim to its actual time namespace as well as the existing boot/network/interface context. Guard receipts and worker readiness now carry both original monotonic and CLOCK_BOOTTIME deadlines. Either deadline can expire admission; the worker restores at the earlier remaining duration without rebasing. Sample boottime first when creating deadlines. Missing/non-finite boottime or missing deadline evidence fails closed, with no wall-clock or monotonic fallback. Preserve the original eight-second qualification guard, restoration windows, single-use attempt claim and context/shape checks. All changes remain in the unactivated review/CI fixture.

The existing lease job adds a separately opted-in step with three private network namespaces. Two test children inject only their own boottime observation (+9 seconds for guard expiry and +23 for readiness expiry); this models elapsed suspension and does not change any kernel clock. The third child uses actual unshare --time --fork with unchanged network namespace and zero clock offsets, proving refusal of a different time domain. Each must fail before apply with its specific reason while the parent still accepts the unchanged preparation against its real live worker and guard. Preparation/readiness/claim bytes, guard handles, maintenance policy, unrelated rules and existing/new management connections remain intact; owned resources must all be cleaned. The fixed fault modes are opt-in test entry points, not runtime configuration hooks.

Local 13 lease/clock/restart + 6 shared recovery + 9 context + 7 rescue tests passed (35). One command-free worker test models boottime advancing past its deadline while monotonic remains live and verifies immediate restoration without a fresh sleep. This is control-flow evidence only. CI must retain the existing 50 lease/restart records and add 15 clock-admission records (65 total), all five final-head workflows/all 26 regression jobs, then independent main-push receipts. Record exact final receipts in the PR; do not claim integration from local units alone.

Linux clock semantics: https://cdn.kernel.org/doc/html/latest/core-api/timekeeping.html . Time namespace semantics: https://man7.org/linux/man-pages/man7/time_namespaces.7.html . No actual host suspend, reboot, wall-clock modification or production network change is performed. This userspace admission check does not qualify kernel packet expiry during/after real suspend, or close a suspend between the final check and policy application. A short suspension within both original deadlines is not an unconditional rejection. Actual reboot/persistence, privileged receipt/guard deletion, arbitrary endpoint updates, first live installation and authenticated external rescue remain unqualified. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF.

Next safe slice: inspect the kernel timeout clock and design an isolated disposable-VM suspend/boot qualification with explicit packet probes and fail-closed startup evidence. Keep actual host operations and live activation out of scope until that environment and evidence exist.

## Current slice: single-use recovery attempts across worker restart

Updated 2026-10-05 (Asia/Tokyo). PR #201 is complete at main `0ed57960b86814649c0724e5ee09a8828be49f81`, tree `263f20005d5f03f0cfde07cd8d8fc8e14450899d`. Independent main workflows all succeeded: regression `37295547713` (26/26 jobs), runtime `37295547695` (exact main SHA/push verified at 19:24:41 JST), UI `37295548397`, AWS `37295547918`, PostgreSQL `37295547955`. Guarded rescue job `111715771442` passed 21 records including available/broken paths and complete cleanup. Exact receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/201 . Older current-slice headings below are historical.

Inspection found that worker startup unconditionally replaced readiness and started a new deadline from the current clock. A command-free mocked replay of the actual pre-change worker on this base (same preparation, mocked PIDs 101/202 and clock 100/200) replaced the first deadline 122 with 222. This is local control-flow evidence, NOT an actual systemd restart, host reboot or suspend result. Existing Restart=no and kernel expiry do not make reused worker preparation a single-use record.

Create an exclusive worker.claim in the existing private root-owned attempt directory before publishing readiness. Bind its first PID/start identity to the original attempt/version/boot/netns/interfaces, and require that same claim at controller readiness. Any existing claim, including a partial one left by process loss, consumes the attempt and stops a second worker before deadline creation or readiness replacement. Preserve original no-restart policy, lease duration, recovery windows, context/shape checks and all legacy negative controls. This remains an unactivated CI-only recovery fixture.

The existing lease CI job adds a separate opt-in step with three fresh namespaces: SIGKILL/manual restart before apply; SIGKILL/manual restart after apply/controller death; and SIGSTOP followed by SIGCONT after the original recovery deadline. Restart cases must observe WORKER_ATTEMPT_ALREADY_USED while the original guard is still live, reject stale controller readiness, preserve preparation/readiness/claim bytes, and expire dual-family qualification while management survives. They must not invent successful recovery after losing the worker. The paused same worker must remain stopped through guard expiry, then restore maintenance after its original deadline without rearming. All cases preserve guard handles/unrelated rules and remove owned units/processes/links/tables/claim files. Existing 35 lease records remain mandatory, with 15 new restart/pause records required. Regression remains 26 jobs.

Local 9 lease/restart + 6 shared recovery + 9 context + 7 rescue tests passed (31). Actual systemd/kernel records, all five final-head workflows/all 26 jobs, and independent main-push receipts must be recorded in the PR before reporting integration complete. No actual reboot or host suspend is performed. Linux CLOCK_MONOTONIC stops during system suspend while CLOCK_BOOTTIME includes it; SIGSTOP only stops a process, so this proof cannot qualify host-suspend expiry. See https://cdn.kernel.org/doc/html/latest/core-api/timekeeping.html and https://github.com/systemd/systemd/blob/main/man/systemctl.xml .

Next safe slice: determine and test suspend-aware admission/evidence invalidation without claiming host-level packet expiry from userspace checks. Actual host reboot/persistence/suspend behavior, privileged claim/guard deletion, arbitrary endpoint changes, first live installation and authenticated external rescue remain unqualified. The private /run claim is not reboot-durable storage or protection against another root writer. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF.

## Current slice: restricted rescue under kernel qualification expiry

Updated 2026-10-05 (Asia/Tokyo). PR #200 completed at main `c8824c7f271ab1359d96d738123eb8a5ae68af9f`, tree `c97f66a311045aa3d997f5300ee31deeafdbea66`. Independent main-push workflows all passed: regression `37292654022` (25/25 jobs), runtime `37292654006` (exact main SHA/push), UI `37292654125`, AWS `37292654118`, PostgreSQL `37292654101`. Guarded chrony job `111706473022` passed 26 records and cleaned up at 18:52:15 JST; runtime finished at 18:57:56. Exact receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/200 . Older current-slice headings below are history.

Add explicit `rescue-lease` admission with the existing fixed DHCPv4 qualification tuple and unchanged restricted-rescue policy. Resolve the guarded alias when binding interface identity so BOTH host0 and rescue0 are checked by readiness and the restoring worker. The original eight-second guard is installed before readiness, while the original independent worker retains its 22-second restoration window.

Two mandatory cases run in separate private namespaces: an available static rescue path and that same path deliberately down. Both require real primary administration/DNS/DHCP denial after controller SIGKILL, followed by old/new qualification expiry while candidate rules and the same worker remain. The available path must retain old/new TCP/22; the broken path must remain unusable. The same worker must restore maintenance after expiry without rearming, followed by actual DHCP ACK, cache-flushed A/AAAA upstream queries and primary administration returning in the same private daemons. Wrong rescue source/port remains denied; unrelated rules and guard handles remain unchanged. A successful table restoration cannot override BLOCKED/RESCUE_PATH_UNAVAILABLE. All verdict activation fields remain false; owned teardown removes both guards and all private resources.

Local 7 rescue + 9 context + 6 shared recovery + 6 lease tests passed (28). The new guarded job is separate from the mandatory original available/broken controls, bringing regression to 26 jobs. Actual kernel results, all five final-head workflows/all 26 jobs and independent main-push receipts must be recorded in the PR before reporting integration complete. No local test result is a kernel acceptance receipt.

The second static veth only isolates the tested primary DHCP/DNS/allowance failure. It is not out-of-band from the same kernel/netns/firewall, and TCP echo is not authenticated SSH. No live installer or arbitrary endpoint updates are added. After successful integration, next examine restart/boot/suspend invalidation of prepared qualification and recovery evidence using isolated controls; do not reboot or suspend the live host. Privileged guard tampering, first live installation and external authenticated management remain unqualified. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF.

## Current slice: real chrony clients under kernel qualification expiry

Updated 2026-10-05 (Asia/Tokyo). PR #199 is complete at main `b935837609a54306bf33f7ff98a3e835fb229046`, tree `4846850a4832bd551c103b0dc9c4facca0945449`. Independent main workflows all passed: regression `37289811718` (24/24 jobs), runtime `37289811518`, UI `37289811508`, AWS `37289811562`, PostgreSQL `37289811763`. DHCPv6 job `111697308154` passed all existing controls and 16 guarded records. Exact PR/main receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/199 . Older current-slice headings below are history.

Compose the real chrony client lifecycle with the already prepared `time-lease` profile. Each family runs in its own private namespace with a fresh one-shot eight-second guard, unchanged time policy and a 22-second independent restoring worker. No guard is deleted/rearmed between attempts in the same namespace.

Require actual old/new qualification success, controller SIGKILL, then kernel expiry while candidate rules and the same worker remain. After observed expiry, both approved peers must supply two NEW good samples within five seconds to the same capability-free client, with the primary selected, both reachable and existing/new management preserved. The same worker must then restore maintenance without rearming. Existing post-controller (3s), post-restore (two samples/5s), fault preparation (four fresh samples from both peers, one completed burst 4/16, 12s), silent/wrong-origin failover (35s), rejection and approved return (20s) contracts remain unchanged. Guard handles must survive the full failover/rejection/return lifecycle and be removed only by owned teardown.

The legacy fifteen-record unguarded job remains mandatory. One new mandatory guarded job has separate IPv4/IPv6 cases and retains real interleaved/kernel RX/TX evidence, wrong-origin/no-response controls, unapproved-source/TCP denial and complete process/file/link/rule cleanup. Local 15 time + 6 lease + 6 shared recovery + 8 context tests passed (35). This is local evidence only; the PR must record actual guarded kernel results, all five final-head workflows/all 25 regression jobs, and independent main-push receipts before reporting integration complete.

No clock is adjusted: clients and real servers run as nobody with no capabilities, NoNewPrivs and `-x -U`. A same-clock synthetic reference does not establish external UTC accuracy, authenticated NTP/NTS or live-host time qualification. Next after successful integration: guarded restricted-rescue composition. Arbitrary endpoint/address changes, reboot/suspend, privileged guard tampering and first live installation remain unqualified. All runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates remain OFF; no phone/AWS/credential step is needed.

## Current slice: DHCPv6 under kernel qualification expiry

Updated 2026-10-05 (Asia/Tokyo). Resume confirmed PR #198 merged at main `06440cab6f52a63405500ade0f3c286c073d98e2`, tree `b2c14005ee5a4dba1fd720b9d9fcdcf982a3794c`. All independent main-push workflows succeeded: regression `37252751176` (24/24 jobs), runtime `37252751169`, UI `37252751187`, AWS `37252751155`, PostgreSQL `37252751170`. Guarded DNS job `111583551262` succeeded. The prior in-progress main receipt is resolved; older current-slice headings below are historical.

Add explicit `dhcp6-lease` admission using the fixed IPv6 tuple and the unchanged DHCPv6 base policy, including multicast DHCPv6 controls. The existing prepared receipt binds the guard to its attempt/boot/netns/interface, expires after eight seconds, and cannot be refreshed by candidate/maintenance restoration.

The mandatory guarded case reuses the pinned patched CI client in a fresh private namespace after the existing original-defect, patched-lifecycle and unguarded-recovery controls. Require actual old/new qualification success, controller SIGKILL, kernel expiry with candidate rules and the same live 22-second worker still present, then a NEW DHCPv6 Renew after expiry and before restoration. Both inet/netdev DHCPv6 counters and actual address lifetime must increase. Existing/new management must remain usable. The same worker must restore maintenance after expiry without rearming; wrong-source denial, another Renew, Rebind to the allowed alternate DUID and genuine address expiry while the RA route remains all continue under unchanged guard handles. Owned teardown removes guards as well as base tables, links and processes.

Local 4 DHCPv6-recovery + 9 DHCPv6 protocol + 6 shared-recovery + 6 lease + 8 context tests passed (33). No kernel success is inferred from these local tests. Exact final-head CI, guarded PASS records and independent main-push receipts must be recorded in the PR. All five required workflows and all 24 regression jobs must succeed before merge. This adds one mandatory step to the existing client-build job, without duplicating the build or dropping existing controls.

Still unqualified: guarded real chrony client and rescue composition; arbitrary endpoint/address changes; reboot/suspend; privileged guard tampering; first live installation. After successful integration, the next dependency is the real chrony client under the same prepared guard, followed by restricted rescue. The DHCPv6 evidence qualifies only the explicitly patched CI client, not the installed Ubuntu/live-host binary. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates remain OFF. No phone/AWS/credential operation is required or authorized by this slice.

## Current slice: DHCP-delivered DNS under kernel qualification expiry

Updated 2026-10-05 (Asia/Tokyo). PR #197 is merged at main `b9013dc9c8bd144771b418ecdeec0d1d32dad5a6`, tree `88a9ba1fdcee45e8b58645f6eead4d4931a1d5dc`. Independent main workflows all passed: regression `37250898062` (23 jobs), runtime `37250898059` (exact main SHA), UI `37250898068`, AWS `37250898109`, PostgreSQL `37250898048`. Dynamic guard job `111578110677` passed twelve records. Current main and these receipts were rechecked before this slice. Older pending/blocker descriptions are history, not a reason to repeat completed work.

Add explicit `dhcp-dns-lease` admission using the unchanged DHCP-DNS maintenance/candidate policy and existing fixed DHCPv4 guard tuple. Preparation creates and seals the independent eight-second guard; worker readiness and both controller checks require its original bound receipt. No DNS observation grants permission or alters the fixed allowed resolver. Legacy unguarded execution remains a separate mandatory control.

The new mandatory private-netns CI case runs real networkd, resolved and a private bus. After controller SIGKILL it must show old/new qualification success, then kernel expiry with candidate rules still present and the same 22-second worker alive. Cache-flushed A and AAAA queries must still reach the approved upstream. Actual DHCP renewal must deliver an unapproved DNS address without widening access, followed by late PID 1 maintenance restoration without guard rearming. Existing distinct negative transactions, approved return, killed/mixed observations, daemon identity checks and genuine DHCP lease/address/route/DNS expiry continue under the same expired guard. Owned cleanup must remove guards as well as the base tables, links, processes and private files.

Code head `497cb60c6281d20029bf00ced482b3d2e8ee58c9`, tree `2e9701620623998ef9decf58ee8e48817ceb14ba`, regression `37252034264`, guarded DNS job `111581475013`: all 21 records passed at 10:37:20 JST. Kernel-expiry denial with candidate rules, the same live worker, fresh approved A/AAAA queries and management was observed at 10:36:10; actual DHCP unapproved-DNS delivery remained denied at 10:36:17; PID 1 maintenance restoration after expiry passed at 10:36:23. Same-daemon approved return, killed/mixed collectors, genuine DHCP address/route/DNS withdrawal and unchanged guard handles through full cleanup also passed. The legacy DHCP-DNS, dynamic guard and time jobs succeeded. Local 17 related tests passed. No failed attempt or identical rerun occurred. Final-head all-five-workflow/24-job and independent main receipts belong in PR #198: https://github.com/bzlove178100/-keirin-ai-web/pull/198 . All five final workflows and 24 regression jobs must pass before merge; no live apply is authorized.

Still unqualified: guarded DHCPv6, chrony client and rescue composition; arbitrary endpoint changes; reboot/suspend; privileged guard tampering; first live installation. Next dependency slice is DHCPv6 under the same prepared-guard boundary. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates remain OFF; no phone/AWS/credential operation is needed.

## Current slice: guarded dynamic dependencies and restoration after expiry

Updated 2026-10-05 (Asia/Tokyo). Start from PR #196 main `43d885ec9b99ab9c74f61260912f39c03a1509ac`, tree `bb58aed189d4ed5299a6b71f47df9c138a0b7a58`. All five independent main-push workflows and 22 regression jobs passed; main regression `37249256571`, runtime `37249256614` (exact main SHA verified at 09:59:08 JST), time `111573315450` (15 records) and lease `111573315341` (35 records). PR #196 is merged; older DRAFT/BLOCKER text below is historical and superseded by its final receipt.

The fixed pure lease renderer now has explicit time, DHCPv4 and IPv6 RA tuple profiles. No caller-supplied addresses or live presets. Shared preparation/admission supports `dhcp4-lease` and `ra6-lease`, preserving their base maintenance/candidate policies while requiring separate fixed guard creation, bound receipt and live lease. Snapshot validation expects the selected profile's fixed rule count and retains handles/policy. Existing legacy profiles and negative controls are unchanged.

A new mandatory private-netns CI job runs real networkd DHCPv4 and IPv6 RA cases with the eight-second kernel guard and 22-second independent worker. Require actual old/new qualification success before expiry; renewal/RA refresh after controller SIGKILL; old/new denial while candidate shape and live worker still remain; dynamic ARP/ND plus existing/new management; subsequent PID 1 maintenance restoration after guard expiry without changing guard handles; then DHCP primary-to-alternate rebind or continued RA refresh followed by genuine route expiry. Owned files/processes/units/links/tables and unrelated-table preservation are checked. Code head `d866cd4d2fc4debab8a96395ea9bea76378231d3`, tree `e3b6e72f3e66fe9101d8843165100cb4dac85adb`, regression `37250237810`, dynamic lease job `111576217409`: all twelve records passed at 10:10:34 JST. IPv4 kernel-expiry denial with ongoing renewal/admin/neighbors was observed at 10:09:10, then the same PID 1 worker restored maintenance at 10:09:24. IPv6 expiry/RA-refresh/admin/ND passed at 10:10:00 and late worker restore at 10:10:08. Post-restore DHCP rebind and IPv6 RA refresh/actual route expiry passed; guard handles were unchanged. Time job `111576217426` passed all fifteen records with actual interleaved/kernel TX evidence at 10:10:02. Existing static guard job also succeeded. Local 3 dynamic-lease + 6 lease + 6 shared + 8 context tests passed (23). Final-head all-five-workflow/23-job acceptance and independent main receipts belong in PR #197: https://github.com/bzlove178100/-keirin-ai-web/pull/197 . No live activation. All five final workflows and 23 jobs must pass before merge.

Scope remains synthetic fixed offered addresses/routes. This does not authorize learning arbitrary endpoints, extend the eight-second lease, qualify DHCPv6/resolved/chrony/rescue composition under the guard, install a live host policy, repair a missing route, authenticate SSH, or handle reboot/suspend/privileged guard tampering. All runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates remain OFF. Next after this slice is dependency-bound preparation for the remaining profiles; do not repeat completed baseline controls as new progress. Exact code/final/main receipts belong in the PR.

## Chrony peer repair: changed-condition acceptance (2026-10-05)

PR #196 now replaces only healthy approved synthetic NTP responses with four real chronyd 4.5 server processes (one per address/family). Clients request interleaved mode, so actual kernel TX timestamps can be returned on the next exchange. Both client and server run as nobody with no capabilities, NoNewPrivs and `-x -U`; each server binds only its fixed peer address, permits only the fixture host, and uses local stratum 1 without an upstream. Only the private peer namespace permits unprivileged port 123. Same host clock remains a synthetic reference, not external UTC qualification. Silent/wrong-origin fault injection explicitly stops the primary server and hands its socket to the bounded fault peer; return restarts the server, never the client or its sample history. Unapproved-source counters remain real packet-server counters; approved-peer counters now count fault traffic only. EOF/SIGTERM cleanup reaps server children and removes private directories.

The old basic-mode Python server placed T3 before the kernel send; RX repair and burst acquisition could not correct that TX approximation. The exact timing of the historical rejected packets was not captured, so do not claim their per-packet TX delay is proven. The new implementation removes the approximation from healthy measurements and explicitly requires interleaved client reports plus positive server kernel RX/TX counters. Filters, four fresh good samples from both peers, one burst 4/16, twelve-second preparation and original 3/5/35/20-second sample/failover/return deadlines are unchanged.

Code head `b1528692be0385cdbd626377ed857ae09137f052`, tree `e6acff5e906c79c7e5f64dbed9d5f6460422dfc3`, regression `37248568514`: time job `111571313613` passed all fifteen records at 09:44:15 JST. Each of four preparation phases confirmed both clients interleaved and both servers actually using kernel RX/TX. Primary/alternate kernel TX counts: v4 silent 15/15, v4 origin 4/28, v6 silent 16/15, v6 origin 4/29. Lease job `111571313723` passed all 35 records at 09:44:23 JST. Local thirteen time + six lease + six shared + eight context tests passed (33). Final head additionally asserts successful peer exit after cleanup; full final-head and main-push five-workflow/22-job receipts belong in PR #196. Until those receipts pass, no merge or live activation. Previous failed head and diagnosis remain below as history.

Next after integration: qualify guard restoration after expiry and required dynamic network dependencies before any live proposal; boot/suspend/first live install remain unqualified. No phone/AWS/credential steps. All activation gates remain OFF.

## Current slice: require a prepared kernel guard before qualification

Updated: 2026-10-05 (Asia/Tokyo). Base main `a44280a77c1d0d0a44285dae29065c5c67d094c6` is PR #195; its five main workflows and 22 regression jobs succeeded. Previous slice below remains historical evidence.

The new explicit CI-only `time-lease` profile prepares the fixed guard with create-table semantics before starting the independent worker. It seals both table readbacks, retaining handles and all policy fields, and binds the receipt to the attempt/boot/netns/interface context. A conservative eight-second deadline starts before install and never refreshes. Worker readiness publication and both controller readiness checks require a live member, unchanged receipt/snapshot and at least two seconds on that original deadline. Missing, altered, recreated or expired guard stops before candidate mutation. Restore to maintenance deliberately does not require an unexpired guard. Legacy unguarded negative controls remain mandatory.

Local six lease, six shared recovery and eight context tests passed. Code head `aa73bae115810b392a83fcde50057ff840175d3a`, regression `37248051381`, lease job `111569789198` passed all 35 records at 09:36:01 JST: original 20 plus healthy guarded apply/restore and missing/changed/expired/recreated guard refusal with maintenance/admin preservation. PR #196 remains DRAFT and UNMERGED: https://github.com/bzlove178100/-keirin-ai-web/pull/196 . No live installation or activation. All production/runtime/provider/credential/DB/data-fetch/scheduler/report gates remain OFF.

BLOCKER: the same head's existing time job `111569789371` failed IPv4 origin-prime at 09:35:24 JST. Primary good RX rose only 17→20 (required +4); alternate 21→32. Raw primary delay-deviation rejections (`111/111/1101`) rose 12→32; all 52 primary responses were valid, only 20 cumulative good. The single burst 4/16 did not make acquisition reliable. Primary remained selected/reachable, so this is insufficient accepted samples, not transport loss or failed source selection. No unchanged rerun, increased deadline, lowered sample count, disabled filter or merge. Documentation-only CI success must not be interpreted as a timing repair.

Next work: correct the synthetic time peer/transport timing model using the recorded receive/response/delay evidence; verify the cause before choosing a remedy. Preserve the four-good-sample and bounded acquisition contracts, real chrony rejection filters, failover deadlines and original mandatory jobs. Kernel RX timing is already measured; Python response construction and transmit timestamp-to-kernel-send delay remain unqualified. Do not claim this latter hypothesis is proven. A changed-condition time test and all required CI must pass before PR #196 can merge.

The receipt is trusted fixed-installer readback, not a cryptographic attestation or protection against arbitrary root writers. Kernel set expiry remains essential after the last read; checks cannot remove the final-read/commit race. Expiry positivity is checked without assuming a JSON time unit; the admission deadline is the original userspace monotonic bound, not a refreshed kernel countdown. Same-handle privileged member recreation is not qualified. Reboot/suspend, dynamic dependency composition, first live installation and authenticated management access remain open. Exact CI/head/merge receipts will be retained in the PR.


## Current slice: kernel-enforced qualification expiry after process loss

Updated: 2026-10-04 (Asia/Tokyo).

Start from main `e05c17ddaa9fbff58db951db8f509c3fe17b07e3` (PR #194 merged). Final PR and main each passed all five workflows and 21 regression jobs; main regression `37208709975`, runtime `37208709982`, time job `111455278843` (15 records). Main tree `193b044fbe37e2441b135ee7e707f45eda14f8be` matched the accepted PR tree. CI candidate/main dependency repair is complete. The historical chrony rejection cause remains unproven; use raw evidence if it recurs, no blind rerun.

PR #193 showed the remaining final-check race: worker SIGKILL just after readiness plus controller SIGKILL can leave qualification active indefinitely. A new pure review renderer now installs a separate, fixed synthetic inet/netdev guard BEFORE readiness. Timed set membership allows only the fixed IPv4/IPv6 peer TCP/443 while an eight-second kernel lease exists. Every packet is gated, including established TCP. The existing candidate/restore transactions do not own those tables. create-table semantics refuse installation replay while the guards exist; no packet-path update, renewal API, flowtable or broad established bypass is present. The one-minute GC interval intentionally exceeds the lease, so traffic expiry cannot depend on prompt garbage collection.

The new mandatory CI job exercises four separate private namespaces: normal PID 1 restoration; worker death immediately after final readiness followed by candidate apply/controller death; a controller held until AFTER the lease expires before applying; and MAC drift causing worker fail-stop. Require dual-family old/new qualification denial, preserved old/new administration, unchanged unrelated table, unchanged guard handles, refused rearming and two stale candidate replays which cannot reopen access. Existing unguarded negative controls remain mandatory, accurately demonstrating why repeated readiness checks alone are insufficient. The parent observes expiry without mutating nft; its later replay/cleanup is explicitly not recovery.

Local: four lease, eight context, six shared recovery and twelve chrony tests pass (30 total); web/safety regression and diff check clean. Targeted real-kernel acceptance is recorded below. All five workflows and now 22 regression jobs must succeed before merge. Exact head, kernel records and merge/main receipts belong in the PR for this slice.


Initial head `da5c78bb98d1f8f6c5a40a8757d4d33405cdda69`, regression `37209633888`, lease job `111457986532`: normal, worker-loss and delayed-apply each passed all five records. Identity-drift passed baseline/fault but failed old-administration exchange at 23:33:22 JST. Linux v6.17 ARP and ND NETDEV_CHANGEADDR handlers call neigh_changeaddr, which flushes even permanent local neighbors. The old fixture updated only the peer's neighbor mapping. The corrected case now reads back and requires local peer mappings absent after MAC change, then explicitly restores the static local mappings and updates the peer before evaluating expiry. This is deliberate fault-fixture setup, not autonomous recovery; the changed MAC still requires worker context fail-stop. Do not claim the historical log independently captured the flushed neighbor table.

The same initial head's time job `111457986448` failed IPv4 origin-prime at 23:33:12 JST. Raw groups now directly identify delay-deviation rejection (`111/111/1101`): 8 primary, 5 alternate. Diagnostic accepted deltas were primary +4, alternate +7, but the bounded predicate had already timed out; diagnostics are later samples, not proof that the predicate was satisfied before deadline. Kernel RX correction remains valid but does not prevent shared-runner/path/TX jitter or ensure four accepted samples from one-second polling in a fixed window.

Healthy phase preparation now issues exactly one chronyc burst 4/16 to each fixed peer, retaining chrony's good-packet filters, the four-new-good requirement, source preference and twelve-second wait. Require both burst states zero before injecting the fault; normal configured poll 0 and all failover/restoration deadlines remain unchanged. This uses bounded active acquisition instead of assuming every periodic response is accepted. No CI rerun, threshold reduction, filter relaxation, source reset or clock change. Twelve chrony unit tests pass, including command scope/failure and completed-burst requirements. Changed-condition CI must still prove all original fifteen records and all twenty lease records.


Corrected code head `1f4f4bd34ec10200fea82b528a5062163c5fdff3` (tree `e9de122079cad46efdaf799012205c8d8d044350`), regression `37210048538`: lease job `111459213686` passed all twenty records at 23:40:13 JST. The MAC-change readback was actually `[]`, confirming local neighbor removal; explicit static transport restoration let the same changed-MAC worker fail-stop while kernel expiry revoked old/new dual-family qualification. Normal restore, combined worker/controller death, delayed post-expiry apply, no-refresh under traffic, refused rearm and candidate replay denial all passed with existing/new administration preserved. Kernel `6.17.0-1022-azure`. No previous failed job was rerun unchanged.

Time job `111459213731` passed all fifteen records at 23:40:42 JST. Every one of four fresh phases measured +4/+4 accepted samples and burst_finished=true. Raw delay-deviation rejections still occurred (e.g. ten primary rejections cumulatively by IPv6 origin preparation), demonstrating accepted acquisition without disabling rejection. This is acceptance of bounded preparation, not proof that shared-runner timing variance is gone. The remaining full regression jobs were still completing when this targeted evidence was recorded; final-head all-five-workflow/22-job acceptance and merge/main receipts belong in PR #195.

This is an unactivated synthetic guard implementation, not a live firewall installer or permission grant. Expiry revokes the temporary transport allowance; it does not restore table shape, repair a broken management route or establish SSH authentication. Current proof is fixed static peers and the existing dual-family time firewall profile. Other profiles/dynamic DHCP/RA/rescue composition, first live installation, reboot/suspend persistence, same-ifindex reuse and arbitrary privileged guard deletion/rearming remain unqualified. Next qualify the guarded installation/ownership path and required dynamic dependencies before any live proposal. No phone/AWS/SSH/credential operation; all production/runtime/provider/DB/data-fetch/scheduler/report gates stay OFF.

## Completed repair: candidate-bound CI and kernel receive timestamps

Updated: 2026-10-04 (Asia/Tokyo).

At the start of that repair main was `f025ff39bf9d67b4a501b7f214ec95a8aa7bd3e5`; its regression `37192146307` failed the time fixture. PR #194's first diagnostic head `bfec3186dac40d2a3dc35f7f169ceef987f4aca2` passed 21/21 regression jobs but failed runtime `37192519684` because that smoke inspected older main. These failures are retained, not reclassified or rerun unchanged.

The repair changes only the CI smoke entry point: resolve the current Actions run, pin file reads to its SHA, and require actual successful regression/UI workflow results at the same SHA, event, branch, repository, workflow ID and path. It waits at most ten minutes for pending/missing siblings; any completed failure blocks immediately. It does not wait on itself, accept old green main, ignore failure, or return success on timeout. The standalone legacy main-health bridge and strict hosted four-workflow/main-drift verifier are unchanged. On main push, the smoke now waits for that same main commit, removing the earlier timing race. Candidate verification is not a claim that the old main is healthy or that hosted execution is authorized.

The synthetic NTP server now places Linux SO_TIMESTAMPNS_NEW kernel receive time in T2, instead of the time Python returns from recvfrom. This corrects accounting of socket queue/process scheduling time: it belongs to server residence T3-T2, which NTP subtracts from RTT. Reject missing/duplicate/malformed/truncated timestamp controls, without userspace fallback. A CI-only queued-packet control checks the actual receive field against the kernel timestamp after a deliberate 25ms dequeue delay. Existing source preferences, chrony filters, packet validation, fresh-sample requirements, all deadlines and fifteen acceptance records remain unchanged. Raw packet-rejection logs remain enabled. Historical failed-main packet rejection is still not retrospectively proven; successful CI alone cannot establish that all runner jitter is fixed.

Local validation: 10 chrony tests, 9 candidate-CI tests (including real BoundRuntime success/blocking), 4 legacy bridge tests and 15 strict SHA bridge tests pass. Code head `cdbc510f38d7b3b3dc15c49dffd04e20f797446f` (tree `473df2f65a71d842170fb0de787a96f318c29cb3`) passed all five workflows: regression `37207894470` (21/21 jobs), UI `37207894486`, runtime `37207894447`, AWS offline `37207894418`, PostgreSQL `37207894420`. Runtime job `111452832524` completed at 23:09:34 JST and explicitly verified this same SHA using regression/UI run IDs above while old main remained failed. Thus the candidate/main dependency defect is repaired in actual CI. Final documentation-head CI and merge/post-merge receipts are recorded in PR #194. Do not merge unless all applicable workflows succeed. If time acceptance fails again, inspect the new timestamp control and raw measurement evidence before changing anything; no blind retry or threshold relaxation.


Time job `111452833052` passed all fifteen records at 23:05:48 JST. The independent receive-time control measured 0.0251536369 seconds of actual queue residence and confirmed the emitted T2 equals kernel receipt. Fresh accepted deltas (primary, alternate) were IPv4 silent (4,4), IPv4 origin (4,4), IPv6 silent (4,5), IPv6 origin (4,4). Delay-deviation rejections still appeared in raw logs, without failing acceptance. This fixes a measured timestamp-accounting defect; it does not eliminate genuine TX/path jitter or prove the exact rejected subtest in the historical failed main. No filter/deadline change or identical rerun.

No live host, phone, AWS, SSH or credential operation. All runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF. PR #193's worker-loss last-check gap and first live installation remain unqualified; they are separate from this repair.

## Previous diagnostic boundary: chrony per-packet rejection after main failure

Updated: 2026-10-04 (Asia/Tokyo).

PR #193 merged/closed at `f025ff39bf9d67b4a501b7f214ec95a8aa7bd3e5` after final head `22fdb1ae49e189d30228bcf0d273790f009e186c` passed all five workflows and twenty-one regression jobs (`37191720165`). Context job `111405131196` reproduced all fifteen identity/worker-loss records; the last-check gap remains explicitly unqualified. Local/remote main and the tested tree matched after merge.

The later main push regression `37192146307`, time job `111406414809`, FAILED at 18:27:09 JST in IPv4 origin-prime preparation. Primary RX/valid/good changed 20/20/17 to 31/31/20: eleven valid packets but only three new accepted measurements, below the unchanged four-measurement requirement within twelve seconds. Alternate changed 28/28/23 to 40/40/35. Primary remained selected and both sources were reachable with poll 0. Earlier controller/restoration and silent-primary failover assertions passed. Main acceptance is not complete and the successful PR acceptance is not a substitute for this failed later run. No identical rerun was requested.

The last ntpdata NTP tests were all 1; they do not retain every earlier response's rejection bits. Chrony 4.5 official source confirms that accepted-count increments depend on additional maximum-delay, delay-ratio, delay-deviation/quantile and loop tests. The precise failed subtest is still unknown. Shared-runner scheduling and the Python server's userspace receive timestamp are hypotheses, not confirmed causes.

The follow-up adds rawmeasurements logging only inside the existing private unprivileged clockless client, a bounded parser restricted to the two synthetic peers, per-source test-bit-group counts and a sixteen-record tail in preparation/failure evidence. No packet contents, source preference, sampling threshold, poll rate, delay filter or deadline is changed. Eight chrony unit tests pass. Changed-condition CI will retain information absent from the failed main run; success still requires the original fifteen records/four preparations, and a failure must be investigated from actual raw test bits. Do not repeat identical reruns or widen acceptance filters.

The legacy runtime smoke reads the latest completed MAIN CI, so it may correctly block this PR while main regression is failed. Do not relabel that failure as success, bypass the verification step or infer production readiness. Keep any diagnostic PR unmerged unless its applicable integration gate is satisfied. No live/phone/AWS/SSH/credential operation; all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates OFF. First installation and combined worker/controller-loss recovery remain unqualified.

## Previous completed slice: recovery context binding and worker loss at final readiness

Updated: 2026-10-04 (Asia/Tokyo).

PR #192 merged/closed at `25b1bb6b65df1a36fa3a56f927592f9674afbe36`. Final head `d2328adce5dd05f1bfd9d549c533467d6201a102` passed all five workflows and twenty regression jobs (`37190265015`); post-merge main also passed all five workflows and twenty jobs (`37190575050`), plus Pages. Main rescue job `111401692696` and time job `111401692694` each passed fifteen records without a rerun. This continuation rechecked remote main, merged PR, successful main jobs and the clean matching local main. Accepted phone evidence is not repeated.

The shared dynamic CI recovery worker now binds the expected attempt/profile to actual boot/netns and fixed interface name/ifindex/MAC/veth kind (host0, plus rescue0 for rescue). The controller verifies that binding and actual context at preflight and again after table comparison immediately before apply. The PID 1 worker verifies context before readiness and before deadline restoration. Changed, missing or unreadable context stops without overwriting current tables. Dynamic address/route/lease, MTU and link up/down remain outside identity so the existing dynamic and broken-path cases retain their original meaning. All original 5/22-second worker windows, 35-second unit bound and protocol assertions remain.

The new twenty-first job requires fifteen records across five fresh process/netns cases: stable restoration/revocation; same-name/same-MAC interface replacement rejected by a changed real ifindex; post-apply MAC drift stopped without replacement; worker SIGKILL after first readiness caught by the final check; and worker SIGKILL just after the final check followed by candidate installation/controller death. The last case must observe no restoration beyond the original deadline and real old/new qualification still active, reporting BLOCKED/WORKER_LOST_RECOVERY_UNVERIFIED. Identity-drift fail-stop similarly can leave qualification active. These are explicit unresolved operational boundaries, not successful recovery. Every authorization/review gate remains false, and the parent's later teardown is not recovery evidence.

Eight new, six shared recovery, six rescue and seven chrony tests pass locally (27 total); the new actual kernel acceptance passed as recorded below. All five final-head workflows and twenty-one regression jobs are required before integration. See [recovery context review](SECRET_CUSTODY_RECOVERY_CONTEXT_REVIEW.md). Exact code/final-head evidence and merge receipt belong in the PR.

Code head `cf623fd4fc106eaa0640ba2a3180734aa07dea75` (tree `10341d9f5eea121e4e08e1d61136ccaf6ef2f73e`), regression `37191566578`, context job `111404653037`, passed all fifteen records on its first execution, with `SYNTHETIC_RECOVERY_CONTEXT_OK_LAST_CHECK_GAP_UNQUALIFIED` at 2026-10-04 18:15:59 JST. The real same-name/same-MAC replacement changed ifindex 3 to 5 and was refused without table overwrite. Stable context restored/revoked old/new qualification and preserved administration. Post-apply MAC drift stopped restoration while actual qualification remained active. Worker loss after the first check was rejected before apply; loss after the final check allowed candidate installation/controller SIGKILL, then showed no recovery result after the original deadline plus one second and still-working old/new qualification. Both unsafe outcomes were explicitly BLOCKED with all authorization flags false. Each case cleaned up the worker/controller/peer, private files, links and owned tables, preserving the unrelated table until fixture teardown. Kernel `6.17.0-1022-azure`; no code-head retry or deadline relaxation.

The changed shared helper also passed the existing restricted rescue job on this code head; other protocol jobs were still completing when this evidence was recorded. All five workflows and twenty-one regression jobs on the final documentation head remain the integration gate. Exact final results and merge receipt belong in PR #193. This evidence demonstrates the last-check gap; it does not repair it or qualify first live installation.

Boot changes and stale attempts are synthetic negative tests; actual machine reboot, same-index/MAC reuse and arbitrary root writers are not qualified. Repeated point-in-time checks do not close the last-check/commit gap. Next: design separately enforced qualification expiry or recovery that remains effective after worker/controller loss, and test that combined failure before first live installation. Historical chrony sample-rejection causes remain unproven; use retained diagnostics if they recur. No phone/AWS/SSH/live-host/credential operation; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: restricted rescue independent of wrong primary allowances

Updated: 2026-10-04 (Asia/Tokyo).

PR #191 is merged/closed at `dfbb572a7f101b3f979951b085bc93395444393f`. Final head `72597b36c6ae7e27cfa216c0262f10845257198b` passed all five workflows and nineteen regression jobs (`37188298011`); DHCP DNS job `111394917716` reproduced all 37 records. This continuation rechecked the merge, final workflows and matching clean local/remote main. Accepted phone and observation evidence is not repeated.

The new fixed CI rescue profile uses a second static-address/static-neighbor veth for exact peer TCP/22 in both directions, with default-drop inet/netdev protection. It is independent of the exercised primary administration/DHCP/DNS allowance fault, not out-of-band from the kernel, namespace or owned tables. Candidate and ordinary fallback deliberately share incorrect primary peer addresses. A negative control requires both profiles to break existing/new primary administration and fresh DNS while the separate path survives. The separately fixed rescue material is not derived from either corrupted profile or discovered endpoints.

The existing independently supervised PID 1 worker retains its 22-second monotonic deadline and atomic two-table restoration. The controller dies by SIGKILL. Real networkd renewal/rebinding output must increment a dedicated drop counter and not reach the synthetic server; primary administration/DNS must fail while the rescue path still works. After exact restricted rescue restoration, require new DHCP ACK, actual lease/DNSEx, fresh A/AAAA including TCP, primary administration, unchanged daemon identities/unrelated table and revocation of old/new qualification. A second case lowers the separate rescue link after readiness; shape restoration and primary recovery must still occur, but unavailable rescue transport must yield BLOCKED/RESCUE_PATH_UNAVAILABLE with all gates false. No link repair or permission expansion is performed automatically.

Six rescue, seven chrony, six shared recovery, five DHCP DNS and four composition tests pass locally (28 total); git diff --check passes. The twentieth mandatory regression job has passed all fifteen real-kernel records across available/broken rescue cases, as recorded below. All five final-head workflows and twenty regression jobs must pass before integration; exact evidence and merge receipt belong in the PR. See [restricted rescue review](SECRET_CUSTODY_RESTRICTED_RESCUE_REVIEW.md).

Initial rescue head `18ad1e1ea9edf9c7c5d7a0e4b20ffe03e707e944`, regression `37189213031`, job `111397692130`, failed before daemon startup at 17:32:04 JST: the unrelated sentinel table omitted a separator after its nested chain. The emitted nft error identifies the closing table brace. Add the same chain separator used by the existing dynamic fixture; policy shape/isolation/client deadlines and all fifteen acceptance requirements remain unchanged. No rescue acceptance record passed on that initial head.

The initial runtime smoke `37189213111`, job `111397691920`, separately reported verification_failed:github.verify_ci at 17:31:49 JST. It reads latest completed main CI, not this PR's kernel test. Direct Actions GET (the commit helper only lists pull-request events) revealed post-merge main regression `37188611863` on `dfbb572a7f101b3f979951b085bc93395444393f` failed time job `111395857615`. At 17:21:40 JST its origin-prime preparation exceeded twelve seconds after successful IPv4 silent-primary failover/return. The primary was selected, both sources had reach 255/poll 0; primary cumulative RX/valid/good were 31/31/20, alternate 39/39/39. The preparation baseline and per-packet rejection reason were not retained, so the precise cause is unproven. Earlier PR #191 final CI and this PR's unchanged time job `111397692121` both passed. The prior PR acceptance statement remains correct; its later main push run did not pass.

One targeted diagnostic rerun of that failed main time job is authorized by the existing CI workflow scope and has been requested on a newly provisioned runner, with code/assertions/deadlines unchanged. Hypothesis: runner-dependent scheduling/sample acceptance may affect fresh-phase preparation. New information: whether the failure reproduces and the actual fresh-phase/client/server counters in the second run. Success requires all fifteen existing records including all four fresh preparations; a pass does not establish a root-cause fix. If it fails again, stop identical reruns and inspect the retained diagnostics. Do not weaken main verification or bypass the final CI gate. The historical preparation reliability limitation stays recorded regardless of that result.

The single diagnostic rerun (main regression `37188611863`, attempt 2, time job `111398307405`) passed all fifteen records at 17:37:07 JST without code/deadline changes. Fresh good-sample deltas (primary, alternate) were IPv4 silent (4,4), IPv4 origin (4,5), IPv6 silent (4,4), IPv6 origin (4,4), with actual poll 0 throughout. This is successful reproduction on another run, not a root-cause fix or a reliability guarantee. The failed attempt remains evidence. The changed fixture now retains the preparation baseline and bounded last ntpdata snapshots on failure, while preserving the original exception, four-good-sample gate and all time limits. One diagnostic regression test passes; seven chrony plus nineteen rescue/reused tests pass locally (26 total). Future recurrence must use these diagnostics rather than repeated identical reruns. Chrony preparation reliability remains an explicit follow-up alongside recovery identity/worker-loss tests.

Corrected grammar head `64a3ae63f9190036bd574cd46e44663dc7eb597c`, regression `37189615299`, rescue job `111398888857`, passed all eight available-path records, including the wrong-shared-fallback control, real DHCP/DNS/admin denial after controller death, independent restoration, actual ACK/fresh answers, usable-rescue verdict and owned cleanup. At 17:40:03 JST the second case failed before daemon startup with EADDRINUSE when reusing the wildcard administration listener. Both cases shared one process/network namespace; the helper's daemon accept threads can outlive socket context closure, but the exact retaining descriptor was not captured. Each case now runs in a separate bounded child process and fresh network namespace, and the parent waits for full process exit before the next case. One new unit guard rejects reuse of the parent namespace. No traffic, lifetime or verdict assertion is weakened; all fifteen records including the broken-link BLOCKED result remain mandatory. Five rescue, six recovery, five DHCP DNS, four composition and seven chrony tests pass locally (27 total). Failure diagnostics now preserve the original chrony exception even if an auxiliary diagnostic read fails; the existing diagnostic test covers both outcomes.

Head `3ff7ced5deaafa790f70c0a24036bacf3a6ce937`, regression `37189773966`, rescue job `111399353028`, again passed all eight available-path records and reached the broken-case baseline. It then timed out waiting only for a netdev DHCP drop. The journal shows real ACK/T1/T2 setup at 17:43:05 JST and bound-to-renewing at 17:43:13; the twelve-second wait ended at 17:43:21 before observing the later-layer count. The candidate also denies normal UDP output at inet, so netdev-only measurement cannot establish absence of DHCP activity. The correction adds a dedicated matching DHCP drop counter at inet as well, requires fresh non-regressing progress in either layer, prints both before/after counts, and still requires no server receipt, a live address, unfinished recovery and separate-path availability. The twelve-second measurement and 22-second recovery windows are unchanged. A new local test rejects unchanged/regressing counts and covers either observed layer.

The same head's time job `111399353040` passed IPv4 fully, then failed IPv6's existing five-second post-restore two-good-sample wait at 17:43:32 JST. That earlier phase had not used the new diagnostic helper, so its exact baseline/rejection cause remains missing. The unchanged three-second post-controller and five-second post-restore predicates now use the same bounded diagnostic wrapper and preserve original sample/selection/reach requirements and failures. No blind rerun or deadline extension is used. Six rescue, seven chrony and fifteen reused tests pass locally (28 total). Corrected-code acceptance is recorded below.

Corrected code head `14fcf826654b16c6fd311e190203fbcb3c4322d6` (tree `56f40d20f7eff67f30a22785cfb03449b6201d79`), regression `37190000878`, rescue job `111400011794`, passed all fifteen records and `SYNTHETIC_RESTRICTED_RESCUE_OK_NO_LIVE_APPLY` at 2026-10-04 17:47:41 JST. Both AVAILABLE and BROKEN cases measured DHCP drops `{inet: 0, netdev: 0}` to `{inet: 1, netdev: 0}` with no new server receipt: this run directly observed denial at the earlier inet hook. Both cases restored exact restricted shape, revoked old/new qualification, reacquired actual DHCP ACK/fresh DNS/primary administration and cleaned up all owned resources. AVAILABLE verified the separate existing/new/bidirectional path; BROKEN correctly returned BLOCKED/RESCUE_PATH_UNAVAILABLE despite successful shape/primary recovery. All verdict gates remained false. Kernel `6.17.0-1022-azure` and networkd/resolved/dbus hashes match PR #191's recorded binaries.

The same head's time job `111400011614` passed all fifteen records at 17:47:53 JST, with fresh primary/alternate good-sample deltas (4,4) in each of the four IPv4/IPv6 silent/origin preparations and poll 0 throughout. Chronyd/chronyc hashes and version 4.5 match the previous recorded binaries. This validates the changed diagnostic code and original acceptance in this run; it does not establish a fix for the missing historical rejection causes. Four other workflows had passed and the existing DHCPv6 lifecycle job was still running when this targeted evidence was recorded. All five final-documentation-head workflows and twenty regression jobs remain required before merging PR #192; exact final results and merge receipt belong in that PR. No additional identical diagnostic rerun is planned; any recurrence must use the new retained baseline/ntpdata evidence.

This starts from a pretested restricted CI anchor; initial installation from the live unfiltered baseline remains unqualified. TCP echo is administration transport evidence, not SSH authentication. No live second interface, rescue route, source approval or independent host recovery exists by implication. Persistent installation/reboot, worker death after readiness, stale interface/boot identity, non-cooperating writers, combined DHCPv6/RA/route faults and rescue-path repair remain outside scope. Next: bind recovery readiness to boot/interface identities and exercise worker loss after readiness before considering first-install rehearsal. No phone/AWS/SSH/live host/credential operation; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: caller-bound observation restart and stale-result rejection

Updated: 2026-10-04 (Asia/Tokyo).

PR #190 is merged/closed at `d5f3cf5cb5ed39ded6423522b4faa4ca3a6b0596`; final head `13712ab400fd0b4971aee4ed949208539ef9492e` passed all five workflows and nineteen regression jobs (`37179787609`). Final DHCP DNS job `111369842553` passed twelve standalone plus eighteen composed records; time job `111369842505` passed fifteen prepared-phase records. The exact historical chrony timeout cause remains unproven. This continuation rechecked the merge, final workflows and matching clean local/remote main; no accepted phone evidence is repeated.

The CI collector now pins the caller's expected boot, daemon PID/start/executable, namespace, cgroup, interface and private-bus identities before its first manager read and before publication. Lease/link versions remain a per-collection bracket, separate from daemon identity. The parent launches a collector, records its actual PID/start and publishes the request atomically; the collector checks its own identity. Consumption requires the exact request ID and collector instance, matching expected service identities and current file bracket, ordered integer monotonic times, a collection window of at most four seconds and request age of at most five seconds. Partial/legacy, different-attempt, expired, changed-identity and changed-bracket results are rejected. All review/apply/freshness/qualification/mutation gates remain false. This is CI plumbing, not a new production reader.

Eight new negative/contract tests plus five DHCP DNS, four composition and six resolver tests pass locally (23 total); git diff --check passes. The nineteenth regression job retains its original twelve standalone and eighteen composed records and adds seven mandatory acceptance records: valid caller binding; actual observer SIGKILL/restart with rejection of old complete/partial results; old sandbox cleanup; whole private networkd/resolved/bus replacement with rejection of old expected identities and old completed results; a newly bound collection of the same selected DNS facts plus fresh A/AAAA/admin; replacement cleanup; and peer/link/rule cleanup.

Code head `21ce5116c4ec3591685138150e9a0a0049308656`, regression `37188103326`, DHCP DNS job `111394316107`, passed all twelve standalone, eighteen composed and seven new restart records. The restart success marker appeared at 2026-10-04 17:13:36 JST (08:13:36 UTC runner log). Actual SIGKILL/restart rejected old completed and partial results. After verified teardown, a second real networkd/resolved/bus sandbox acquired the same selected DNS facts; the old expected identity caused the collector to exit before publishing any partial/complete file, and the old completed result was rejected against the new identity. A new caller-bound collection succeeded, with fresh A/AAAA/TCP upstream events, administration, unchanged policy shapes and complete cleanup. The job reported kernel `6.17.0-1022-azure` and the same installed binary hashes as PR #189/#190. No failure or retry occurred in this code-head acceptance. Four other workflows were successful; the existing DHCPv6 lifecycle job was still running when this evidence was recorded. All five workflows and nineteen regression jobs on the final documentation head remain the integration gate; exact final results and merge receipt belong in PR #191.

Whole private-sandbox replacement is the intended restart scope, not an individual service restart retaining the same private bus/mount. Synthetic cases exercise same-PID/different-start and identity/clock changes; real kernel PID reuse and machine reboot are not claimed. Equal brackets and short age do not establish atomicity, authenticated origin, production freshness, protection from arbitrary root writers, or single-use replay protection inside one accepted attempt. The immutable live dependency reader is unchanged and uninvoked. First restricted installation, independent rescue for wrong shared allowances, reboot, non-cooperating writers and recovery-worker death after readiness remain unqualified. Next: review and test an independent restricted rescue path under deliberately wrong shared allowances before considering initial installation. No phone/AWS/SSH/live host/credential operation; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: DHCP DNS changes across independent restricted recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #189 merged at `d68820cd22d848267f5060497ba54b0378d7b1a0`. Final head `8fb75fe66e6f39cc2330fc47c190c1868593be7c` passed all five workflows and nineteen regression jobs (`37178146385`); DHCP DNS job `111364997322` reproduced twelve acceptance records, and resolver job `111364997370` reproduced eighteen. This continuation rechecked merged/closed state, final workflows and matching clean local/remote main.

This slice composes the real private networkd/resolved DHCP DNS fixture with the independent PID 1 recovery worker. A fixed `dhcp-dns` profile restores the exact DHCP DNS maintenance tables, including TCP DNS and excluding unused NTP. Require fresh stub answers after controller SIGKILL, then an actual DHCP renewal to the unapproved DNS source while qualification remains active. Actual observations must require review with all gates false; new DNS output drops and unchanged upstream events prove denial. Independent two-table restoration must revoke old/new TCP qualification while preserving administration and the unchanged DNS configuration. Require a fresh denial after restoration, then actual DHCP renewal back to the approved source, fresh answers and unchanged daemon identities. The complete original twelve-record observation/expiry suite continues under the restored policy. Six added composition records plus the twelve base records are mandatory; the original standalone run remains a separate mandatory step in the same nineteenth job.

Four composition, five DHCP DNS, six shared recovery, six resolver and six chrony tests pass locally (27 total); git diff --check passes.

Corrected DNS code head `7466aba9da805d768ed9d58403edaa8ea8e125fb`, regression `37179484253`, DHCP DNS job `111368947973`, passed all twelve standalone plus eighteen composed acceptance records and `SYNTHETIC_DHCP_DNS_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY` at 14:20:57 JST. The installed binaries/kernel match PR #189. In the real composed run, A increased active transactions 0→1 before restoration and distinct AAAA increased 1→2 afterward; approved-source renewal drained the work and fresh A/AAAA answers succeeded with unchanged daemons/admin. The restored policy subsequently passed the full interrupted/mixed collection, source-change, return and real expiry lifecycle. This proves the exercised order, not simultaneous DHCP mutation and firewall restoration. The full run did not pass because the separate existing chrony job failed as recorded below.

On the same head/run, time job `111368947964` passed IPv4 and IPv6 post-restore samples plus IPv6 silent-primary failover, then exceeded the unchanged 35-second IPv6 wrong-origin failover bound. Its log shows alternate selection at 14:19:11 JST and primary return at 14:19:12, but omits reach, poll and accepted-measurement state at timeout; the historical cause is not established. Existing code started the next fault as soon as primary selection returned, which can reuse old samples. Phase carryover/insufficient fresh alternate samples is a hypothesis to test, not a retroactive diagnosis. The changed fixture requires four fresh good measurements from BOTH sources with primary selected/reachable before each fault (12-second bounded preparation), reads one source-state snapshot per failover predicate, records poll/reach and client/server counters, and preserves the original 35-second failover/20-second return bounds and invalid-response rejection. The same unprivileged clockless client survives throughout; no reset, forced selection or packet-filter change is introduced. One new local test rejects old/one-sided/unreachable measurements. Six chrony plus twenty-one DNS/recovery/resolver tests pass (27 total). Current-head real fresh-phase acceptance and all five workflows/nineteen regression jobs remain required; exact final results and merge receipt belong in PR #190. A later successful prepared-phase run does not prove the missing historical state.

Initial head `c23e575df48f5d068b840aae52e9286293088ed2`, regression `37179257704`, job `111368290742`, passed all twelve standalone records plus fresh queries after controller death, actual changed-DNS denial under qualification and PID 1 restoration with old/new qualification denial. It then failed while waiting fifteen seconds for all transactions to disappear with the unapproved DNS still configured. The retained journal explicitly shows timeout/retry and TCP fallback for transaction 48673 at 14:14:56 JST; a one-second UDP client timeout did not cancel the resolver's continuing work. The earlier source-return drain result does not apply while the source stays blocked. The correction keeps the original A denial, requires its one pending transaction after restoration, then issues distinct AAAA and requires actual active count 1→2 plus a new output drop and no peer receipt. This prevents coalesced/cached failure from being accepted without assuming premature drain. After actual DHCP return to the approved source, the original fifteen-second zero-transaction bound and fresh A/AAAA answer requirements remain. A new local negative test rejects unchanged active count; four composition tests pass (21 total with reused suites). No firewall/client deadline was relaxed and no daemon restart or blind rerun is used. Corrected DNS acceptance subsequently passed as recorded above; the full final CI gate remains required. All five final-head workflows and nineteen regression jobs remain required before integration. See [DHCP DNS review](SECRET_CUSTODY_DHCP_DNS_REVIEW.md); exact final evidence and merge receipt belong in the PR.

This does not prove that DHCP mutation and firewall restoration occur in the same kernel transaction, or qualify production observation/freshness, DHCPv6 DNS, NSS, observer restart/reuse with changed daemon identities, independent rescue for wrong shared allowances, first restricted installation, reboot, non-cooperating writers or recovery-worker death after readiness. Next: bind observation restart/reuse to the expected daemon identities and reject stale completed/partial results; keep the first-install/rescue boundary explicit. Accepted phone evidence stays accepted. No phone/AWS/SSH/live host/credential operation; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: actual DHCPv4 DNS delivery and interrupted observation

Updated: 2026-10-04 (Asia/Tokyo).

PR #188 merged at `b364f4fcd2400dfa436cb0e995cbec2b0f1ab2a3`. Final head `afc2a2bfe2362e1865af0d6bca852c9316753dab` passed all five workflows and eighteen regression jobs (`37174593370`); final resolver job `111354474154` reproduced all eighteen acceptance records. This continuation rechecked merged/closed state, the final workflows and matching clean local/remote main.

This slice shares a private mount/network/runtime and D-Bus between actual installed networkd and resolved. A bounded synthetic DHCPv4 server supplies option 6; real renewals change the DNS address and restore it, and real lease expiry withdraws it. No SetLinkDNS is used. Require the private lease, actual DNSEx and networkd Describe origin to agree, then query the real stub and observe upstream answers. Unapproved DHCP-provided DNS must be denied without changing either firewall table. Existing administration and the same daemon identities must survive source changes; expiry intentionally removes address/route reachability. Separate collection processes bind a unique attempt ID, monotonic window, boot/process/start/namespace/interface/bus identities and private lease/link file versions. Real SIGKILL after the first read must leave no complete observation. A real renewal between reads must reject the mixed collection. Completion is fixture evidence only: matching brackets do not prove atomicity or live freshness, and all apply/qualification/freshness gates stay false.

Five new, six resolver, fourteen comparison and five DHCP tests pass locally (30 total). A nineteenth mandatory regression job and twelve kernel acceptance records are added. Code head `7638dcc6000d9921752333caf3f0f6b4293a23c8`, regression `37178001953`, new job `111364577877`, passed all twelve acceptance records and `SYNTHETIC_DHCP_DNS_OBSERVATION_OK_NO_LIVE_APPLY` at 04:48:17 UTC on October 4 (13:48 JST). Installed systemd is `255.4-1ubuntu8.17`, kernel `6.17.0-1022-azure`; networkd SHA-256 `12e65fbae70b7cf17a84299c5323eb0735309c2891d3caea321a4ad2093f8c19`, resolved `5e694042ba4bad6c29584334eeb5b06c6abdab17a84d96718dd286e41bff322d`, dbus-daemon `8c479f1fcddfd6693c736ce541da0955f6752834bdeeef4b928e27f5e974c247`. Real acquisition, origin agreement, stub A/AAAA/TCP, SIGKILL partial rejection, renewal-during-collection rejection, unapproved-source denial without widening, approved return with unchanged daemon identities/admin, expiry withdrawal and full cleanup passed. Four completed collection windows were 24.878015, 23.923450, 24.856132 and 23.621945 milliseconds; three had matching selected facts and the expired observation was blocked as EMPTY_RESOLVER_SET. The separate resolver job `111364577855` also reproduced all eighteen previous acceptance records. Other workflows/jobs were still running when this targeted evidence was recorded; all five final-head workflows and nineteen regression jobs remain the merge gate. No failure/retry occurred in this code-head acceptance. See [DHCP DNS observation review](SECRET_CUSTODY_DHCP_DNS_REVIEW.md). Exact final results and merge receipt belong in the PR.

This qualifies neither DHCPv6 DNS nor NSS, production collection, authenticated origin, atomic cross-manager snapshots, first restricted installation, independent rescue from wrong shared allowances, reboot, non-cooperating writers, or worker death after readiness. The collection ID is not a DHCP protocol generation. The prior resolver recovery fixture remains separately mandatory; combined DHCP-DNS plus controller-death restoration is still untested. Next: compose actual DHCP-delivered DNS changes with independent restoration and review bounded observer restart/reuse under changed daemon identities. Accepted phone evidence is not repeated. No phone/AWS/SSH/live host/credential operation; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: isolated real resolver cache and source switching

Updated: 2026-10-04 (Asia/Tokyo).

PR #187 merged at `2cf71d9acae31fb444503fbea77c55a9ea03206a`. Final head `c4b04fed4121cdcadf52c391455c5bd4684dee54` passed all five workflows and seventeen regression jobs (`37171989540`). Dependency job `111346644090` passed fourteen comparison tests, ten reader tests and the separate Ubuntu reader check. This continuation rechecked merged/closed status, final workflows and matching clean local/remote main.

The new CI fixture runs actual systemd-resolved and a private D-Bus daemon in a dedicated mount/network environment with generated read-only configuration and private runtime. It queries the actual stub, measures A/AAAA cache hits and real TTL expiry using upstream events, tests upstream truncation/TCP fallback and stub TCP, composes controller-death restoration with the same resolver, and changes private per-link DNS to an unapproved source without changing firewall rules. Require actual DNSEx readback, bounded failure and output drops with no unapproved server receipt, approved-source return, administration survival and full cleanup. Eighteen acceptance records and the new eighteenth mandatory regression job are required. Six local resolver tests plus five DNS and six shared recovery tests pass (17 total). Corrected code head `e9289e5a9df87f10eddb85230d0de0dbffa3e522`, regression `37174444054`, resolver job `111354030300`, passed all eighteen acceptance records and `SYNTHETIC_RESOLVED_CACHE_SWITCH_RECOVERY_OK_NO_LIVE_APPLY` at 03:35:14 UTC on October 4 (12:35 JST). The actual package reports systemd `255.4-1ubuntu8.17`, kernel `6.17.0-1022-azure`; resolved SHA-256 `5e694042ba4bad6c29584334eeb5b06c6abdab17a84d96718dd286e41bff322d`, dbus-daemon SHA-256 `8c479f1fcddfd6693c736ce541da0955f6752834bdeeef4b928e27f5e974c247`. Both families passed private bus/config/source readback, warm A/AAAA cache with unchanged upstream events, changed answers after real TTL expiry, UDP truncation/TCP and TCP stub cache responses, fresh queries after controller death and after independent restoration, unapproved-source denial without rule changes, source return, administration and full cleanup. Actual pending transaction count was one in each family; after source restoration, zero was reached in 9.008 seconds for IPv4 and 9.203 seconds for IPv6, followed by fresh same-name A/AAAA upstream events. This confirms delayed drain in the reproduced scenario, not instantaneous recovery or a guarantee for other versions. Other code-head jobs were still running when this targeted evidence was recorded. All five workflows and eighteen regression jobs on the final head remain mandatory; exact final results and merge receipt belong in PR #188. See [resolver cache review](SECRET_CUSTODY_RESOLVED_CACHE_REVIEW.md). All five workflows and eighteen regression jobs on the final head remain the merge gate; exact final evidence belongs in the PR.

Initial head `51bcca67c3d792ff0666580ff1d3ab91a4178654`, regression `37174153597`, resolver job `111353154685`, passed direct upstream baseline then stopped before daemon startup: `/run/systemd` already existed in the private runtime and exclusive mkdir raised FileExistsError. The private mount/runtime/config guards had passed. The fixture now accepts an existing real directory after lstat, but rejects symlinks/files; a real temporary-filesystem regression covers these cases. Six resolver plus eleven reused tests pass (17 total). No isolation guard, deadline or network assertion was relaxed. Corrected real-resolver acceptance subsequently passed as recorded above; final complete CI remains required.

Second head `c5f7197dc1b626614471137e24e8de7fde7ab4d5`, regression `37174244369`, resolver job `111353435221`, passed isolation plus IPv4 cache/TTL, truncation/TCP, controller-death and restored fresh queries, and unapproved-source denial. It failed the immediate same-name query after restoring the approved source. The log shows the denied UDP attempt falling back to TCP and the subsequent query remaining in processing; upstream v255 uses a ten-second TCP transaction timeout. A pending old transaction is the hypothesis to measure, not an assertion that configuration readback guarantees immediate recovery. The changed test requires actual positive TransactionStatistics after client timeout, restores the approved source, waits at most fifteen seconds for actual zero active transactions, then flushes only the private cache and requires fresh A/AAAA upstream events. Existing one-second client queries, isolation, policy shape and deny assertions are unchanged. If transactions do not drain, the test fails; no daemon restart or blind retry is used. Corrected acceptance subsequently passed as recorded above; final complete CI remains required.

This uses explicit private SetLinkDNS, not actual DHCP-to-resolved delivery or NSS integration. No production DNS, cache, transport or initial installation is qualified. Next: actual isolated DHCP-provided DNS changes and generation/identity-bound observation, including interrupted collection. Initial restricted installation, independent rescue for wrong shared allowances, reboot, non-cooperating writers and worker death after readiness remain blocked. Do not repeat accepted phone evidence. Installed Ubuntu DHCPv6 remains unqualified. No phone/AWS/SSH/live host/credential action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: DNS observation reconciliation and first-install review

Updated: 2026-10-04 (Asia/Tokyo).

PR #186 merged at `82e6a4f65b479cc85798b1ba94af6c71771e3ef1`. Final head `0cf7e7b53cb7263977bd642cd943db3899a76a5a` passed all five workflows and seventeen regression jobs (`37167335331`); final time job `111332909527` reproduced all fifteen acceptance records. This continuation rechecked the merged PR, final workflows and matching clean local/remote main.

This slice adds a pure comparison of selected private dependency-reader facts. Existing-parser synthetic inputs test resolved/networkd agreement, endpoint addition/removal/change, provider/interface change, default-port representation, unknown/incomplete data and output redaction. Matching observations never authorize endpoints or establish freshness. All decisions retain qualification/mutation/apply/freshness gates false; there is no host reader invocation, policy renderer or apply adapter. Fourteen new comparison tests plus ten existing reader tests pass locally (24 total). The comparison tests are mandatory in the existing dependency CI job; all five final-head workflows and seventeen regression jobs remain the merge gate. Exact final results and merge receipt belong in the PR.

The [DNS reconciliation and first-install review](SECRET_CUSTODY_DNS_RECONCILIATION_REVIEW.md) separates implemented comparison from proposed real-resolver and first-install acceptance. No current report has trustworthy freshness, atomic collection or effective resolver-transport/routing coverage. No live resolver or initial maintenance installation has become qualified. A separately restricted rescue profile and a recovery path demonstrated under deliberately wrong candidate allowances are prerequisites; a timer restoring the same wrong allowance is insufficient. No automatic unfiltered rollback or broader access is introduced.

Next: isolate a real resolver with private IPC/config/runtime, then verify client-path queries, cache/TTL behavior, changed DHCP DNS and denial without widening rules. First-install independent rescue, reboot, non-cooperating writers and worker death after readiness remain blocked. Do not repeat the accepted phone reader observation. Installed Ubuntu DHCPv6 remains unqualified. No phone/AWS/SSH/live host/credential operation; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: chrony source selection without host clock control

Updated: 2026-10-04 (Asia/Tokyo).

PR #185 merged at `1e534bed3cb3b27720cbd5385942e2e59be208da`. Final head `1ed064012fd25d6fdf15668e6445face7f8d356a` passed all five workflows and sixteen regression jobs (`37165380672`); final DNS job `111327095363` reproduced all sixteen acceptance records. This continuation rechecked the merge, exact final workflows and matching clean local/remote main. Fixed DNS evidence remains accepted with its recorded limits.

The new isolated time fixture uses real chronyd with `-x` and uid/gid 65534, empty capability sets/bounding set and NoNewPrivs. It extracts the Ubuntu chrony package into an owned CI directory without package installation or service scripts; version and executable hashes are recorded. Only two fixed synthetic NTP sources per family are approved. Require primary selection, new accepted measurements after controller SIGKILL and after PID 1 two-table restoration, automatic alternate selection when the primary becomes silent or sends wrong originate timestamps, primary return, and denial of an unapproved source/TCP transport. The same client and administration socket persist across recovery. Read actual chronyc selection/reach and accepted-measurement counters, not just UDP receipt. Five NTP/report/guard and six shared recovery tests pass. Corrected code head `f13291df52c550ed5ae19d46282e3ba91eaf9ef5`, regression `37167200665`, time job `111332494299`, passed all fifteen acceptance records and `SYNTHETIC_TIME_RECOVERY_OK_NO_CLOCK_OR_LIVE_APPLY` at 01:11:47 UTC on October 4 (10:11 JST). Ubuntu package `4.5-1ubuntu4.2`, chronyd 4.5, kernel `6.17.0-1022-azure`; chronyd SHA-256 `7a834e478d8a904c39a348606a5d0ac58fd1ccbca24f333a8170c786af8ca508`, chronyc SHA-256 `271ea54c67206559437bd299d0e08c9e3d42ee6be322b1722e76311cd5d9df8d`. Both families selected the preferred primary without clock capabilities, accepted fresh measurements after controller death and independent restoration, selected the approved alternate for silence and wrong-origin replies, returned to primary, denied the unapproved source/TCP transport, preserved administration and qualification denial, and cleaned up clients, files, links and rules. Other code-head jobs were still running when this targeted evidence was recorded. All five workflows and seventeen regression jobs for the final head remain mandatory; exact final evidence and merge receipt belong in PR #186. See [time recovery review](SECRET_CUSTODY_TIME_RECOVERY_REVIEW.md). All five final-head workflows and seventeen regression jobs are required before merge.

Initial head `dd847428974c748d5472f3b2dd47b865b30e6e0e`, regression `37166897486`, time job `111331572656`, passed baseline and five IPv4 records, including accepted measurements after restoration and alternate selection for silent/wrong-origin replies. It stopped at the unapproved UDP probe: `sendto` returned `EPERM` immediately, but the helper handled only receive timeout. The helper now accepts only EPERM or timeout for an expected denial; positive probes, unrelated errors and any received reply still fail. A local regression covers these distinctions. The actual output-drop increment and unchanged peer counters remain mandatory. Five time tests plus six recovery tests pass. Corrected CI subsequently passed both families and complete cleanup as recorded above; the final complete CI gate remains required.

No host clock setting, host time-service installation/configuration, external time server, NTS/cryptographic authentication, accuracy/UTC traceability, DNS discovery or combined DHCP/RA/DNS/PMTU lifecycle is qualified. Next: resolver integration/discovery and first restricted maintenance installation/recovery design. Nine observed live time entries do not become an approved allowlist. Installed Ubuntu DHCPv6 remains unqualified. Worker death after readiness, non-cooperating root writers, reboot and wrong shared allowlists remain unresolved. No phone/AWS/SSH/live host/credential action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: fixed DNS transport through independent recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #184 merged at `99110f436a3cb8ac1bd1b94342d09e0fdbf43144`. Final corrected head `231acd82c86d806480f47b883fed1412cdc47fa1` passed all five workflows and fifteen regression jobs (`37163379851`). Its PMTU job `111321280325` passed ten standalone and sixteen recovery records. H2d job `111321280201` passed fourteen local and five real-systemd tests including intentional collection before stale reset. This continuation rechecked the merge, exact final workflows and matching clean local/remote main. The earlier reset failure remains historical evidence; its omitted state is not retroactively proved by the reproduced race.

This slice adds mandatory `custody-dns-recovery` with installed `dig` and bounded synthetic DNS servers in a private dual-stack network. Require actual A/AAAA answers over UDP, explicit TCP and UDP truncation→TCP fallback under maintenance, after controller SIGKILL with qualification active, and after independent two-table restoration. A silent approved server must cause a bounded failed query; an unapproved changed endpoint must remain denied over UDP/TCP; re-enabling the original server with changed data must yield fresh answers. Actual unsolicited replies from the approved address must reach netdev then be denied by inet conntrack, and wrong-source replies must be denied at netdev. Existing/new administration, old/new qualification denial, final rule shape and cleanup remain required. Fifteen local DNS/recovery helper tests pass. Corrected code head `6d1e5e762799a8f3a3a145d18e6e299134645625`, regression `37165231450`, DNS job `111326663169`, passed all sixteen acceptance records and `SYNTHETIC_DNS_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY` at 00:32:22 UTC on October 4 (09:32 JST). Installed client identity was `DiG 9.18.39-0ubuntu0.24.04.7-Ubuntu`, kernel `6.17.0-1022-azure`. Actual A/AAAA UDP, TCP and truncation fallback passed in maintenance, while the controller was dead, and after PID 1 restoration. Both families passed bounded outage, changed-endpoint denial, fresh changed answers, unsolicited/wrong-source rejection and cleanup. The other code-head jobs were still running when this targeted evidence was recorded; all five workflows and sixteen regression jobs for the final head remain mandatory. Exact final results and merge receipt belong in PR #185. See [DNS recovery review](SECRET_CUSTODY_DNS_RECOVERY_REVIEW.md). All five final-head workflows and sixteen regression jobs are the integration gate; exact final evidence and merge receipt belong in the PR.

Initial head `2973efc9ff5b19d1dad02148afbf6899ded00519`, regression `37165073764`, DNS job `111326222401`, passed baseline, both maintenance/qualification transport sets, independent restoration and IPv4 post-restoration DNS. It then failed the expected-outage assertion: dig correctly returned exit 9 (no response), but its single-semicolon banner was incorrectly counted as an answer. The parser now excludes both single/double-semicolon diagnostics and requires exactly exit 9 plus no answer lines for negative queries. A regression test rejects arbitrary exit 1, success-without-answer and a failed query containing an answer. Version reporting now checks both stdout/stderr and requires a bounded `DiG ` identity. The changed conditions are result classification/version capture only; no network assertion is skipped. Five DNS and ten helper tests pass (15 total); Corrected DNS acceptance passed as recorded above; the final complete CI gate remains required.

This qualifies fixed DNS transport only, not systemd-resolved/NSS, cache or TTL expiry, automatic resolver discovery/failover, DNSSEC, encrypted DNS, or simultaneous DHCP/RA/PMTU lifecycles. No resolver configuration or host clock is changed. Next: synthetic time-source behavior, resolver integration/discovery design and first restricted maintenance installation/recovery design. Installed Ubuntu DHCPv6 remains unqualified. Worker death after the final readiness check, non-cooperating root writers, reboot and wrong shared allowlists remain unresolved. Completed phone evidence stays accepted. No phone/AWS/SSH/live host/credential action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: routed PMTU after independent restricted recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #183 merged at `98f569e29ac7e5b862f5d298704281164ee6121c`. Its final head `1b08ac107d4ad2bfd4e04e478961d0961bbd40d5` passed all five workflows and fifteen regression jobs. Merge state, final workflows and matching clean local/remote main were rechecked on this continuation; all twelve DHCPv6 composition acceptance records remain accepted.

This slice composes routed IPv4/IPv6 PMTU with the existing independent PID 1 recovery worker. Fixed qualification profiles add only the documentation peer's TCP/443 tuple in both owned tables. After controller SIGKILL, actual qualification exchange must succeed; independent atomic restoration must revoke old/new qualification while existing management/bulk and new management connections work. The existing bulk socket must still report PMTU 1500 after restoration. The original forged-error rejection and real router 1500→1280 blocked-PTB stall/same-flow recovery then run under the restored policy. Final shape and old/new denial are checked again. The original standalone fixture stays mandatory. See [PMTU recovery review](SECRET_CUSTODY_PMTU_RECOVERY_REVIEW.md). Code head `ed5e49640688e2384ae95016a170be795b271dd8` passed all sixteen composition acceptance records in regression run `37162795373`, PMTU job `111319533837`, on kernel `6.17.0-1022-azure`. The ten standalone records also passed. For both families the independently restored bulk socket still reported PMTU 1500; subsequent real router errors quoted 1500-byte packets and announced MTU 1280. Blocking them stalled the transfer, and admitting them delivered all 65,536 bytes on the same socket. IPv4 MSS changed 1448→1228, IPv6 1428→1208, with actual unfragmented wire packet lengths at most 1280 and 1280 observed. Post-restoration forged-error rejection, restored shape, old/new qualification denial, management survival and cleanup passed. The composition ended with `SYNTHETIC_PMTU_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY` at 23:46:31 UTC on October 3 (08:46 JST on October 4). Fourteen local tests and `git diff --check` passed. All five code-head workflows succeeded, including all fifteen regression jobs in run `37162795373`. All five final-head workflows are required before integration; final run IDs and merge receipt belong in PR #184.

The first evidence-only head `d56f6fb9c4d21776e94cacafffad3efbb7c81853` passed PMTU again but failed existing H2d job `111320627742` in run `37163162130`. Invalid probe output was correctly rejected as `PROCESS_EVIDENCE_INVALID`; cleanup then replaced that error with `PROCESS_RESET_FAILED`. The log does not contain reset stderr/state, so transient-unit collection between ownership readback and reset is a hypothesis, not a proven diagnosis of that historical run. H2d cleanup now tolerates a nonzero reset only when a new manager readback verifies `LoadState=not-found`; existing directory/cgroup absence checks still run. A retained or unreadable unit still fails. Two local tests cover absent/retained units and remaining cgroups. A real-systemd test forces collection between readback and the actual stale reset, requires its nonzero exit, preserves the original rejection and verifies cleanup. The probe exits nonzero on SIGTERM so the test retains the failed unit until intentional collection. Fourteen H2d local tests pass (28 total with the PMTU/helper checks). Corrected-head CI remains required; no assertion was skipped and no blind rerun was used.

Next: DNS/time protocol lifecycle and first restricted maintenance installation/recovery design. Static routes/neighbors here do not establish simultaneous DHCP/RA/PMTU composition or a route change during the restoration transaction. Installed Ubuntu DHCPv6 remains unqualified. Worker death after the final readiness check, non-cooperating root writers, reboot and a wrong shared allowlist remain unresolved. Completed phone evidence remains accepted. No phone/AWS/SSH/live host/credential operation; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: patched DHCPv6 with independent restricted recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #182 merged at `a8cb390df54b1c183623cfee31d7c905eef8dc39`. Final head `a8fb90bfbec4a575a144952805fe2d0c1d6591b0` passed all five workflows and fifteen regression jobs. GitHub merge and final workflows were rechecked on this continuation; its seventeen dynamic-recovery acceptance records remain accepted.

The next slice adds a fixed DHCPv6 profile to the independent PID 1 worker, using only the previously qualified pinned patched CI networkd build. A real Renew must refresh the lease while the controller is dead and qualification is active; the worker then atomically restores inet and netdev, denying established/new qualification traffic while preserving administration. The original complete lifecycle is reused after restore, with a fresh event window for Renew, alternate-DUID Rebind/adoption and lease expiry while RA routing remains. A post-restore wrong-source frame is rejected. The original-client defect control and standalone patched lifecycle remain mandatory. Seventeen local composition/helper tests plus four builder/provenance tests pass (21 total); all five final-head workflows are required before integration. See [DHCPv6 recovery review](SECRET_CUSTODY_DHCPV6_RECOVERY_REVIEW.md).

Initial PR #183 head `54530d4ce47f13850da3fd8a904bfd9b750fe1fc` failed before compilation in run `37161194778`, job `111314797928`: `PINNED_CLIENT_INPUT_MISMATCH`. All three Ubuntu downloads still match their original hashes. The GitHub-generated fix patch changed only its index abbreviations from 11 to 12 hex digits; restoring the 11-digit representation exactly reproduces original SHA-256 `b581a4c784a89648f8a8f25866a2b66ad57e54e6644a3ab2c8b6fe75fef86ffb`. The current generated patch hashes to `f67ad156f3ec7e005cbdeb7975c5f7af201e2ac081714ea9a6d348d465743667`; the official commit API confirms the same one-line getter fix. The original reviewed bytes are now vendored in `tests/fixtures/dhcpv6-t2-fix.patch`. No pin or source change is accepted automatically: the old SHA check and exact applied one-line comparison remain mandatory. The changed condition is local immutable patch input rather than GitHub's generated representation. Corrected code head `27dd63ef9bc003c04c7e2f62e58da1418bd988a7` then passed the actual composition and all five workflows. Regression run `37161487535` passed all fifteen jobs; DHCPv6 job `111315666049` passed both original/standalone controls and all twelve composition acceptance records, ending in `SYNTHETIC_DHCP6_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY`. The kernel was `6.17.0-1022-azure`. The independent restoration completed at 23:24:42 UTC, fresh post-restoration Renew at 23:24:44, alternate-DUID Rebind/adoption at 23:25:18 and expiry/final denial at 23:26:06. Owned-build cleanup succeeded and the installed networkd SHA-256 was unchanged. Final-head workflow evidence and merge receipt belong in PR #183.

Next is routed IPv4/IPv6 PMTU recovery composition. Installed Ubuntu DHCPv6 remains unqualified. DNS/time lifecycle, worker death after the last readiness check, non-cooperating root writers, reboot, first maintenance installation and a wrong shared allowlist remain unresolved. Completed phone observations stay accepted. No AWS/SSH/live host/credential operation; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: dynamic configuration with independent restricted recovery

Updated: 2026-10-03 (Asia/Tokyo).

PR #181 is merged at `1dd5666d779d82793b63d4a838b023ce1247d7ed`. Final head `f43ecb26969555a49a78a27e2e83ca30c784ce82` passed all five workflows and all fourteen regression jobs; this continuation rechecked the merge and workflow results against GitHub. Its actual IPv4/IPv6 routed PMTU evidence remains accepted.

PR #182 adds mandatory `custody-dynamic-recovery`, which composes installed networkd DHCPv4 and IPv6 RA/SLAAC/ND, in separate private networks, with PID 1 supervised recovery. Both inet and netdev tables are replaced in one nft transaction. The controller dies by SIGKILL; actual renewal/RA refresh must continue during qualification and after restricted restoration, existing/new administration must survive, and old/new qualification connections must fail. Real worker death before apply, controller death before apply, and independent drift in either table are negative cases. Shape comparisons ignore only handles and counter measurements, so legitimate packet counts cannot masquerade as policy drift. See [dynamic recovery review](SECRET_CUSTODY_DYNAMIC_RECOVERY_REVIEW.md). Code head `69ae85206d5bc193de6f538af2df549f959c16d0` passed all five workflows on its first run; regression `37128722659` passed all fifteen jobs. Dynamic recovery job `111219298078` passed all seventeen acceptance records (eight IPv4, nine IPv6) and `SYNTHETIC_DYNAMIC_RECOVERY_OK_NO_LIVE_APPLY`, using kernel `6.17.0-1022-azure` and installed networkd `255.4-1ubuntu8.17`. This success applies to DHCPv4 and RA/ND, not DHCPv6. Actual post-restoration DHCP Renew/Rebind, RA refresh/ND/expiry, worker/controller death cases, both-table drift and cleanup all passed without skipped assertions. Six new local tests and thirteen reused-helper tests also pass. All five final-head workflows must pass before integration; final evidence and merge receipt belong in PR #182.

This slice does not combine DHCPv6 or routed PMTU with recovery yet; these are the next composition targets. Installed Ubuntu DHCPv6 remains unqualified, while the separate pinned patched CI build remains qualified only in its recorded scope. DNS/time lifecycle, worker death after the last readiness check, concurrent non-cooperating root writers, reboot, first maintenance installation and a wrong shared administration allowlist remain unresolved. Completed phone evidence stays accepted. No phone/AWS/SSH/live host changes or credential use; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: real routed IPv4/IPv6 PMTU fixture

Updated: 2026-10-03 (Asia/Tokyo).

PR #180 merged at `c64253ff9443a19b6fa2c0964e9c4a75c0e34d07`. All five workflows for final head `c0affba6344e3a3589e4fe01bef6c3cb16dcb7b9` succeeded, rechecked on this continuation. Its success qualifies only the pinned patched CI build; installed Ubuntu 8.17 DHCPv6 remains unqualified.

PR #181 adds mandatory `custody-routed-pmtu`. Code head `a0e599ec6dde248882980182c7325cc92ec4b9ba`, regression run `37121414940`, job `111198105956`, passed all ten acceptance records and `SYNTHETIC_ROUTED_PMTU_OK_NO_LIVE_APPLY` on kernel `6.17.0-1022-azure`. Both IPv4/IPv6 real routers emitted valid errors quoting 1500-byte TCP packets and announcing MTU 1280. Blocking those errors stalled the queued transfer; admitting only RELATED PMTU errors recovered the same 65,536-byte transfer. Connected MTU and TCP_INFO PMTU read 1500 then 1280; MSS changed 1448→1228 for IPv4 and 1428→1208 for IPv6. Receiver packet lengths were at most 1280, with a 1280-byte packet observed. Wrong source/code, unrelated quoted flow and out-of-window quoted TCP sequence rejection all passed, including the kernel sequence-rejection counter. TCP/443 stayed denied, existing/new administration remained usable, and namespace/process/link/rule cleanup passed. All fourteen regression jobs and all five code-head workflows succeeded. Four new and three shared-helper local tests pass. See [PMTU review](SECRET_CUSTODY_PMTU_REVIEW.md). All five final-head workflows must pass before integration; final results and merge receipt belong in PR #181.

The first PMTU head `8db90623c103fef7c85cf1bf164e8bb943d24c89` failed router setup in run `37121343744`, job `111197907590`: a missing separator after the nested nft chain produced an explicit parser error. The corrected separator/newline was the changed condition; the next run exercised every required assertion successfully. No PMTU success was claimed from the initial setup failure and no failed assertion was skipped.

This is fixed isolated PMTU qualification, separate from DHCP/RA and rollback. Next compose qualified dynamic controls with independently supervised restricted recovery. DNS/time lifecycle, a fixed live DHCPv6 deployment candidate, first restricted maintenance installation and wrong shared allowlist recovery remain unresolved. Completed phone observations remain accepted. No phone/AWS/SSH/live host action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: patched DHCPv6 CI lifecycle

Updated: 2026-10-03 (Asia/Tokyo).

PR #179 merged at `e805038a5c1404c260ab1a63a55726c81ec26810`; its IPv6 RA/ND/DAD evidence remains accepted. PR #180 adds paired real networkd source builds in isolated CI. Code head `e066c8c97f086df0f6cc0900337df2a402583b9b` passed all five workflows. Regression run `37118721668`, DHCPv6 job `111190467251`, built both clients, confirmed the typed defect in the original, and passed all eight patched-client acceptance records plus `SYNTHETIC_DHCP6_LIFECYCLE_OK_NO_LIVE_APPLY` on kernel `6.17.0-1022-azure`. The patched client acquired its IA_NA address, reported separate timers, refreshed its actual lease, adopted the alternate DUID on the next Renew, preserved administration transport, expired the address while RA routing remained, and cleaned up. All thirteen regression jobs passed. Both root-owned client builds were removed; the installed networkd SHA-256 remained unchanged before and after.

The qualification target is explicitly the minimal custom Ubuntu 255.4-1ubuntu8.17 source build containing official upstream fix `8f5eaeb143dd9e58503980ae5f63dd78c463180e`. Identical build settings and RPATH removal are used for original and patched clients. Four source inputs are SHA-256 pinned; the applied patch is checked as exactly one getter-line change. Internal systemd libraries are statically linked and runtime binaries/manifest verified before use, then bound read-only inside the private client namespace. Twenty-one local tests pass. See [DHCPv6 review](SECRET_CUSTODY_DHCPV6_REVIEW.md) for the source hashes, executable hashes and acceptance evidence. All five final-head workflows must still pass before integration; their results and merge receipt belong in PR #180.

The original installed Ubuntu client remains unqualified: earlier heads `d92e190d82d6e21669a54ff8dc8e8f897137f9a6` and `87cd699cae804a5589764dfd9a9934f6e8bc1fe3` exposed its T2 getter defect. Do not replace this failure with the custom build's success. The first paired build at `a4f032dfc26bcf115e1bb32405a2b7667fb98084` compiled but failed the dependency/search-path gate; identical RPATH removal corrected that build-artifact issue and the next run verified no shared-systemd dependency. No protocol assertion was waived. Historical failures and the changed validation target remain recorded.

Next implement actual constrained-path IPv4/IPv6 PMTU, then compose dynamic control dependencies with independently supervised restricted recovery. Live DHCPv6 still needs an independently reviewed fixed deployment candidate; this CI build is not an installed or vendor-supported remedy. DNS/time lifecycle, first restricted maintenance installation and wrong shared allowlist recovery remain unresolved. Completed phone observations remain accepted; no phone/AWS/SSH/host action is requested. H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: IPv6 RA/ND/DAD control fixture

Updated: 2026-10-03 (Asia/Tokyo).

PR #178 merged at `5dd41f9fd28738530b05754582940ef19d08c521`. All five workflows succeeded for final head `89ca803cec06501f4e9b07f18eec4dcdd9266cae`, rechecked on this continuation. Restricted-link DHCPv4 acquisition/renewal/rebinding/expiry and administration survival are complete only in the recorded isolated scope.

The new mandatory IPv6 job reuses the private networkd launcher with a fixed IPv6 profile. It requires actual RA/SLAAC route acquisition/refresh/expiry, dynamic neighbor rediscovery, duplicate-address refusal, header rejection counters and existing/new off-link administration transport. See [IPv6 control review](SECRET_CUSTODY_IPV6_CONTROL_REVIEW.md). Four new local guard/checksum/empty-state tests and five shared DHCP tests pass; actual changed-head CI and all five final-head workflows must pass before integration. Initial head `af9a4a152b53329e2b45b9cb4d74afe0a2113e0f` failed before rule installation because an address-free IPv6 query returned an empty list; the unsafe first-element assumption is corrected with a reproducing local test. No protocol assertion is skipped. Corrected code head `153d681d755c2e332873370eadc01041a55fca42` passed IPv6 job `111179939207` in regression run `37114983663` on kernel `6.17.0-1022-azure`, networkd `255.4-1ubuntu8.17`, with all nine PASS records and `SYNTHETIC_IPV6_RA_ND_DAD_OK_NO_LIVE_APPLY`. Final-head workflow results and merge evidence belong in PR #179.

This is not DHCPv6, PMTU, router/neighbor authentication, complete IPv6 validation or live qualification. Next implement real DHCPv6 lifecycle and constrained-path PMTU, then compose qualified dynamic controls with independently supervised restricted recovery. First maintenance-anchor installation and recovery from a wrong shared allowlist remain unresolved. Completed phone observations remain accepted; no phone/AWS/SSH/host action is needed. H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: DHCPv4 lifecycle composed with restricted link policy

Updated: 2026-10-03 (Asia/Tokyo).

PR #177 merged at `e6f7c597d24c73f0d8f8852631b3c06bd87f67a6`. All five workflows succeeded for its final head `8d3af4b191c246359d3005a7ac773e41d0dda147`, rechecked on this continuation. The protocol-specific versus all-protocol packet-socket distinction and capability-free worker boundary remain accepted.

The next change strengthens the mandatory real networkd DHCPv4 fixture: inet and default-drop netdev restrictions exist before initial acquisition, then remain through unicast renewal, alternate-server rebinding and expiry. It adds pre-rule positive packet controls, exact drop counters for wrong tuples/fragments, qdisc-bypass controls, actual ARP without static neighbors and expired-address reachability refusal. Existing/new TCP administration transport and all prior lifecycle assertions remain required. See [composition review](SECRET_CUSTODY_DHCP_LINK_REVIEW.md). Five DHCP and three packet local tests pass. Code head `d6554eb9184a6ff83c825a015e6ed2f7d7b634bf` passed regression run `37113754710`, DHCP job `111176470089`, with all ten PASS records and `SYNTHETIC_DHCPV4_LINK_POLICY_COMPOSITION_OK_NO_LIVE_APPLY` on kernel `6.17.0-1022-azure`, nftables `1.0.9` and networkd `255.4-1ubuntu8.17`. All eleven regression jobs succeeded, including unchanged transition, recovery and packet-boundary jobs. Require all five final-head workflows successful before integration; their results and merge receipt belong in PR #178.

This is a fixed synthetic IPv4 composition, not a live policy, server authentication, ETH_P_ALL capture isolation, address renumbering, ARP spoofing defense or complete maintenance qualification. Next qualify IPv6 control traffic, then dynamic-dependency composition with restricted recovery. The first restricted maintenance anchor and recovery from an incorrect shared allowlist remain unresolved. Completed phone observations remain accepted; no repeated phone/AWS/SSH/host operation is needed. H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: raw packet filtering measured; DHCP link-policy composition next

Updated: 2026-10-03 (Asia/Tokyo).

PR #176 is merged at `d82ed0cf76d3f3bc240b8fba447c081d0465eec9`. Its final head `526dca65c4101a71176e23ceafcb45b8d7ab7bab` passed all five workflows, rechecked on this resumption. The real DHCPv4 lifecycle is complete in its recorded isolated scope. Completed live phone observations remain accepted; do not request identical retries.

PR #177 adds a mandatory CI fixture that measures ordinary UDP, protocol-specific AF_PACKET and ETH_P_ALL receive paths separately. It checks inet versus netdev ingress/egress, normal and qdisc-bypass transmission, wrong tuples/fragments, a separately executed capability-free child and owned cleanup. See [packet boundary review](SECRET_CUSTODY_RAW_PACKET_REVIEW.md). Code head `ce4fa08d8377b4dbf1634231598aa159d6af157c` passed the complete real-kernel job `111173559093` in regression run `37112699408`, including all six PASS records and `SYNTHETIC_RAW_PACKET_BOUNDARY_OK_NO_LIVE_APPLY`, on kernel `6.17.0-1022-azure`. Three local tests passed. The review records the EPERM assertion, direct-egress protocol matching and capability-free checkout-access corrections with their failed and successful evidence. Final-head workflow results and merge receipt are recorded in PR #177; require all five workflows successful before integration.

The design keeps raw capabilities out of the application worker. netdev ingress is not a confidentiality boundary against privileged ETH_P_ALL capture. These are synthetic packet/permission tests, not a live policy or DHCP authentication. Next compose restricted link rules with the actual DHCP lifecycle and existing administration assertions, then IPv6 control packets and fallback. First restricted maintenance installation/recovery remains unresolved. No phone operation or AWS/SSH/host mutation is requested; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: isolated DHCPv4 lifecycle passed; control-packet qualification remains

Updated: 2026-10-03 (Asia/Tokyo).

PR #175 merged at `06646c9b40726517e71da98bcd9509ebc1395b43` after all five workflows succeeded on head `59246821baf89b7bac3a7284e729ba29b52526f1`. The complete user dependency report is accepted below; no identical phone retry is needed.

PR #176 adds `tests/test_secret_custody_network_dhcp.py` and a mandatory Ubuntu CI job. It uses the actual networkd client in private network/mount/runtime/config namespaces and a synthetic DHCP server to test unicast renewal, broadcast rebinding to an alternate server, TCP transport continuity and lease expiry. See [scope and limitations](SECRET_CUSTODY_NETWORK_DHCP_REVIEW.md). Five local parser/namespace/runtime refusal tests pass. The actual lifecycle passed for code head `c7b040e515f72291168ffc42c2ac0bc9d8f9c22f` in regression run `37029254624`, DHCP job `110911645738`, on networkd `255.4-1ubuntu8.17`. Acquisition, unicast renewal with inet counters, alternate-server rebinding with existing/new administration transport, expiry/removal, negative reachability and cleanup all passed. Existing transition and independent recovery jobs also passed.

Resumed PR #176 after the user's pause. Previous head `796f6cf685022501408551008d2c2b1c4092e28a` failed initial acquisition in run `36945051624`, job `110645135668`; all other jobs/workflows passed. Ubuntu's downstream patch uses container detection for link initialization, unlike the upstream read-only-sysfs predicate previously assumed. The correction adds a marker only within verified private runtime storage and a real before/after container-detection check. It keeps isolation and lifecycle deadlines/assertions intact. The corrected real lifecycle now passes; this resolves the CI initialization incident in the measured fixture scope. Final-head workflow results and the merge receipt are recorded in PR #176; require all five workflows green before integration. No phone operation is needed.

Source review identified a material enforcement distinction: DHCP discovery/rebinding use raw packet sockets; bound renewal uses UDP. Only renewal asserts inet firewall counter passage. Passing this fixture must not be described as raw-frame filtering, DHCP authentication, address renumbering or complete maintenance qualification. The existing static transition/watchdog tests remain intact.

Next after this slice: address raw-socket/control-packet enforcement, then DHCPv6/RA/ND/PMTU and composition with fallback. Initial restricted maintenance installation and recovery from a wrong shared allowlist remain unresolved. No live firewall command, independent AWS/SSH access, new resource/IAM/inventory or credential is introduced. H2a and every runtime/provider/prediction/DB-write/data-fetch/scheduler/report gate remain inactive/OFF.

## Accepted live evidence and maintenance design: live dependencies observed; maintenance policy design

Updated: 2026-10-02 08:40 JST (Asia/Tokyo).

PR #174 merged at `1aa360b257da55d91facb857ff16b8be41a63d3e`. Its corrected head `e0ae01e3d92d84e4f127e997cd36bcd9b54a3864` passed all five workflows, rechecked on resumption. Regression run `36904707742` includes successful independent recovery job `110512222225` and local reader job `110512222345`. The earlier CI parser defect is historical and corrected.

The user has now supplied the complete requested dependency evidence: IMG_8937–IMG_8946, terminal captures at 08:17–08:32 JST. The immutable reader finished with `LOCAL_DEPENDENCIES_OBSERVED_WITH_UNRESOLVED_ITEMS_NO_MUTATION` and returned to the prompt. All selected sections were observed; `mutation=false`, `qualification=false`. This closes the request for that reader output. Do not ask for another identical run or more screenshots of these sections.

Sanitized observations: two interfaces; one DNS endpoint consistent with networkd's DHCPv4 provider data; zero fallback DNS entries; nine Chrony sources, one selected; nine IPv4 and seven IPv6 routes; DHCPv4 address/default-route configuration, DHCPv6 global address configuration, and an RA-derived IPv6 default route. One SSH endpoint tuple is caller-supplied/unverified. These are private user-supplied observations, not an independent Work host session, durable endpoint guarantees or packet-policy qualification. Exact addresses, allowlists and account identifiers stay out of public GitHub.

See [maintenance dependency design](SECRET_CUSTODY_NETWORK_MAINTENANCE_DESIGN.md) for the evidence-to-test matrix and initial-anchor decision. Next repository implementation is an isolated dynamic-address/control-packet fixture: real renewal/rebind, RA/ND and PMTU behavior with negative controls, preserving the existing transition/recovery tests. A UDP echo on DHCP ports does not qualify lease renewal. No live firewall installer or command is ready; the initial restricted maintenance anchor and recovery from a wrong shared allowlist remain unresolved.

H1 and measured H2a/H2b/H2c/H2d are complete. Keep H2a inactive and every runtime/provider/credential/prediction/data-fetch/scheduler/report gate OFF. No extra AWS inventory, IAM change, resource, secret, reboot or live firewall action follows from this evidence. Current unfiltered host state is not an allowed automatic fallback.

## Historical PR #174 preparation: independent recovery rehearsal and private dependency reader

Updated: 2026-10-02 (Asia/Tokyo).

PR #173 is merged at `180e590d1cede88f1326642170b73856d40deeea`. All five workflows passed for head `c321c22f89ec56c3432115993371535b0f9cc1dd`; regression run `36900487170`, job `110498113203`, completed all seven real IPv4/IPv6 transition markers with `SYNTHETIC_NETWORK_TRANSITION_OK_NO_LIVE_APPLY`. The initial fixture failure below was corrected before that successful run. No live firewall changed.

This follow-up implements a PID-1-supervised watchdog rehearsal in disposable network namespaces and a bounded local-only dependency reader. See [review and limits](SECRET_CUSTODY_NETWORK_RECOVERY_REVIEW.md). The real systemd test kills the applying child before/after apply, requires restricted fallback, verifies new/existing administration and qualification traffic in both families, and rejects unknown owned-table drift. Cooperative locks are not protection against arbitrary root writers. Independent recovery, initial anchor, persistence and live concurrency remain unqualified. Require the current PR's actual CI results before claiming this new rehearsal passed.

Initial PR #174 head `0396f275d7e14ef7672e9480284e34841685dd4d` passed the actual independent recovery job `110510991785` (run `36904340074`). The dependency job rejected the real DNS response format. The correction uses explicit D-Bus Properties.Get calls (honoring no-auto-start) and parses the returned variant array correctly, as verified against systemd v255 source. The original private reader is not approved for phone use. Require corrected-head CI; do not skip the failing assertion or ask the user to diagnose this CI-only defect.

The reader selects local interface/address/route/networkd/DNS/Chrony facts without external probes, raw config or credentials. Seven fixed commands are bounded by time/output; unavailable or unsupported sections remain unknown. Default output is counts only; `--private` emits selected private endpoints to the phone terminal. Keep those values out of public GitHub. A report is observation with unresolved items, never a completed policy or apply authorization.

Next: finish exact-head CI and read back the merge; then provide one immutable/hash-checked private reader command for the existing Termius session. This supplies missing dependency evidence, not a repeat of completed H1/H2/nft/UFW probes. Review that new private output before preparing actual profiles and an initial-anchor recovery proposal. Do not invent browser SSH ranges, DNS/NTP/renewal destinations or a recovery path. No live apply artifact exists yet and no firewall approval is requested now.

The user's 02:07–02:16 baseline below remains accepted. H1 and H2a/H2b/H2c/H2d are complete in their measured scopes. H2a remains inactive; all runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Work has no independent AWS/SSH connection. No third inventory run, IAM expansion, new resource, credential entry, production DB action, stress or reboot is authorized by this development step.

## Historical PR #173 preparation: network baseline and isolated transition rehearsal

Updated: 2026-10-02, carrying completed 02:07–02:16 JST evidence (Asia/Tokyo).

PR #172 is merged at `92a4dfed17a385a7045decebb661aa70619b0305`. The user's IMG_8930 at 02:07 shows the corrected observer at `78bbea96eec8d9c8228fe07c4e9ed71dbc1a3e2f`, SHA-256 `92a2f6a135c73d6ed972b61f203ee035e28c5ff7a473934b809041dac8aeb712`, succeeding with `H3_HOST_NETWORK_OBSERVED_NO_MUTATION`. Empty nft objects/base chains, zero exposed legacy IPv4 tables, IPv6 legacy tables not exposed, SSH wildcard listeners in both families, DNS/time-sync/DHCP-related listener ports and forwarding flags were observed. This supersedes the pending/correction boundary below; the failed PR #171 observer must not be retried.

IMG_8933–IMG_8935 at 02:12–02:13 show one visible SSH/TCP rule, a Custom IPv4 /32, browser SSH IPv4 enabled and browser IPv6 unchecked. Private addresses are omitted. Current screenshots do not re-show the port field; earlier configuration and successful Termius use TCP 22. The /32 is a public source address, not a unique-device guarantee; the browser checkbox does not disable host IPv6. Preserve the known manual/template difference. IMG_8936 at 02:16 shows UFW's own `Status: inactive`, despite its loaded/active/enabled systemd unit. Service state is not firewall state. These are user-supplied observations, not an independent Work AWS/SSH session or full effective-policy/reboot qualification.

The [transition proposal and rehearsal](SECRET_CUSTODY_NETWORK_TRANSITION_REVIEW.md) defines a default-deny maintenance fallback and an atomic qualification transition that preserves the same administration paths. It must remove qualification allowances including established flows, preserve unrelated tables, and stop on unknown owned-table drift. No fallback to unrestricted egress or world-open SSH is permitted. The initial maintenance anchor and independently supervised recovery remain unresolved live boundaries.

This development adds fixed synthetic nft profiles and mandatory isolated IPv4/IPv6 packet tests for connection preservation, positive/negative reachability, failed-transaction atomicity, restricted rollback and ownership drift. It is CI-only; it has no live apply path. Exact-head CI and merge evidence belong in the associated PR. Local Work cannot unshare; local guard tests alone do not qualify kernel behavior. TCP-22 echo tests are transport evidence, not authenticated SSH. No live policy was applied or existing phone command repeated.

Initial CI on `224f0be5add39e9cd27770993e8070f3785178b9` stopped while loading the unrelated fixture table, before packet assertions. No live host was involved. The one-line nested nft fixture was replaced with explicit statement/newline boundaries, and bounded synthetic-only command diagnostics were added. The original log did not include nft stderr; do not invent its exact parser message. Require the changed-code kernel run to succeed; no test is skipped or weakened.

Next: implement the bounded private dependency reader and initial-anchor recovery design, then the actual private profiles, independent watchdog and concurrency/ownership guard. Missing inputs include browser-SSH source-range lifecycle and independent recovery, effective upstream DNS/NTP, DHCP/IPv6 control/PMTU dependencies, exact bootstrap/runtime destinations and future policy ownership. Do not invent them, request secrets, repeat general baseline/probes, or widen egress to make tests pass. There is not yet a concrete live apply artifact to approve. H2a authorization does not imply firewall apply.

H1, corrected H2a install and measured H2b/H2c/H2d results remain complete. The H2a placeholder stays inactive. All runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Host/cloud hardening, persistence, local IPC/syscall/application capacity, TLS and full controller/reboot recovery remain incomplete. Host remains untrusted / no-secret.

## Historical boundary at 01:56 JST: readback failure and parser correction

Updated: 2026-10-02 01:56 JST evidence (Asia/Tokyo).

The user's IMG_8929 shows the immutable PR #171 observer at commit `60b435c8e2e04d9dc14bbc5070e867cdfa8ad996`, SHA-256 `d94175d03b18fa167fa98b76379d62ef8df178e4a7fe21e899437a93a08ef572`, ending with `STOP NETWORK_READBACK_UNAVAILABLE` and `RESULT H3_NETWORK_OBSERVATION_INCOMPLETE_NO_MUTATION`, followed by the prompt. This is an unsuccessful host observation. No host facts were emitted; effective network policy remains unknown. The screenshot cannot identify the failed stage or exception type. Do not repeat that unchanged command or claim a host configuration failure.

A concrete observer defect is reproduced locally: `ss` can render scoped IPv6 as `[fe80::1234]%interface:546`. The old `strip("[]").split("%", 1)[0]` leaves a closing bracket and raises ValueError. The iproute2 v6.1.0 source brackets the address before appending the interface scope, confirming that this is a legitimate representation. The original tests exercised only scope inside brackets and real unscoped loopback sockets. This is a verified parser defect and a plausible explanation of the live STOP, **not yet a confirmed live root cause**.

The correction supports both bracket/scope placements and scoped wildcards, while rejecting malformed brackets, duplicate/empty zones and invalid addresses. It also attributes read/parse failures to fixed stage and category codes without exception text, raw addresses or command diagnostics. No read is skipped; facts stay buffered until complete success. The fixed read-only commands, byte/time bounds, no-mutation scope and all disabled gates remain unchanged.

Sixteen offline tests cover the correction and error attribution. Mandatory existing CI adds an actual scope-bearing IPv6 UDP socket inside its disposable isolated network namespace, alongside nft and IPv4/IPv6 checks. All five workflows must pass on the correction commit before merge/readback and a replacement immutable phone command. CI success alone does not resolve the live incident. One changed-code phone run should either complete with `H3_HOST_NETWORK_OBSERVED_NO_MUTATION` or provide a new fixed STOP/STAGE pair; diagnose that pair rather than repeating unchanged commands.

H1, H2a recovery/installation, H2b, H2c and the ten H2d PASS records at 01:38 JST remain completed in their measured scopes (PR #170). Do not repeat provisioning, login/key/keyboard setup, rollback/apply or those completed probes. The H2a placeholder remains inactive. Work has no independent host/AWS session and the user supplies the live terminal evidence.

After one successful host readback, inspect the current Lightsail IPv4 and IPv6 firewall entries from the existing phone session. The earlier SSH edit screenshots did not expose the complete saved policy. Unknown/nonempty host rules require private review; do not flush or replace them. No IAM expansion, new inventory workflow dispatch, firewall change, stress or reboot follows from this correction. Preserve phone SSH and the recorded manual/template difference.

See [network readback review](SECRET_CUSTODY_HOST_NETWORK_READBACK_REVIEW.md). All runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Local IPC/syscall, application capacity, complete host/cloud ingress and default-deny egress, TLS, whole-controller and reboot recovery qualification remain pending. The host stays untrusted/no-secret.

## Historical failed H2a attempt and correction: H2a authorized; first apply failed; correction under validation

Updated: 2026-10-02 00:06 JST evidence (Asia/Tokyo).

The user explicitly said `適用して` at 2026-10-01 23:56:43 JST after the exact H2a identity/files/inactive-unit scope was presented. That authorization remains valid for diagnosis, bounded recovery and corrected application within the same scope; **do not ask for the same permission again**. It does not activate runtime, provider, credentials, networking changes or any other gate.

PR #166 merged offline preparation. The user's first live command pinned commit `5cc75aa40523e405ccd0a6515386d3a41eeb886d` and script SHA-256 `50a92a2b0c4585cc965a91faf737d81d337408573cf2668dd26dc49a825473e1`. At 00:00 JST it returned `STOP HOST_COMMAND_FAILED` / `RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_APPLY`. This was **not a successful installation**.

At 00:06 JST screenshot IMG_8924 confirmed: the receipt directory exists; the reserved code/config directories and unit file are absent; dedicated user/group lookups each return 2; systemd reports not-found/inactive, empty fragment/drop-ins/unit-file state, and show exit 0. Receipt contents have not independently been read back. The failure is consistent with the invalid `useradd --key CREATE_MAIL_SPOOL=no` argument found in our implementation. The prior mocked account tests missed the real parser boundary. The correction removes that invalid login.defs override; system accounts already skip mail creation. Fixed stage-specific command errors retain diagnostic privacy.

[H2a review and recovery](SECRET_CUSTODY_HOST_H2A_REVIEW.md) describes the defect, primary source and new real CLI test: installed Ubuntu 24.04 account tools target only a disposable chroot database, while the manager/process adapter remains synthetic. It reproduces the invalid command, checks receipt-only partial state, then exercises bounded rollback, corrected apply and verification. Require this CI step and existing regression checks to pass on the exact correction commit before merge or phone execution. Local Work has only UID/GID 0 and rejects the account CLI audit interface; it cannot substitute for this CI gate.

After CI/merge, use an immutable, hash-checked corrected script. Run its existing ownership-checked rollback once, then apply only if rollback succeeds; verify afterwards. Preserve the existing receipt schema for compatibility. No blind recursive removal, unchanged retry, approval bypass, password/key request or firewall widening. Any new STOP requires diagnosis. Successful offline tests are not live success; await the phone result `INSTALLED_DISABLED_NOT_QUALIFIED` before recording installation.

The candidate remains **untrusted / no-secret**; H2-H7 effective qualification and all runtime/credential gates remain pending/OFF. Work has no independently verified AWS/SSH session. The user's Termius connection works. Do not repeat provisioning, cost approval, IAM/bootstrap, inventory, key import, keyboard setup or H1.

## Previous milestone: creation and H1 completed

Updated: 2026-10-01 23:23 JST (Asia/Tokyo).

The user's phone screenshots confirm completion of the approved single Tokyo candidate and attached static IPv4, successful native Termius SSH login, command execution and the read-only H1 result `PREFLIGHT_OK_NO_MUTATION` with zero warnings/failures. See [creation and H1 evidence](SECRET_CUSTODY_HOST_H1_EVIDENCE.md) for the sanitized chronology, immutable script identity and limits.

The host remains **untrusted / no-secret**. H2-H7, workload capacity, effective sandbox/default-deny egress, static egress, TLS and reboot/recovery qualification are pending. H2a authorization, correction and successful installation are recorded above; effective qualification remains pending. No runtime/provider activation or custody secret use follows from H1.

Do not repeat creation, its cost approval, IAM/bootstrap, inventory, phone browser keyboard attempts, key import or H1 just to resume. The existing phone Termius path works. Work has no independently verified AWS/host session; use existing evidence and connectors within their actual permissions.

The phone administration change added one observed-source IPv4 /32 for SSH while preserving browser SSH IPv4 access. The 02:12–02:13 saved-rule UI evidence above supersedes the earlier pending readback; effective reachability remains unqualified. The original CloudFormation template still describes browser-only ingress. Review this manual difference before any stack update; keep IPs/key material private.

The dated sections below are historical observations at their stated stage. Their earlier zero-resource counts and untested-login statements are superseded by the evidence above, not instructions to repeat those operations.

## Scoped creation authorization (historical; operation now complete) — 2026-10-01 20:56:49 JST

The user replied `続けて` directly to the explicit approval request for the presented candidate file, one Tokyo Ubuntu 24.04 / 1 GB / 2 vCPU / 40 GB instance, USD 7/month base bundle (tax/transfer overage separate), one attached static IPv4, browser-SSH-only initial ingress and retention of successfully created resources on failure. In that conversational context, this authorizes proceeding with that exact one-candidate creation. Do not ask the same cost/configuration question again.

The approved template remains blob `4c8913e893ece7ed95e35827af6bf9406783e59e`. Its default and repository metadata remain non-authorizing; the live parameter may now be set to `ONE_CANDIDATE_USD7_APPROVED` for this approved operation. Proposed inputs remain stack `keirin-ai-custody-h1`, instance `keirin-custody-h1`, static IP `keirin-custody-h1-ip`, zone `ap-northeast-1a`, blueprint `ubuntu_24_04`, bundle `micro_3_0`, and existing default key `LightsailDefaultKeyPair`.

Authorization is not completion. No CREATE change set, instance, static IP or SSH login has been performed by this turn. The next required evidence is the authenticated intended-account/Tokyo context, absent proposed stack name, current selected blueprint/bundle and the actual resolved change set with exactly two Add actions. Verify preserve-successful-resources and deletion-policy behavior before Execute. A matching actual proposal can proceed under the existing approval; a different scope, cost, account, ingress or failure behavior requires resolving that difference before execution.

The usable AWS session is on the user's phone; Work has no verified AWS control-plane session and the existing GitHub role cannot provision. Guide the existing phone session without retrying the known Work login failure. Do not repeat inventory/bootstrap, expand IAM, create/download keys or introduce extra resources. Hosted execution, real credentials, hardening, Supabase changes and production prediction remain outside this authorization.

## Creation configuration and public-price review — 2026-10-01 (before approval)

At the earlier offline review, the paid scope was fully specified but not yet authorized or executed; subsequent authorization is recorded above. AWS's [current public pricing](https://aws.amazon.com/lightsail/pricing/) was rechecked on 2026-10-01: Linux/Unix with public IPv4, 1 GB memory, 2 vCPU, 40 GB disk and 2 TB transfer is USD 7/month. The [billing FAQ](https://docs.aws.amazon.com/en_en/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html) confirms no additional static-IP charge while attached, and USD 0.005/hour when unattached for more than one hour. Taxes, currency conversion and transfer overage are outside the bundle ceiling; no free-trial credit is assumed.

The exact candidate remains unchanged from main `16c31f91a4205991c28ac2a33e8c64678a2a4f29`, blob `4c8913e893ece7ed95e35827af6bf9406783e59e`. Its two resources are CustodyCandidate and CustodyStaticIp. The proposed new stack name is `keirin-ai-custody-h1`; stack-name absence and independent account identity are still unverified. The selected zone is `ap-northeast-1a` and the existing key parameter is `LightsailDefaultKeyPair`, observed by inventory run #2. Blueprint/bundle availability evidence remains the 18:28 catalog run; public-price verification is not a new AWS API observation.

At this earlier review point, the cost decision was still pending and the acknowledgement remained NOT_AUTHORIZED. The subsequent 20:56:49 JST authorization is recorded above. The actual CREATE change set and account/stack checks remain pending; do not confuse approval with execution or GitHub authentication with AWS access.

## Corrected inventory verified on 2026-10-01 (historical, before creation)

At 20:37:39 JST the user explicitly authorized one additional corrected read-only inventory run. [Inventory run #2](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36856726931) was dispatched exactly once from main `de7cd0b97bb009f5f9394512f94bf5be33d5251b` (PR #161 merged). Job `110350863079` completed successfully, including OIDC authentication and all three inventory reads. The version 2 result was emitted at 11:39:38 UTC / 20:39:38 JST.

| Observation | Verified result |
| --- | --- |
| Region | ap-northeast-1 |
| Instances / static IPs / key pairs | 0 / 0 / 1 |
| Proposed instance / static-IP name collisions | false / false |
| Tokyo default key present | true |
| Review reasons | empty |
| Key login / independent account identity / stack-name inventory | Not verified |
| Live creation authorized | false |

The corrected default-key classifier is now verified against AWS metadata. This resolves the earlier default-key identity uncertainty; version 1's absence flag remains invalid historical evidence. No key was created or downloaded and no private key material was read. Metadata presence does not verify SSH login.

Both authorized inventory runs are complete. Do not dispatch a third run or repeat the IAM/bootstrap setup automatically. Next, verify the intended account, proposed stack name and current blueprint/bundle/price before preparing the exact two-resource CREATE change set for separate approval. No paid host/IP creation, provisioning permission, runtime activation or Supabase change was authorized by this inventory execution.

## Concrete host proposal prepared offline (historical)

The user authorized the exact Tokyo GetInstances/GetStaticIps/GetKeyPairs IAM update plus one inventory run on 2026-10-01. The reviewed single-role, non-replacement change set preserved trust and all other role properties. CloudFormation reached UPDATE_COMPLETE at 19:52:49 JST. Separate post-update IAM policy/trust read-back was not performed.

[Inventory run #1](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36852494617) succeeded on main `a713b6d57199975e13c32edd84cee9d2ed2da602` at 19:59:23 JST: Tokyo instances 0, static IPs 0, key pairs 1; both proposed name-collision flags false. This consumed the first one-run authorization; the separately authorized corrected run #2 is recorded above.

Version 1 used a download filename stem for the default-key match; its false default-key flag/reason remains invalid as absence evidence. Version 2 corrected the API name to `LightsailDefaultKeyPair` with independent literal regression fixtures, passed 33 local tests and all five applicable CI workflows, and is now verified by run #2. The existing Tokyo default key was observed without an IAM expansion. Full evidence and retry/stop conditions are in `AWS_LIGHTSAIL_INVENTORY_REVIEW.md` and `WORK_RESUME.md`.

`review/aws_lightsail_candidate.json` proposes exactly one Tokyo Ubuntu 24.04 LTS / micro_3_0 candidate and one attached static IPv4. The planned names are keirin-custody-h1 and keirin-custody-h1-ip, not verified existing resources. The USD 7/month figure is the observed bundle price, subject to a fresh pre-execution price check.

The template rejects its default acknowledgement, wrong region or mismatching expected account. It requires an existing Tokyo Lightsail key pair, requests only browser-SSH source alias ingress, embeds no launch script/credentials and retains both resources on stack removal. The review explains failure-retention costs, change-set review, actual firewall verification and separately authorized cleanup. Local cfn-lint 1.57.1 passed with no findings and 10 candidate safety-contract tests passed; the offline CI repeats these checks.

The host proposal remains offline: no host, static IP or key was created. The authorized IAM update and both inventory runs are complete. Default-key identity is resolved; independent account/stack checks and deployment permissions remain unresolved. The role has six read actions (three catalog plus three Tokyo inventory), with no provisioning permission. Read `SECRET_CUSTODY_HOST_PROVISIONING_REVIEW.md` for the subsequent execution sequence.

## Product direction

`AI_AGENT_REQUIREMENTS.md` is authoritative. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI is the first major execution target, not the only scope.

## Fixed safety state

Unless a new, specific boundary is explicitly authorized:

- deployed hosted task/provider execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- provider generation/write bindings: **unbound**;
- report delivery / live 21:00 scheduling: **OFF / unconfigured**;
- scheduler / recurrence: **OFF**;
- no real provider/OAuth refresh exchange is connected;
- no real provider credential or refresh secret is stored in the custody project;
- no live secret-store schema has been applied to the custody project;
- one paid candidate and attached static IPv4 exist; H1 passed, full hardening is pending.

Agent-only checkpoint/activity persistence and queue coordination in `keirin-ai-staging` were separately authorized. Exact-task lease acquisition is deployed. No always-on worker is active.

## Verified repository state

The live observation ran against main `f08bfbb3ed59478653f9055757b138e7c0141dcf` (PR #157 merged). PR #157 head `e21f161075908fac10e938a56c11ab6440640cc5` passed all five applicable workflows: collection progress UI regression, agent runtime read-only smoke, aws observation offline contract, keirin-ai regression and agent checkpoint PostgreSQL contract.

PR #151 introduced the reviewed OIDC read-only observation package; #152 added catalog-error privacy and #153 added offline CloudFormation template validation. The live run is separate evidence that the deployed OIDC role and catalog reads worked.

Resolve current main from GitHub on the next resumption; embedded SHAs are historical evidence, not a permanently current branch pointer. The PostgreSQL contract retains the application stack, lease/trust/hostname, row-lock/deadline, TLS/restart recovery and audit-redaction checks.

## Runtime staging project

Existing runtime/checkpoint staging remains `keirin-ai-staging` in `ap-northeast-1`. Provider/runtime execution gates, prediction DB writes and external race-data fetching remain OFF.

Do not repurpose this shared application staging Vault for real agent refresh-secret custody. The 2026-09-30 Phase A inventory confirmed `service_role` can directly access decrypted Vault data in that project.

## Secret-custody project

A dedicated `keirin-ai-secret-custody` project exists in `ap-northeast-1` (Tokyo). The organization plan remains Free and the project-creation cost check returned 0 per month. The project was `ACTIVE_HEALTHY` at the last live check.

No paid add-on, database password, Vault secret, binding row, provider credential, Edge Function or hosted worker has been created for the custody path.

## C0 / C1 complete boundary

`SECRET_CUSTODY_C0_C1_EVIDENCE.md` records the dedicated-project provisioning and catalog-only inventory. The observed database is PostgreSQL 17.6 family, primary, with `supabase_vault` 0.3.1. Proposed private roles/schema were absent. No secret row/value/name/description or provider credential was read and no DDL/DML was submitted during C1.

Project isolation, not revocation of Supabase-managed platform privileges, is the selected blast-radius boundary.

## C2 review artifacts complete

PR #138 added `SECRET_CUSTODY_C2_REVIEW.md`, the candidate/rollback SQL outside `supabase/migrations`, and regression guards. The reviewed model retains the dedicated LOGIN host / NOLOGIN broker split, private metadata schema, forced RLS, exact read/CAS functions, no runtime `vault.create_secret` capability, no password, no binding row and no secret provisioning.

**C2 has not been applied to Supabase.**

## Management-plane preflight

PR #139 added `SECRET_CUSTODY_MANAGEMENT_PLANE_PREFLIGHT.md` with three hard gates:

1. Data API disabled;
2. Postgres SSL enforcement enabled;
3. database/pooler network restrictions limited to the approved hardened-host egress CIDR set.

Their authoritative live state remains unknown until verified through the Dashboard or an appropriately scoped Management API path. Unavailable/denied reads remain unknown; no world-open placeholder CIDR is accepted; management changes are not batched with C2 DDL.

## Hardened-host candidate

PR #140 selected Amazon Lightsail Linux/Unix Micro 1 GB in Tokyo (`ap-northeast-1`) as the first later qualification candidate: 2 vCPU, 1 GB RAM, 40 GB SSD, 2 TB transfer, reviewed maximum bundle price USD 7/month, with an attached static IPv4.

The provider boundary was re-checked on 2026-10-01. Lightsail remains the first candidate: current public documentation still shows Tokyo support and the USD 7 Micro 1 GB public-IPv4 bundle shape. Railway and Render do not currently provide a lower-friction equivalent for this design's Tokyo + stable-egress requirement, and DigitalOcean has no Tokyo region.

AWS account bootstrap is now complete. The user created the Proof of Concept account, upgraded it to the paid usage model, activated advanced features, and created the `ai-agent-team` management boundary. A USD 10 monthly AWS Budget exists and its charge-type filter excludes Credit and Refund so AWS usage remains visible while promotional credits are available. The single candidate and attached static IPv4 have now been created; H1 passed. If 1 GB proves insufficient, do not weaken safeguards to preserve the USD 7 target.

## Host safety reviews complete

PR #141 added the read-only H0-H7 hardening qualification review and offline `review/lightsail_host_preflight.sh`. PR #142 added the fail-closed provisioning review and `review/lightsail_provisioning_manifest.template.json` with `authorized_for_live_create=false`. PR #144 added the declarative hardening package review, offline validator and regression guards with `authorized_for_live_apply=false`. PR #145 added fail-closed recovery/rollback review artifacts with `authorized_for_live_recovery=false`. PR #146 added the read-only AWS control-plane observation review and sanitized observation template with `authorized_for_live_create=false`.

The created candidate remains **untrusted / no-secret** after H1. Passing repository review or host hardening by itself does not authorize C2 DDL or credential use.

The hardening package is declarative data, not an executable host mutation script. The recovery plan keeps the runtime disabled and host no-secret on preflight, hardening, network/TLS, capacity or reboot/recovery failure. Automatic AWS destruction/resize/reboot/snapshot/replacement, automatic firewall relaxation/egress widening, protected Supabase/Vault/provider/prediction/race-data mutations, insecure TLS/plaintext fallback and credential introduction during recovery are forbidden by the reviewed contracts.

## AWS GitHub OIDC read-only automation

`AWS_GITHUB_OIDC_READONLY_OBSERVATION.md`, `review/aws_github_oidc_readonly_role.yaml`, `review/aws_lightsail_readonly_observation.sh` and the manual-dispatch workflow define the short-lived OIDC observation path. The deployed role was successfully assumed in run #1 and the three catalog calls passed.

The reviewed role is restricted to the immutable GitHub owner/repository IDs, branch main, audience sts.amazonaws.com, and the three catalog actions `GetRegions`, `GetBlueprints`, `GetBundles`. The separately approved update added only Tokyo `GetInstances`, `GetStaticIps`, `GetKeyPairs`. It has no Lightsail mutation permission. Do not widen it for provisioning without a separate review/authorization.

CloudFormation/SCP and browser/app troubleshooting are completed history for this boundary. Do not repeat failed CloudShell/mobile-editor paths or recreate the stack/secret. Offline checks still enforce exact Tokyo, active identifiable Ubuntu LTS, the matching bundle shape/public IPv4 and a finite nonnegative price at or below USD 7. Passing catalog reads does not verify allocation, host safety or provisioning permissions.

## AWS control-plane observation review complete

`SECRET_CUSTODY_AWS_CONTROL_PLANE_OBSERVATION_REVIEW.md` and `review/lightsail_control_plane_observation.template.json` define the reviewed observation boundary. The template fixes the expected region/host shape/price ceiling while leaving every live observation value unset. It keeps `authorized_for_live_create=false`, rejects automatic size/region substitution, forbids sensitive account/key/IP/credential material and keeps every runtime/provider/prediction gate disabled.

The initial authenticated catalog observation passed; see the verified values above. Static IPv4 creation/attachment was subsequently observed through the phone console; see the H1 evidence. Unknown, ambiguous or mismatching future values fail closed. Passing observation still requires a separate explicit live-provision instruction before any Lightsail instance or static IP is created.

## Cost / availability boundary

Keep the Supabase Free project for architecture, review and no-secret qualification while it remains operationally suitable. Free is not approved for real always-on credential custody because low-activity Free projects can be paused. Before C4 real credential activation, require either a paid-plan availability boundary or an equivalent separately reviewed solution.

Exactly one USD 7/month candidate has been created under the scoped approval. Continue qualification with synthetic/no-secret inputs; a rejection requires a separately reviewed and authorized cleanup decision. Do not keep multiple paid hosts running for convenience.

## Next work / next boundary

1. Creation, native SSH and read-only H1 are complete. Use `SECRET_CUSTODY_HOST_H1_EVIDENCE.md`; do not recreate or re-run setup without a changed condition.
2. H2a installation and measured H2b/H2c/H2d verification are complete. H3 dependency observation is also complete; follow the current maintenance design above, not historical phone-run instructions.
3. Confirm complete relevant current firewall rules before H3/H4; preserve the bounded phone/browser administration path. The manual /32 source differs from the original browser-only template.
4. Qualify effective sandbox/resource limits, no-secret capacity, default-deny egress, verified static egress, TLS verify-full and reboot/recovery before introducing custody credentials.
5. Use verified hardened-host egress for separately authorized Supabase network restrictions; verify Data API disabled and SSL enforcement, changing each separately only if required.
6. Require fresh explicit authorization for C2 live DDL, clearly synthetic material for C3, and a separate availability/cost decision and authorization for C4 real credentials.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity. Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers, host allowlists, provider account identifiers or personal data. Prefer current `main`, current CI, deployed metadata and direct bounded checks over older handoff notes.

## Catalog command error privacy (2026-10-01, historical validation)

PR #152 is merged (`cb32f7f2351536cfef26ac0702252aeb8e593574`). The follow-up suppresses raw stderr from all three catalog AWS CLI commands, including warnings on successful commands. Failures report only the fixed operation name and exit status, preserve the original nonzero status, and stop before subsequent commands or a success report. Partial stdout remains in the temporary directory and is removed on exit. This intentionally sacrifices raw diagnostic detail to avoid publishing account IDs or role ARNs. It does not change credential-action logging or AWS CLI internal retry behavior.

Local shell syntax validation and 58 offline tests passed, including synthetic private stderr/partial-stdout canaries at each of the three failure points. No real AWS calls were made during that historical validation. Later bootstrap and live observation passed, as recorded above. The historical pending-policy/access incident is no longer the current boundary.

## OIDC template preflight (2026-10-01, historical validation)

Verified base: PR #153 merged, main `c3fd6d1488f1b4c8113ca652ca7dd109c15413d4`; its five exact-head CI workflows succeeded. The unchanged OIDC CloudFormation template passed local `cfn-lint==1.57.1` for Tokyo with no findings and no AWS credentials in the validation process environment. The offline CI now repeats that template check alongside the existing catalog tests. This is local schema validation, not AWS account/change-set validation or deployment.

The SCP change and OIDC bootstrap were subsequently completed, and live run #1 succeeded. Those later observations supersede the old browser/session blocker. Offline work itself did not verify live AWS state. The successful live run also reported checkout Node.js deprecation and ubuntu-latest migration notices; these remain nonblocking maintenance follow-ups.
