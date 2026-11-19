# ProgImage Design

This document explains the design decisions and trade-offs behind ProgImage. For setup, API usage and operations, see the [README](README.MD).

## Image storage

Image metadata is stored in PostgreSQL, while image files are stored separately using Django's `FileField` and storage API.

Each image is assigned a UUID, which is also used to construct its storage filename.

For example:

```text
images/a602c1ce-3904-4c41-ac52-62901b7e5bc3.jpg
```

This avoids depending on user-provided filenames and makes storage keys predictable.

The filesystem is backed by a persistent Docker volume so uploaded images survive container restarts.

Django's storage abstraction allows the underlying storage backend to be changed in the future without tightly coupling application logic to local filesystem paths.

## Upload lifecycle

Each upload has a status:

- `PENDING` — the metadata record has been created, but the upload has not completed
- `COMPLETED` — the image has been stored successfully
- `FAILED` — storage or completion failed; any written file has been removed

The upload flow is:

1. Validate the uploaded image.
2. Create a database record with `PENDING` status.
3. Save the file through Django's storage API.
4. Mark the database record as `COMPLETED`.
5. Return the image UUID.

Only completed images are available through the GET endpoint.

## Failure handling and consistency

PostgreSQL and filesystem storage do not participate in a shared transaction.

Consequently, a failure between writing the file and updating the database may leave a pending database record or an orphaned file.

Failures are handled as follows:

- If storage or the completion update fails, the error is logged, the record is marked `FAILED`, any written file is deleted, and the API returns `503 Service Unavailable`.
- The file is only deleted after the record is confirmed `FAILED`, so a `COMPLETED` record never loses its file.
- A `PENDING` record is only left behind if the database is unavailable during cleanup or the process is killed mid-upload.
- Failed and pending uploads are not exposed through the retrieval endpoint.

## Reconciliation

Uploads left `PENDING` (for example, the database was unavailable during cleanup or the process was killed) are recovered by the `reconcile_images` management command. Usage is described in the [README](README.MD#maintenance).

Stale `PENDING` records are marked `FAILED` and any written file is deleted. They are not promoted to `COMPLETED`: the client never received the image ID, and the file may be partially written.

The command is safe to run concurrently with uploads and with itself, because each record only changes state through a conditional update. In production it would run on a schedule, for example every 5 minutes with cron or a Kubernetes CronJob.

A `(status, created_at)` index keeps the stale-upload query efficient as the table grows.

## Database connections

Connections are reused for up to 60 seconds (`CONN_MAX_AGE`, configurable with `POSTGRES_CONN_MAX_AGE`), and `CONN_HEALTH_CHECKS` checks a reused connection before each request, so a database restart or idle timeout causes a reconnect instead of a failed request.

Application-level retries are deliberately not implemented. Retrying is only safe for steps that can be repeated without side effects (the initial insert and the conditional completion update), and retrying a whole upload without idempotency keys would create duplicate images. A failure mid-request returns `503`, and reconciliation guarantees that no record is left inconsistent.

## Caching

A completed image never changes for its UUID, so successful GET responses are marked `public, max-age=31536000, immutable`. Browsers and CDNs can cache them for a year without revalidating.

`404` responses are not cached this way, because a pending image may complete later.

## Image validation

Pillow is used to identify the actual image format and verify image structure.

The API enforces file-size and pixel-count limits to reduce the risk of oversized uploads and excessive image-processing resource consumption.

Validation is performed before creating the database record or writing the image to persistent storage.

## Separation of responsibilities

The application separates its responsibilities into:

- **Views:** HTTP request and response handling
- **Serializers:** Input validation
- **Services:** Image creation and storage workflow
- **Models:** Image metadata and lifecycle state

This keeps individual components small and makes their behaviour straightforward to test.

## Known limitations and future improvements

The following improvements would be appropriate for a larger production deployment:

- Extended reconciliation: `COMPLETED` records whose file is missing, files with no matching record, and purging old `FAILED` records
- Object storage such as Amazon S3 for distributed deployments
- Additional monitoring and operational metrics
- Rate limiting and authentication where access controls are required
- More comprehensive image decoding checks for malformed files

These features are intentionally outside the current implementation.
