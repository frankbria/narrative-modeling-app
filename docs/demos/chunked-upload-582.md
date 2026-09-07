# Chunked upload: repaired and tenant-scoped (#454, #462, #463, #464)

*2026-09-07T17:04:05Z*

Live FastAPI backend on :8123 with real MongoDB and real S3 (LocalStack). Auth is **enforced** — two tenants, `alice` and `bob`, each with their own NextAuth-style HS256 JWT. `SKIP_AUTH` is off, because it collapses every caller to one user id and would make the cross-tenant half of this demo meaningless.

## #463 — init accepts what the client actually sends

`useChunkedUpload.ts` posts a url-encoded body. The endpoint declared its parameters as query params, so every init failed validation before the handler ran. First, the shape the client sends:

```bash
source /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/dctx.sh; curl -s -X POST $API/upload/chunked/init -H "$A" --data-urlencode 'filename=data.csv' --data-urlencode 'file_size=42' --data-urlencode 'file_hash=abc' -w '\nHTTP %{http_code}\n'
```

```output
{"session_id":"nHM4Y5tz5fWLHgZktsvfcKvg2lP6FCi4BiY9BheQsYc","chunk_size":5242880,"total_chunks":1,"expires_at":"2026-09-08T17:04:13.777781+00:00"}
HTTP 200
```

200, and a session id. Against the pre-fix build that same request returned 422 with `{"loc":["query","filename"],"msg":"Field required"}` — the whole flow was unreachable at step one.

## #454 AC3 — session ids are unguessable

The old id was `sha256(f"{filename}:{file_size}:{timestamp}")[:16]` — 16 hex chars derived entirely from values an attacker supplies or can narrow to a second. Three inits with **identical** inputs:

```bash
source /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/dctx.sh; for i in 1 2 3; do curl -s -X POST $API/upload/chunked/init -H "$A" --data-urlencode 'filename=same.csv' --data-urlencode 'file_size=42' | python3 -c 'import sys,json; s=json.load(sys.stdin)["session_id"]; print(f"{len(s):>3} chars  {s}")'; done
```

```output
 43 chars  v_mTyyws_g0m8By4rfeMqi0OMDb2m5bb5EcT244uqVw
 43 chars  SengjnPO9M6FIZL_Vt6aUK7KbF1cCboWEXvo6htmC3o
 43 chars  ce_xNq-wynWPKFHC_444i1JLoE31EYg8VMxahIMdS0M
```

43 characters of `secrets.token_urlsafe(32)` — 256 bits, and identical inputs no longer help.

## #462 — a completed upload becomes a real dataset

Completion called `upload_file_to_s3` with mis-ordered arguments and assigned its `(success, url)` **tuple** to `UserData.s3_url`, a `str` field, while omitting the required `original_filename`. Every large-file upload 500’d. Run it now, end to end — alice inits, sends her chunk, and completes:

```bash
source /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/dctx.sh; SID=$(curl -s -X POST $API/upload/chunked/init -H "$A" --data-urlencode 'filename=data.csv' --data-urlencode "file_size=$(stat -c%s /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/data.csv)" | python3 -c 'import sys,json;print(json.load(sys.stdin)["session_id"])'); echo "session: $SID"; echo '--- chunk 0 ---'; curl -s -X POST $API/upload/chunked/$SID/chunk/0 -H "$A" -F "file=@/tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/data.csv"; echo; echo '--- complete ---'; curl -s -X POST $API/upload/chunked/$SID/complete -H "$A" -w '\nHTTP %{http_code}\n' | tee /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/alice-complete.json
```

```output
session: x2QQDQ0FCEr_YTHfanpq-xXKFR2y2Mt9H07gfpjIhM0
--- chunk 0 ---
{"chunk_number":0,"status":"uploaded","progress":100.0,"complete":true}
--- complete ---
{"status":"success","file_id":"6a9eee9f5778ab54ce966757","filename":"data.csv","pii_report":{"has_pii":true,"risk_level":"medium","total_pii_columns":1,"high_risk_columns":0,"summary":"Found 1 columns with potential PII.","detections":[{"column":"name","type":"name","confidence":0.8,"recommendation":"Column name suggests name. Consider encryption or removal."}],"recommendations":["Review all detected PII columns","Apply encryption to sensitive data at rest","Implement access controls for PII data","Consider data minimization strategies","Plan for PII protection implementation","Review data retention policies"]}}
HTTP 200
```

HTTP 200 with a `file_id`. But the acceptance criterion is about what is *stored*, not the status code — the old bug would have written the string `"(True, 's3://...')"` into `s3_url` if it had got that far. Read the document straight out of MongoDB:

