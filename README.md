Plans & Demo Enforcement (Step 1)

Plan catalog lives in `app/utils/plans.py` and includes: `demo`, `basic`, `pro`, `enterprise`, `free_unlimited`.

- demo: per_file_limit=10, no monthly quota
- basic: monthly_quota=1,000
- pro: monthly_quota=10,000
- enterprise: monthly_quota=50,000
- free_unlimited: no limits (testing only)

Request plan resolution
- Anonymous users default to `demo`.
- Dev/test header override: `X-B2P-Plan`. This is gated by env flag `ALLOW_PLAN_OVERRIDE_HEADER=true|false` (default false). In production keep it false.

Response headers (for UI banner)
- `X-B2P-Plan`: plan id
- `X-B2P-Processed`: number of images actually exported
- `X-B2P-Saved`: number of first-time filenames saved
- `X-B2P-Duplicate`: number of duplicate filenames overwritten
- `X-B2P-Requested`: total images detected across all files in the batch
- `X-B2P-Truncated`: "true"|"false" – true if any file was truncated by per-file cap

Server-side enforcement
- Per-file cap enforced via early slicing (no work beyond cap).
- Helper `extract_images_details_with_total` returns both processed list (capped) and total available.

Security/Storage
- No persistent image storage is used; all writes are to the in-memory ZIP stream.

Testing (suggested)
- Anonymous with 6 images → processed=6, truncated=false
- Anonymous with 27 images → processed=10, truncated=true
- Override to `free_unlimited` (with flag enabled) → processed=requested, truncated=false
- Invalid override → falls back to demo


Plan limits & testing
---------------------

Server reads plan limits from env (defaults shown):

```
GUEST_FILE_LIMIT=10
BASIC_MONTHLY_LIMIT=1000
PRO_MONTHLY_LIMIT=10000
ENTERPRISE_MONTHLY_LIMIT=50000
```

Verify effective limits at runtime:

```
curl -s http://127.0.0.1:8000/health/limits | jq
```

Guest per-file cap (no user id):

```
curl -X POST http://127.0.0.1:8000/process \
  -F 'imageColumn=A' -F 'nameColumn=B' \
  -F 'files=@/absolute/path/to/gt10.xlsx' -i
```

Expect HTTP 402 JSON on files with >10 images:

```
{ "plan":"guest", "limit":10, "usage": N, "month":"YYYY-MM", "reason":"limit_exceeded" }
```

Monthly cap (signed-in): set a tiny limit temporarily and send header with a test user id:

```
export BASIC_MONTHLY_LIMIT=1  # or set enterprise_monthly_limit in users
curl -X POST http://127.0.0.1:8000/process \
  -H 'X-B2P-User: <USER_UUID>' \
  -F 'imageColumn=A' -F 'nameColumn=B' \
  -F 'files=@/absolute/path/to/ok.xlsx' -i
```

Second run should return 402 with:

```
{ "plan":"basic", "limit":1, "usage":1, "month":"YYYY-MM", "reason":"limit_exceeded" }
```


