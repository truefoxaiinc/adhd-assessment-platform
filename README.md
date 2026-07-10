# ADHD-Minder Backend API

ADHD-Minder is a Django REST Framework backend for user authentication, self-assessment, scoring, learning progress tracking, file/content delivery, and storing frontend-submitted attention summaries.

The backend supports:

- JWT authentication and password reset flows.
- Self-assessment questions, responses, scoring, and progress.
- ADHD content listing and lock/unlock logic based on user progress.
- Frontend-submitted attention score and session summary storage.
- Learning progress updates after video/file completion.
- Swagger API documentation.
- Redis-backed Channels and cache support.
- Optional AWS S3 media/file storage.

## Tech Stack

- Python 3.11
- Django 5.x
- Django REST Framework
- SimpleJWT
- Django Channels
- Daphne
- Redis
- PostgreSQL or SQLite, depending on settings
- drf-yasg Swagger docs
- Docker and Docker Compose

## Project Structure

```text
ADHD-Minder-backend/
  apps/
    authentication/    Login, logout, JWT authentication
    users/             Custom user model and profile APIs
    assessment/        Self-assessment questions, responses, scoring
    filehandler/       ADHD content/file listing and S3 helpers
    progresstracker/   User learning progress and attention sessions
    websocket/         Channels routing and middleware for future websocket features
    articles/          Article APIs
  helpers/             Shared response, auth, exception helpers
  services/            Business logic services
  project_adhd/        Django settings, urls, ASGI/WSGI
```

## Environment Variables

Create a `.env` file in the project root. Use `.env.example` as the base.

Minimum example:

```env
DJANGO_ENV=development
SECRET_KEY=your_django_secret_key
DEBUG=True

DB_NAME=truefoxai_db
DB_USER=postgres
DATABASE_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432

JWT_SIGNING_KEY=your_jwt_secret

AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_STORAGE_BUCKET_NAME=s-adhd
AWS_S3_REGION_NAME=us-east-1

REDIS_CACHE_URL=redis://127.0.0.1:6379/1
CELERY_BROKER_URL=redis://127.0.0.1:6379/2
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2

EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your_email
EMAIL_HOST_PASSWORD=your_email_password
EMAIL_PORT=587
DEFAULT_FROM_EMAIL=your_email

FIREBASE_CREDENTIALS_PATH=files/attentionminder-3f4d6-firebase-adminsdk-fbsvc-704503bc6e.json
```

Production deployments must set required secrets explicitly. When `DJANGO_ENV=production`, missing values such as `SECRET_KEY`, `DATABASE_PASSWORD`, `JWT_SIGNING_KEY`, and `EMAIL_HOST_PASSWORD` fail fast during startup.

## Running With Docker

Make sure Docker Desktop is running.

```bash
docker-compose up --build
```

The API will be available at:

```text
http://127.0.0.1:8000/api/docs/
```

The legacy face-detection WebSocket endpoint is disabled. Frontend clients should perform detection locally and submit final metrics through the REST API.

## Running Natively

Install Python 3.11 first.

```bash
python -m venv venv
```

Activate the environment.

Windows:

```powershell
.\venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run migrations:

```bash
python manage.py migrate
```

Run the normal HTTP development server:

```bash
python manage.py runserver
```

For WebSocket support, run Daphne:

```bash
daphne -b 0.0.0.0 -p 8000 project_adhd.asgi:application
```

## Redis Configuration

For native/server deployment where Redis runs on the same machine:

```python
"hosts": [("127.0.0.1", 6379)]
```

For Docker Compose internal networking, the Redis service name can be used:

```python
"hosts": [("redis", 6379)]
```

Current server-oriented setting:

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}
```

## API Documentation

Swagger UI:

```text
http://localhost:8000/api/docs/
```

Production example:

```text
http://13.217.234.177/api/docs/
```

## Authentication

The API uses JWT authentication with SimpleJWT.

HTTP APIs expect:

```http
Authorization: Bearer ACCESS_TOKEN
```

The backend no longer accepts webcam frames over WebSockets. Do not send `user_id` from the client for score or progress updates; the backend reads the authenticated user from the JWT.

## Main REST API Modules

### Authentication

Base path:

```text
/api/auth/
```

Handles login, logout, refresh/blacklist flows, and password reset related actions.

### Users

Base path:

```text
/api/users/v1/users/
```

Common APIs:

```text
registration
update-profile
get-user-profile
password-reset/request
password-reset/otp-verify
password-reset/change
social-login
```

#### Password Reset Flow

Password reset is a two-step verified flow. The backend does not allow password reset using email alone.

Request OTP:

```text
POST /api/users/v1/users/password-reset/request
```

```json
{
  "email": "user@example.com"
}
```

Verify OTP and receive a one-time reset token:

```text
POST /api/users/v1/users/password-reset/otp-verify
```

```json
{
  "email": "user@example.com",
  "otp": "123456"
}
```

Successful response:

```json
{
  "status": true,
  "status_code": 200,
  "message": "Success",
  "data": {
    "reset_token": "one-time-reset-token"
  },
  "errors": {}
}
```

Change password:

```text
POST /api/users/v1/users/password-reset/change
```

```json
{
  "email": "user@example.com",
  "reset_token": "one-time-reset-token",
  "password": "NewPassword123!"
}
```