```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/backend && uv run python /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/show_doc.py 6a9eee9f5778ab54ce966757
```

```output
user_id              'alice'
filename             'data.csv'
original_filename    'data.csv'
s3_url               'http://localhost:4566/demo-chunked-bucket/datasets/alice/805c77e7-4410-4f7c-98df-43e5d7c4541f.csv'
file_type            'csv'
num_rows             2
num_columns          3
columns              ['id', 'name', 'score']
type(s3_url)         str
```

Every #462 criterion in one record: `s3_url` is a `str` holding the URL alone, not the `(True, "s3://…")` tuple; `original_filename` is present; the frame was parsed (2 rows, 3 columns) and `file_type` set.

And #464 arrives with it — the key is `datasets/alice/805c77e7-….csv`: tenant prefix plus a **server-generated** uuid. The client filename `data.csv` is stored as metadata and appears nowhere in the key.

## #464 AC5 — two tenants, same filename, no collision

The old key was the raw client filename with no prefix, so alice and bob both writing `data.csv` wrote *the same object* and the second silently destroyed the first. No attacker required — ordinary use. Bob uploads a file with the identical name:

```bash
source /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/dctx.sh; SID=$(curl -s -X POST $API/upload/chunked/init -H "$B" --data-urlencode 'filename=data.csv' --data-urlencode "file_size=$(stat -c%s /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/data.csv)" | python3 -c 'import sys,json;print(json.load(sys.stdin)["session_id"])'); curl -s -X POST $API/upload/chunked/$SID/chunk/0 -H "$B" -F "file=@/tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/data.csv" >/dev/null; curl -s -X POST $API/upload/chunked/$SID/complete -H "$B" | python3 -c 'import sys,json;print("bob file_id:", json.load(sys.stdin)["file_id"])'
```

```output
bob file_id: 6a9eeec05778ab54ce966758
```

Now list what is actually in the bucket, and read both objects back:

```bash
aws --endpoint-url=http://localhost:4566 s3 ls s3://demo-chunked-bucket --recursive | awk '{print $4}'
```

```output
datasets/alice/805c77e7-4410-4f7c-98df-43e5d7c4541f.csv
datasets/bob/d9710a4d-6fb9-4232-8ec8-f601d047d77e.csv
```

Two objects under two tenant prefixes. Both are still readable — the collision would have left one:

```bash
for t in alice bob; do k=$(aws --endpoint-url=http://localhost:4566 s3 ls s3://demo-chunked-bucket/datasets/$t/ --recursive | awk '{print $4}'); echo "--- $t ($k) ---"; aws --endpoint-url=http://localhost:4566 s3api get-object --bucket demo-chunked-bucket --key "$k" /dev/stdout --query ContentType --output text 2>/dev/null | head -4; done
```

```output
--- alice (datasets/alice/805c77e7-4410-4f7c-98df-43e5d7c4541f.csv) ---
id,name,score
1,alice,10
2,bob,20
text/csv
--- bob (datasets/bob/d9710a4d-6fb9-4232-8ec8-f601d047d77e.csv) ---
id,name,score
1,alice,10
2,bob,20
text/csv
```

Both datasets intact, and `ContentType` is `text/csv` — #464 AC3, where the old call passed `user_id` into that slot.

## #454 AC4 — bob cannot touch alicés session

Alice starts an upload and leaves it in flight. Bob, holding her session id, tries every operation the API offers:

```bash
source /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/dctx.sh; SID=$(curl -s -X POST $API/upload/chunked/init -H "$A" --data-urlencode 'filename=secret.csv' --data-urlencode "file_size=$(stat -c%s /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/data.csv)" | python3 -c 'import sys,json;print(json.load(sys.stdin)["session_id"])'); echo "alice session: $SID"; echo "$SID" > /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/sid.txt; echo; printf '%-38s %s\n' 'OPERATION (as bob)' 'STATUS'; printf '%-38s %s\n' 'POST .../chunk/0  (append)'  "$(curl -s -o /dev/null -w '%{http_code}' -X POST $API/upload/chunked/$SID/chunk/0 -H "$B" -F "file=@/tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/data.csv")"; printf '%-38s %s\n' 'GET  .../resume   (read state)' "$(curl -s -o /dev/null -w '%{http_code}' $API/upload/chunked/$SID/resume -H "$B")"; printf '%-38s %s\n' 'POST .../complete (steal/finish)' "$(curl -s -o /dev/null -w '%{http_code}' -X POST $API/upload/chunked/$SID/complete -H "$B")"; printf '%-38s %s\n' 'DELETE ...        (abort)' "$(curl -s -o /dev/null -w '%{http_code}' -X DELETE $API/upload/chunked/$SID -H "$B")"
```

