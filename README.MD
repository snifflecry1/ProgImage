# ProgImage

A REST API for uploading, storing and retrieving images, built with Django, Django REST Framework and PostgreSQL.

ProgImage stores image metadata in PostgreSQL and image files in persistent filesystem storage. It uses Django's storage abstraction to keep the application independent of the underlying storage backend.

## Tech Stack

- Python 3.12
- Django and Django REST Framework
- PostgreSQL 17
- Pillow for image validation
- pytest and pytest-django
- Docker and Docker Compose
- Gunicorn for production serving

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### 1. Configure environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

Update `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD` in `.env`.

### 2. Start the application

```bash
docker compose up --build -d
```

This starts the Django development server and PostgreSQL.

The API is available at:

`http://localhost:8000`

### 3. Apply database migrations

```bash
docker compose exec api python manage.py migrate
```

The application is now ready to accept requests.

## API Endpoints

### POST /images/

Upload an image using a multipart form request.

**Request**

```bash
curl -X POST http://localhost:8000/images/ \
  -F "file=@/path/to/image.jpg"
```

**Successful response — 201 Created**

```json
{
  "id": "a602c1ce-3904-4c41-ac52-62901b7e5bc3"
}
```

The returned UUID identifies the uploaded image and can be used to retrieve it.

**Validation rules**

- Supported formats: JPEG, PNG and WebP
- Maximum file size: 10 MiB
- Maximum image dimensions: 25 million pixels
- File content is inspected using Pillow rather than relying on the filename extension or supplied MIME type
- Empty files and invalid image content are rejected

Invalid requests return `400 Bad Request` with validation details.

### GET /images/{id}/

Retrieve a previously uploaded image by UUID.

**Request**

```bash
curl -f \
  http://localhost:8000/images/a602c1ce-3904-4c41-ac52-62901b7e5bc3/ \
  -o downloaded-image.jpg
```

**Successful response — 200 OK**

The response contains the original image bytes with the appropriate `Content-Type` header.

Images are streamed using Django's `FileResponse` rather than being loaded entirely into application memory.

**Not found — 404**

A `404 Not Found` response is returned when:

- The image UUID does not exist
- The upload has not completed
- The underlying stored file is missing

## Running Tests

Run the test suite using the development container:

```bash
docker compose exec api pytest -v
```

The tests use pytest and pytest-django.

Test coverage includes:

- Successful image uploads
- Required file validation
- Invalid image content
- Unsupported image formats
- Storage failure handling
- Successful image retrieval
- Unknown image IDs
- Incomplete uploads
- Missing stored files

Filesystem tests use temporary storage locations to avoid modifying persistent development data.

## Production Configuration

The Dockerfile provides separate development and production build stages.

The production image:

- Runs Django through Gunicorn
- Uses a non-root application user
- Installs production dependencies only
- Uses persistent storage for uploaded images
- Supports environment-based configuration

Build and start the production stack:

```bash
docker compose -p progimage-prod \
  -f compose.prod.yaml up --build -d
```

Apply migrations:

```bash
docker compose -p progimage-prod \
  -f compose.prod.yaml exec api python manage.py migrate
```

The separate Compose project name isolates production-test volumes from the development environment.

The production Compose configuration is intended to demonstrate the production container setup locally. An internet-facing deployment would additionally require HTTPS termination, appropriate secret management and infrastructure-level security controls.

## Design Decisions

### Image storage

Image metadata is stored in PostgreSQL, while image files are stored separately using Django's `FileField` and storage API.

Each image is assigned a UUID, which is also used to construct its storage filename.

For example:

```text
images/a602c1ce-3904-4c41-ac52-62901b7e5bc3.jpg
```

This avoids depending on user-provided filenames and makes storage keys predictable.

The filesystem is backed by a persistent Docker volume so uploaded images survive container restarts.

Django's storage abstraction allows the underlying storage backend to be changed in the future without tightly coupling application logic to local filesystem paths.

### Upload lifecycle

Each upload has a status:

- `PENDING` — the metadata record has been created, but the upload has not completed
- `COMPLETED` — the image has been stored successfully
- `FAILED` — reserved for recording unsuccessful uploads

The upload flow is:

1. Validate the uploaded image.
2. Create a database record with `PENDING` status.
3. Save the file through Django's storage API.
4. Mark the database record as `COMPLETED`.
5. Return the image UUID.

Only completed images are available through the GET endpoint.

### Failure handling and consistency

PostgreSQL and filesystem storage do not participate in a shared transaction.

Consequently, a failure between writing the file and updating the database may leave a pending database record or an orphaned file.

The current implementation deliberately keeps this failure handling simple:

- Failed uploads are not exposed through the retrieval endpoint.
- Unexpected storage errors are logged and propagated.
- A failed or interrupted upload may leave a `PENDING` record for later investigation.

A production system operating at larger scale could introduce periodic reconciliation to identify stale pending records and orphaned files.

This has intentionally not been implemented to avoid introducing unnecessary background infrastructure for the scope of this service.

### Image validation

Pillow is used to identify the actual image format and verify image structure.

The API enforces file-size and pixel-count limits to reduce the risk of oversized uploads and excessive image-processing resource consumption.

Validation is performed before creating the database record or writing the image to persistent storage.

### Separation of responsibilities

The application separates its responsibilities into:

- **Views:** HTTP request and response handling
- **Serializers:** Input validation
- **Services:** Image creation and storage workflow
- **Models:** Image metadata and lifecycle state

This keeps individual components small and makes their behaviour straightforward to test.

## Known Limitations and Future Improvements

The following improvements would be appropriate for a larger production deployment:

- Automated reconciliation of stale pending uploads and orphaned files
- Object storage such as Amazon S3 for distributed deployments
- Additional monitoring and operational metrics
- Rate limiting and authentication where access controls are required
- More comprehensive image decoding checks for malformed files

These features are intentionally outside the current implementation.

## Project Structure

```text
ProgImage/
├── config/              # Django project configuration
├── images/
│   ├── migrations/      # Database migrations
│   ├── tests/           # Automated tests
│   ├── models.py        # Image metadata
│   ├── serializers.py   # Upload validation
│   ├── services.py      # Storage workflow
│   ├── views.py         # API endpoints
│   └── urls.py          # API routes
├── requirements/        # Development and production dependencies
├── Dockerfile
├── compose.yaml
├── compose.prod.yaml
├── pytest.ini
├── .env.example
└── manage.py
```

## Summary

ProgImage provides a small, focused image storage API with persistent storage, input validation, explicit upload states and automated tests.

The implementation prioritises correctness, maintainability and clear failure behaviour while avoiding infrastructure that is unnecessary for the project's scope.