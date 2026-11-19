# ProgImage

A REST API for uploading, storing and retrieving images, built with Django, Django REST Framework and PostgreSQL.

ProgImage stores image metadata in PostgreSQL and image files in persistent filesystem storage. It uses Django's storage abstraction to keep the application independent of the underlying storage backend.

For the design decisions, failure handling and trade-offs, see [DESIGN.md](DESIGN.md).

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

If the image cannot be stored, the API returns `503 Service Unavailable` and the client may retry:

```json
{
  "detail": "The image could not be stored. Please retry."
}
```

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

Successful responses include `Cache-Control: public, max-age=31536000, immutable`.

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
- Storage, completion and record-creation failures
- Successful image retrieval
- Unknown image IDs
- Incomplete uploads
- Missing stored files
- Reconciliation of stale pending uploads

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

## Maintenance

### Reconciling stale uploads

Uploads left `PENDING` (for example, if the process was killed mid-upload) can be cleaned up with:

```bash
# Report stale uploads without changing anything
docker compose exec api python manage.py reconcile_images --dry-run

# Mark PENDING uploads older than 15 minutes as FAILED and delete their files
docker compose exec api python manage.py reconcile_images --older-than 15
```

`--older-than` defaults to 15 minutes and must be at least 1. In production this command would run on a schedule, for example every 5 minutes.

## Project Structure

```text
ProgImage/
├── config/              # Django project configuration
├── images/
│   ├── management/      # reconcile_images command
│   ├── migrations/      # Database migrations
│   ├── tests/           # Automated tests
│   ├── models.py        # Image metadata
│   ├── serializers.py   # Upload validation
│   ├── services.py      # Storage workflow
│   ├── views.py         # API endpoints
│   └── urls.py          # API routes
├── requirements/        # Development and production dependencies
├── DESIGN.md            # Design decisions and trade-offs
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

See [DESIGN.md](DESIGN.md) for the design decisions, failure handling and known limitations.