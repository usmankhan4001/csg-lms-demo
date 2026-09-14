# Object storage — R2, AWS S3, MinIO

Uploaded media, course transfer archives, SQLite playground databases and
**LiveKit class recordings** all go to object storage. Until one is configured
the app stays on the local filesystem, and class recording reports
`UNAVAILABLE` rather than failing — deliberately, so a teacher is not sent
chasing a fault that is really an unset variable.

Three backends are supported. Only MinIO needs an extra service.

---

## Before anything else: this was broken until 2026-09-14

If you configured storage before that date and it never worked, this is why.
Three separate name mismatches meant **an operator who set every documented
variable still got no storage at all**:

| The compose files set | The code read | Result |
|---|---|---|
| `LEARNHOUSE_STORAGE_TYPE` | `LEARNHOUSE_CONTENT_DELIVERY_TYPE` | backend never switched off `filesystem` |
| `S3_BUCKET_NAME`, `S3_ENDPOINT_URL` | `LEARNHOUSE_S3_API_*` | bucket and endpoint always empty |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | boto3's ambient `AWS_*` chain | **no credentials reached boto3** |

All three spellings are now accepted. Nothing needs renaming.

---

## Variables

Set these on the `api` service. The short `S3_*` names are the recommended
spelling; `LEARNHOUSE_S3_API_*` and `AWS_*` also work.

| Variable | Required | Notes |
|---|---|---|
| `LEARNHOUSE_STORAGE_TYPE` | yes | `s3api` to enable. `local` / `filesystem` to disable. |
| `S3_ENDPOINT_URL` | R2, MinIO | **Omit the bucket** — see the trap below. AWS can leave this unset. |
| `S3_ACCESS_KEY_ID` | yes | |
| `S3_SECRET_ACCESS_KEY` | yes | |
| `S3_BUCKET_NAME` | yes | |
| `S3_REGION` | yes | `auto` for R2; the real region for AWS; anything for MinIO. |
| `S3_ADDRESSING_STYLE` | **MinIO** | `path`. Leave unset for R2 and AWS. |
| `S3_PUBLIC_DOMAIN` | no | CDN domain for public URLs. Unset means no public URL is produced — deliberately, since a guessed one 404s. |

---

## ⚠️ The endpoint trap — silent, and it corrupts every key

**Cloudflare's dashboard shows the R2 endpoint with the bucket appended:**

```
https://<account-id>.r2.cloudflarestorage.com/s3-testing
                                             ^^^^^^^^^^^ remove this
```

Pasting that verbatim while also setting `S3_BUCKET_NAME` makes boto3 append
the bucket a second time. An object meant for `avatars/1.png` is stored at
`s3-testing/avatars/1.png`.

**It does not raise an error.** Verified against a live MinIO: the upload
returns success, and only the public URL and any read by the correct key fail —
so the misconfiguration surfaces days later as missing files.

The config layer now detects an endpoint ending in the bucket name, strips it,
and logs a warning. Check your startup logs for:

```
WARNING  S3 endpoint ended with the bucket name (...); using ... instead.
```

If you see it, fix the variable — the guard is a safety net, not a licence to
leave it wrong.

---

## Cloudflare R2

```bash
LEARNHOUSE_STORAGE_TYPE=s3api
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com   # no bucket
S3_ACCESS_KEY_ID=<r2 access key id>
S3_SECRET_ACCESS_KEY=<r2 secret>
S3_BUCKET_NAME=<your bucket>
S3_REGION=auto
S3_PUBLIC_DOMAIN=https://<your cdn domain>
```

R2 requires SigV4 and the `auto` region. Both are set by the shared client;
without them R2 rejects presigned URLs with 401.

## AWS S3

```bash
LEARNHOUSE_STORAGE_TYPE=s3api
S3_ACCESS_KEY_ID=<aws access key id>
S3_SECRET_ACCESS_KEY=<aws secret>
S3_BUCKET_NAME=<your bucket>
S3_REGION=<your region>          # a real region, not "auto"
```

Leave `S3_ENDPOINT_URL` unset so boto3 resolves the regional endpoint itself.

## MinIO (self-hosted)

For a school that wants no cloud account. Set your own credentials — there are
no defaults, by design:

```bash
MINIO_ROOT_USER=<choose one>
MINIO_ROOT_PASSWORD=<choose one, 8+ characters>
S3_BUCKET_NAME=csg-lms-storage
```

```bash
docker compose -f docker-compose.local.yml -f docker-compose.minio.yml up -d
```

The overlay sets `S3_ADDRESSING_STYLE=path`, points the API at
`http://minio:9000`, and creates the bucket via a one-shot `mc` container that
uses `mb --ignore-existing` — so it is a no-op on every subsequent start and
there is no manual setup step to forget.

Console: `http://localhost:9001`.

**Why path-style matters:** botocore's `auto` resolves to virtual-hosted
addressing for a custom endpoint, producing `bucket.minio` — a hostname that
does not resolve. The resulting error looks like a network failure and mentions
nothing about addressing, which makes it expensive to diagnose.

---

## Verify it actually works

Configuration that looks right and was never exercised has shipped from this
repo before. Prove it instead:

```bash
docker compose exec api python -c "
from src.services.utils.s3_client import build_s3_client, get_s3_bucket_name
c = build_s3_client(); b = get_s3_bucket_name()
c.put_object(Bucket=b, Key='healthcheck/probe.txt', Body=b'ok')
print('read back:', c.get_object(Bucket=b, Key='healthcheck/probe.txt')['Body'].read().decode())
print('bucket:', b)
"
```

Expected: `read back: ok`.

Then confirm the key is where you expect — this is what catches the endpoint
trap, because the upload above succeeds either way:

```bash
docker compose exec api python -c "
from src.services.utils.s3_client import build_s3_client, get_s3_bucket_name
c = build_s3_client()
for o in c.list_objects_v2(Bucket=get_s3_bucket_name()).get('Contents', []):
    print(o['Key'])
"
```

Expected: `healthcheck/probe.txt`. If you see `<bucket>/healthcheck/probe.txt`,
your endpoint still contains the bucket name.

---

## Implementation

`src/services/utils/s3_client.py` builds every client. It replaced four
hand-rolled `boto3.client("s3", ...)` calls that had already drifted — the
course-transfer path set SigV4 and a region (needed for R2), while the upload
and playground paths set neither, so an object could be written with one
configuration and read with another.

Call sites: `services/utils/upload_content.py` (×2),
`services/courses/transfer/storage_utils.py`, `routers/code_execution.py`.
`services/sms/live_class_recording.py` passes credentials to LiveKit's egress
service rather than to boto3, so it reads the same config without using the
client.