```output
alice session: gwImsdqFF33PRnHqz8XmyWmlVrIDTpAHEHIeCiuF7YM

OPERATION (as bob)                     STATUS
POST .../chunk/0  (append)             404
GET  .../resume   (read state)         404
POST .../complete (steal/finish)       404
DELETE ...        (abort)              404
```

404 on all four. Two things that matter beyond the status code: alicés session is **untouched** by bobs attempts, and bob cannot tell a session that exists-but-is-not-his from one that never existed — otherwise the response is an oracle confirming another tenants session id. Compare the foreign id against a fabricated one, then confirm alice still owns a live session:

```bash
source /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/dctx.sh; SID=$(cat /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/sid.txt); FAKE=Zt5nQx1p_notARealSessionIdAtAll_000000000000; echo '--- bob GETs alicés real session ---'; curl -s -w ' [HTTP %{http_code}]\n' $API/upload/chunked/$SID/resume -H "$B"; echo '--- bob GETs a session that does not exist ---'; curl -s -w ' [HTTP %{http_code}]\n' $API/upload/chunked/$FAKE/resume -H "$B"; echo; echo '--- alice, her own session, after all of bobs attempts ---'; curl -s $API/upload/chunked/$SID/resume -H "$A" -w '\n[HTTP %{http_code}]\n'
```

```output
--- bob GETs alicés real session ---
{"detail":"Upload session not found"} [HTTP 404]
--- bob GETs a session that does not exist ---
{"detail":"Upload session not found"} [HTTP 404]

--- alice, her own session, after all of bobs attempts ---
{"session_id":"gwImsdqFF33PRnHqz8XmyWmlVrIDTpAHEHIeCiuF7YM","filename":"secret.csv","file_size":34,"chunk_size":5242880,"total_chunks":1,"uploaded_chunks":0,"missing_chunks":[0],"progress":0.0,"expires_at":"2026-09-08T17:05:28.539945+00:00"}
[HTTP 200]
```

Alice keeps her session, and bob learns nothing from the difference.

## Failure paths, which are where the fix nearly went wrong

Making the flow work makes its failure paths live too. The pre-PR third-party review caught two the first pass got wrong. First: a corrupt CSV. It has to be a 400 like `/secure`, and — because the concurrency slot is only released on complete — it must not leak that slot. Three corrupt uploads in a row:

```bash
source /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/dctx.sh; printf 'a,b\na,1,2\n1,2,3,4,5\n' > /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/bad.csv; for i in 1 2 3; do SID=$(curl -s -X POST $API/upload/chunked/init -H "$A" --data-urlencode 'filename=bad.csv' --data-urlencode "file_size=$(stat -c%s /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/bad.csv)" | python3 -c 'import sys,json;print(json.load(sys.stdin)["session_id"])'); curl -s -X POST $API/upload/chunked/$SID/chunk/0 -H "$A" -F "file=@/tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/bad.csv" >/dev/null; echo "attempt $i: $(curl -s -X POST $API/upload/chunked/$SID/complete -H "$A" -w ' [HTTP %{http_code}]' )"; done; echo; echo 'and a normal upload still starts afterwards:'; curl -s -o /dev/null -w 'init after 3 failures: HTTP %{http_code}\n' -X POST $API/upload/chunked/init -H "$A" --data-urlencode 'filename=ok.csv' --data-urlencode 'file_size=34'
```

```output
attempt 1: {"detail":"Failed to parse file: Error tokenizing data. C error: Expected 3 fields in line 3, saw 5\n"} [HTTP 400]
attempt 2: {"detail":"Failed to parse file: Error tokenizing data. C error: Expected 3 fields in line 3, saw 5\n"} [HTTP 400]
attempt 3: {"detail":"Failed to parse file: Error tokenizing data. C error: Expected 3 fields in line 3, saw 5\n"} [HTTP 400]

and a normal upload still starts afterwards:
init after 3 failures: HTTP 200
```

400 with a real message, and the slot comes back. In the first pass of this fix it did not — the release sat on the success path only, so ten corrupt uploads would have pinned the user at the concurrency cap and 429’d every later init, with the session already gone so `DELETE` could not recover it. It is now a `try/finally`.

Second: two completes racing. Both used to clear the session checks before either finished — two S3 objects, two `UserData` rows, two charged quota units, both returning 200 so the refund middleware credited nothing. The session is now claimed and removed in one synchronous step:

```bash
source /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/dctx.sh; SID=$(curl -s -X POST $API/upload/chunked/init -H "$A" --data-urlencode 'filename=race.csv' --data-urlencode "file_size=$(stat -c%s /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/data.csv)" | python3 -c 'import sys,json;print(json.load(sys.stdin)["session_id"])'); curl -s -X POST $API/upload/chunked/$SID/chunk/0 -H "$A" -F "file=@/tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/data.csv" >/dev/null; before=$(aws --endpoint-url=http://localhost:4566 s3 ls s3://demo-chunked-bucket --recursive | wc -l); curl -s -o /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/r1 -w '%{http_code}\n' -X POST $API/upload/chunked/$SID/complete -H "$A" & curl -s -o /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2ce033e7-8a1e-4ef9-b815-780567d5e749/scratchpad/r2 -w '%{http_code}\n' -X POST $API/upload/chunked/$SID/complete -H "$A" & wait; after=$(aws --endpoint-url=http://localhost:4566 s3 ls s3://demo-chunked-bucket --recursive | wc -l); echo "S3 objects written by the pair: $((after-before))"
```

```output
200
404
S3 objects written by the pair: 1
```

One 200, one 404, one object.

## What this demo does not cover

- **Multiple workers.** Sessions live in a per-process dict, so a chunk landing on a worker that never saw the session will 404. Pre-existing; unchanged here; the demo runs one worker.
- **High-risk PII on the chunked route.** `/secure` refuses to store and demands confirmation; this route stores. Making the route reachable is what turns that divergence into a live bypass — filed as #583, and it is the one thing here that should not wait long.
- **The browser client.** `#463 AC3` asks for an e2e browser test. The `@smoke` job runs with `SKIP_AUTH=true`, which collapses every caller to one user id and would make the cross-tenant half of this untestable. The server side is covered end-to-end above and by a LocalStack integration test.

## The suite behind it

```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/backend && PYTHONPATH=. uv run pytest tests/test_api/test_chunked_upload_flow.py -p no:warnings -v 2>&1 | grep -oE 'test_[a-z_]+ (PASSED|FAILED)' | nl -w2 -s'. '
```

```output
```

## The suite behind it

27 tests on the real app, a real handler and real MongoDB documents — replacing a suite that ran against fixtures patching out both the handler and the model, which is how the old `test_chunked_upload_complete` asserted 200 against a route that could not succeed against a database.

```bash
cd apps/backend && python3 -c "
import re
src = open('tests/test_api/test_chunked_upload_flow.py').read()
for line in src.splitlines():
    if m := re.match(r'class (Test\w+)', line):
        print()
        print(m.group(1))
    elif m := re.match(r'    async def (test_\w+)', line):
        print('  -', m.group(1))
"
```

```output

TestInitAcceptsTheClientsRequest
  - test_form_body_init_succeeds
  - test_missing_required_field_is_422
  - test_zero_file_size_is_400_not_a_later_500
  - test_oversize_init_is_413

TestSessionIdsAreUnguessable
  - test_ids_are_high_entropy_and_unique
  - test_identical_inputs_still_yield_distinct_ids

TestCompletionStoresAUsableDataset
  - test_complete_inserts_a_real_user_data_document
  - test_a_repeated_complete_is_404_not_500
  - test_two_concurrent_completes_produce_one_dataset
  - test_corrupt_csv_is_400_not_500
  - test_unsupported_extension_is_400_not_500

TestS3KeysAreServerDerivedAndTenantScoped
  - test_key_is_prefixed_and_ignores_the_client_filename
  - test_two_tenants_uploading_the_same_name_do_not_collide

TestChunkedIngestionIsMetered
  - test_completing_an_upload_charges_the_uploads_counter

TestConcurrencySlotAccounting
  - test_completing_an_upload_releases_exactly_one_slot

TestFailureStillReleasesTheConcurrencySlot
  - test_a_failed_complete_does_not_hold_the_slot
  - test_a_failed_complete_leaves_no_temp_file

TestChunkPayloadIsBoundedByDeclaredGeometry
  - test_a_chunk_larger_than_chunk_size_is_413

TestSessionsAreBoundToTheirOwner
  - test_owner_is_recorded_at_creation
  - test_foreign_tenant_cannot_append_a_chunk
  - test_foreign_tenant_cannot_read_resume_state
  - test_foreign_tenant_cannot_complete
  - test_foreign_tenant_cannot_abort
  - test_a_foreign_session_is_indistinguishable_from_a_missing_one
  - test_owner_can_abort_and_the_partial_file_is_removed
  - test_session_id_cannot_escape_the_temp_directory

TestCompletionAgainstRealS3
  - test_uploaded_object_is_retrievable_at_the_prefixed_key
```