Security notes:

- OTP values are hashed before storage.
- Reset tokens are hashed before storage.
- Reset tokens expire and are one-time use.
- A password reset without `reset_token` is rejected.

#### Public Registration Security

Public registration creates only normal non-staff users. The API does not allow clients to set or modify:

```text
id
is_staff
is_admin
is_superuser
is_active
groups
user_permissions
```

### Assessment

Base path:

```text
/api/assessment/v1/self-assessment/
```

Endpoints:

```text
GET  get-questions
POST save-response
GET  fetch-result
GET  progress
```

The assessment app:

- Fetches adult or child/adolescent questions based on user age.
- Saves user responses.
- Calculates assessment score.
- Returns latest result.
- Returns progress for mobile UI.

Example save response payload:

```json
{
  "assesment": [
    {
      "question": 1,
      "response": "2",
      "text_response": "optional"
    }
  ]
}
```

Note: The current API key is `assesment` for compatibility with existing code.

### Filehandler

Base path:

```text
/api/filehandler/v1/filehandler/
```

Enabled endpoints:

```text
GET  list-files
GET  save-feedback
POST update-learning-progress/
```

`list-files` returns ADHD content filtered by:

- authenticated user's age group
- `is_management=true|false`
- progress-based unlocked days

Example:

```text
GET /api/filehandler/v1/filehandler/list-files?is_management=true
```

### Frontend Attention Score

Face/attention detection runs entirely in the frontend. After a video or assessment session completes, submit the final frontend-calculated metrics:

```text
POST /api/assessment/v1/ai-assessment/save-score
```

All listed fields are required. Send `0` for numeric telemetry values that do not apply.

Example payload:

```json
{
  "session_id": "frontend-session",
  "file_id": 12,
  "is_assessment": true,
  "final_score": 80,
  "attention_engagement_rate": 90,
  "average_confidence": 0.85,
  "total_processed_frames": 120,
  "sampled_frames": 120,
  "session_duration_seconds": 300,
  "inattention_duration": 20,
  "gaze_ratio_avg": 0,
  "drowsy_state": 0,
  "brightness_score": 0,
  "pitch": 0,
  "yaw": 0,
  "roll": 0,
  "blink_ratio": 0,
  "yawn_distance": 0,
  "bad_frame_count": 0,
  "blurry_frame_count": 0,
  "low_light_frame_count": 0,
  "eyes_closed_count": 0,
  "gaze_warning_count": 0
}
```

## Assessment Score Calculation

The assessment scoring follows the provided assessment PDF.

Response scale:

```text
0 = Never
1 = Rarely
2 = Sometimes
3 = Often
4 = Very Often
```

There are 21 items for adults and 21 items for kids.

Reverse-scored questions:

```text
N1 to N9
```

Reverse scoring rule:

```text
scored_value = 4 - response
```

Normal questions use:

```text
scored_value = response
```

Final calculation:

```text
Raw Total = sum(scored values)
TenScore = round((Raw Total / 84) * 10)
```

Program duration:

```text
0-4  => Severe difficulty       => 3-month program
5-6  => Moderate difficulty     => 2-month program
7-8  => Mild difficulty         => 1-month program
9-10 => Satisfactory to strong  => maintenance only
```

The result label is saved into `SelfAssessmentResult.result`.

## WebSocket Face Detection API

The legacy `/ws/face-detection/` endpoint has been removed. The backend must not receive webcam frames or run attention detection. Clients should run detection locally and submit only final session metrics through the REST score-save endpoint.

## Error Response Format

Unexpected internal API errors use a safe response format:

```json
{
  "success": false,
  "message": "Internal server error",
  "code": "INTERNAL_ERROR"
}
```

Internal details such as filenames, line numbers, traceback text, exception class names, and raw internal errors are logged server-side only and are not returned to clients.

## Deployment Notes

For a server deployment using systemd, restart after code/config changes:

```bash
sudo systemctl restart adhd
```

Manual Daphne command:

```bash
daphne -b 0.0.0.0 -p 8000 project_adhd.asgi:application
```

Make sure Redis is running:

```bash
redis-cli ping
```

Expected response:

```text
PONG
```

## Useful Commands

Run migrations:

```bash
python manage.py migrate
```

Create superuser:

```bash
python manage.py createsuperuser
```

Collect static files:

```bash
python manage.py collectstatic --noinput
```

Run Django checks:

```bash
python manage.py check
```

Run tests:

```bash
python -m pytest
```

## Troubleshooting

### Frontend score save returns unauthorized

Cause: token is missing, expired, invalid, or not accepted by JWT authentication.

Fix: send a valid bearer token with the REST request.

### Redis connection fails

If running natively, use:

```python
"hosts": [("127.0.0.1", 6379)]
```

If running inside Docker Compose, use:

```python
"hosts": [("redis", 6379)]
```

### Docker cannot connect

Start Docker Desktop, then run:

```bash
docker-compose up --build
```

### Native Python does not run

Install Python 3.11 and recreate the virtual environment:

```bash
python -m venv venv
```

## Notes

- Keep secrets out of Git.
- Use `.env` for credentials and deployment configuration.
- Use Daphne only if future non-detection WebSocket features are added.
- Do not trust `user_id` from client payloads for progress or score updates.
- Password reset requires the one-time `reset_token` returned by OTP verification.
