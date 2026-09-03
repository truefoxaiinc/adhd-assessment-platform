# ADHD-Minder Backend

ADHD-Minder is a Django REST Framework backend for the Attention Minder mobile app. It handles authentication, user profile management, self-assessment questionnaires, learning progress, ADHD content delivery, frontend-submitted attention scores, management activity scores, articles, cache-backed dashboards, and Google Play account deletion compliance.

The backend is intentionally API-first. Face and attention detection are performed in the frontend; the backend stores the final telemetry submitted by the app.

## Current Production URLs

```text
API docs:              https://attention.truefoxaiinc.com/api/docs/
Support page:          https://attention.truefoxaiinc.com/attention-minder-support/
Account deletion page: https://attention.truefoxaiinc.com/account-deletion/
Account deletion alias: https://attention.truefoxaiinc.com/delete-account/
```

## Tech Stack

```text
Python 3.11
Django 5.x
Django REST Framework
SimpleJWT
Daphne / ASGI
Django Channels
Redis
PostgreSQL
django-redis
drf-yasg Swagger
WhiteNoise
django-cors-headers
AWS S3 / django-storages
Unfold admin
Docker / Docker Compose
```

## High-Level Architecture

```text
Mobile app / admin / Play Store
        |
        v
HTTP(S) / REST / public pages
        |
        v
project_adhd.urls
        |
        +-- /api/auth/              -> apps.authentication
        +-- /api/users/             -> apps.users
        +-- /api/assessment/        -> apps.assessment
        +-- /api/filehandler/       -> apps.filehandler
        +-- /api/progresstracker/   -> apps.progresstracker
        +-- /api/articles/          -> apps.articles
        +-- /api/docs/              -> Swagger
        +-- /attention-minder-support/ -> public App Store support page
        +-- /account-deletion/      -> public Google Play deletion page
        |
        v
Services / serializers / permissions
        |
        +-- PostgreSQL for persistent data
        +-- Redis for API response cache and Channels layer
        +-- S3 for media/file storage when configured
        +-- SMTP for password reset OTP email
```

## Project Structure

```text
ADHD-Minder-backend/
  apps/
    authentication/    Login, logout, JWT token handling
    users/             Custom user model, profile, social login, password reset, account deletion
    assessment/        Self-assessment questions, responses, scoring, AI score APIs, dashboards
    filehandler/       ADHD content catalog, feedback, progress update helpers
    progresstracker/   Course progress, goals, attention sessions, activity sessions
    articles/          Article list API and article cache invalidation
    websocket/         Channels routing for non-detection websocket features
  helpers/             Shared response format, auth helpers, exception handling
  services/            Business logic services such as assessment scoring
  templates/           Admin, payment result, email, and account deletion HTML templates
  project_adhd/        Django settings, URL routing, ASGI/WSGI, middleware
```

## Runtime Settings

Settings are split under `project_adhd/settings/`.

Important settings:

```text
AUTH_USER_MODEL = users.Users
ASGI_APPLICATION = project_adhd.asgi.application
ROOT_URLCONF = project_adhd.urls
REST_FRAMEWORK default auth = JWTAuthentication + TokenAuthentication
SIMPLE_JWT auth rule = active_not_deleted_user_authentication_rule
DATABASES default = PostgreSQL
CACHES default = Redis via django_redis
CHANNEL_LAYERS default = Redis via channels_redis
X_FRAME_OPTIONS = SAMEORIGIN
```

Allowed hosts and browser origins are environment-driven with production defaults that include:

```text
attention.truefoxaiinc.com
https://attention.truefoxaiinc.com
```

## Environment Variables

Create a `.env` file in the project root. Use `.env.example` as the base if available.

Minimum example:

```env
DJANGO_ENV=development
SECRET_KEY=your_django_secret_key
DEBUG=True

ALLOWED_HOSTS=localhost,127.0.0.1,13.217.234.177,attention.truefoxaiinc.com
CSRF_TRUSTED_ORIGINS=https://13.217.234.177,https://attention.truefoxaiinc.com
CORS_ALLOWED_ORIGINS=https://13.217.234.177,https://attention.truefoxaiinc.com

DB_NAME=truefoxai_db
DB_USER=postgres
DATABASE_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432

JWT_SIGNING_KEY=your_jwt_secret

GOOGLE_OAUTH_CLIENT_IDS=your_google_web_client_id,your_google_ios_client_id
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
APPLE_OAUTH_CLIENT_IDS=com.your.ios.bundle.id,com.your.apple.service.id

REDIS_CACHE_URL=redis://127.0.0.1:6379/1
CELERY_BROKER_URL=redis://127.0.0.1:6379/2
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2

AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_STORAGE_BUCKET_NAME=s-adhd
AWS_S3_REGION_NAME=us-east-1

EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your_email
EMAIL_HOST_PASSWORD=your_email_app_password
EMAIL_PORT=587
DEFAULT_FROM_EMAIL=your_email

```

Production deployments must set required secrets explicitly. When `DJANGO_ENV=production`, missing values such as `SECRET_KEY`, `DATABASE_PASSWORD`, `JWT_SIGNING_KEY`, and `EMAIL_HOST_PASSWORD` fail fast during startup.

## Backend Apps

### Authentication

Base path:

```text
/api/auth/v1/
```

Endpoints:

```text
POST login/
POST logout/
```

Responsibilities:

```text
Authenticate users
Issue JWT tokens
Reject inactive users
Support logout/blacklist flow where configured
```

### Users

Base path:

```text
/api/users/v1/users/
```

Endpoints:

```text
POST registration
POST update-profile
GET  get-user-profile
POST password-reset/request
POST password-reset/otp-verify
POST password-reset/change
POST social-login
POST delete-account
```

Responsibilities:

```text
Custom user model
Profile details
Password reset OTP and reset token flow
Google/Facebook/Apple social login
Account deactivation and soft deletion
Goal flags such as is_first and is_last
```

### Push Notifications

Flutter registers each installation after login and whenever FCM refreshes the token:

```text
POST   /api/notifications/v1/devices/register/
DELETE /api/notifications/v1/devices/unregister/
```

Register request:

```json
{
  "token": "fcm-token-from-device",
  "platform": "android",
  "device_id": "installation-specific-id"
}
```

The authenticated JWT user owns the device registration; the client does not send `user_id`.
The backend can call `apps.notifications.services.notify_user()` from trusted events. Invalid
or unregistered FCM tokens are disabled automatically. Do not expose a public endpoint that
accepts arbitrary notification recipients or message content.

Pending activity reminders are checked every 15 minutes by Celery Beat and can also be
checked for the authenticated user through:

```text
POST /api/notifications/v1/pending-activities/check/
```

The backend sends once per user/unlocked day only when the unlocked day is greater than one
and an activity from an earlier management day remains incomplete. Run both Celery worker
and Celery Beat in production for automatic reminders.

Social login request:

```json
{
  "provider": "google",
  "id_token": "google_id_token_from_frontend"
}
```

The client must send the Google ID token (JWT credential), not a Google access
token or authorization code. The backend verifies its signature, expiry,
issuer, audience, and verified email before issuing the application's JWT
access and refresh tokens. Configure every accepted frontend client:

```text
GOOGLE_OAUTH_CLIENT_IDS=web-client.apps.googleusercontent.com,ios-client.apps.googleusercontent.com
```

Apple social login can additionally provide the name returned on first
authorization:

```json
{
  "provider": "apple",
  "id_token": "apple_identity_token_from_frontend",
  "full_name": {
    "givenName": "Optional Apple given name from first authorization",
    "familyName": "Optional Apple family name from first authorization"
  },
  "username": "Optional preferred username"
}
```

Apple login notes:

```text
APPLE_OAUTH_CLIENT_IDS must contain the allowed Apple token audience values.
For iOS apps this is usually the bundle id, and for web flows this is the Apple Services ID.
Apple may only send email on the first authorization, so first login must include email or the Apple account must already be linked.
```

### Native in-app subscriptions

#### Guest purchase and restore flow

Purchase verification accepts authenticated users and guests. Guests do not send
an application account identifier. The App Store signed transaction or Google
Play purchase token is the proof of purchase.

`POST /api/payments/v1/payments/verify-in-app-purchase/`

```json
{
  "platform": "ios",
  "product_id": "attentionminder.monthly",
  "transaction_id": "APPLE_TRANSACTION_ID",
  "verification_data": "SIGNED_TRANSACTION_OR_RECEIPT_DATA",
  "verification_source": "app_store",
  "is_restore": false
}
```

An unauthenticated successful verification returns `data.entitlement_token`,
`data.subscription_status`, `data.expires_at`, and `data.is_guest`. Store the
opaque token securely and send it on subsequent requests using either:

```http
Authorization: Bearer GUEST_ENTITLEMENT_TOKEN
```

or `X-Entitlement-Token`. Restore uses the same verification request with
`is_restore: true`. Repeating valid store evidence is idempotent and returns the
existing entitlement with a newly rotated guest token.

Check access with `GET /api/payments/v1/payments/entitlement/`. Missing or invalid
tokens return `401`; inactive entitlements return `403`; invalid store evidence
returns `422`; and store verification/configuration failures return `500`.

After registration, authenticate with the user's normal bearer token and call:

`POST /api/payments/v1/payments/link-guest-entitlement/`

```json
{"entitlement_token": "GUEST_ENTITLEMENT_TOKEN"}
```

The operation atomically transfers the subscription and supported progress.
An entitlement already linked to another account returns `409`.

The app verifies Google Play and App Store subscriptions before granting an
entitlement. The authenticated user comes only from the bearer token.

```http
POST /api/payments/v1/payments/verify-in-app-purchase/
Authorization: Bearer <access-token>
Content-Type: application/json
```

Android request (the Flutter `serverVerificationData` value is the purchase
token):

```json
{
  "platform": "android",
  "product_id": "attentionminder.monthly",
  "purchase_id": "GPA order id when available",
  "purchase_token": "google-play-purchase-token",
  "verification_source": "google_play",
  "is_restore": false
}
```

iOS request. Send the StoreKit 2 signed transaction as `verification_data`
when available; otherwise the backend looks up `transaction_id` through the
App Store Server API:

```json
{
  "platform": "ios",
  "product_id": "attentionminder.monthly",
  "transaction_id": "app-store-transaction-id",
  "verification_data": "optional-Apple-signed-transaction-JWS",
  "verification_source": "app_store",
  "is_restore": false
}
```

Successful response data:

```json
{
  "verified": true,
  "subscription_status": "active",
  "platform": "android",
  "product_id": "attentionminder.monthly",
  "expires_at": "2026-09-10T12:00:00Z"
}
```

Current entitlement: `GET /api/payments/v1/payments/entitlement/`.

Lifecycle webhooks:

- Google RTDN push URL: `/api/payments/v1/payments/notifications/google-play/`
  with the configured token as `X-Goog-Verification-Token`.
- App Store Server Notifications V2 URL:
  `/api/payments/v1/payments/notifications/app-store/`.

Before starting a purchase, fetch user-safe store identifiers from
`GET /api/payments/v1/payments/purchase-account-identifiers/` and pass the
Google value as `obfuscatedAccountId` and the Apple value as
`appAccountToken`/`applicationUserName`. Then set
`STORE_REQUIRE_ACCOUNT_ASSOCIATION=True`. This prevents a valid store purchase from being transferred between
application accounts. Store credentials, Apple private keys, and root
certificates must be mounted secrets, never committed files.

Account deletion requires the current password:

```json
{
  "action": "delete",
  "password": "CurrentPassword123!"
}
```

`deactivate` sets `is_active=false`. `delete` sets `is_active=false` and `is_deleted=true`.

### Assessment

Base path:

```text
/api/assessment/v1/
```

Self-assessment endpoints:

```text
GET  self-assessment/get-questions
POST self-assessment/save-response
GET  self-assessment/fetch-result
GET  self-assessment/result-history
GET  self-assessment/progress
```

AI/management endpoints:

```text
GET  ai-assessment/score-history
POST ai-assessment/save-score
GET  management/dashboard
GET  management/latest-week
POST management/activity-score
```

Responsibilities:

```text
Question listing by age group
Response saving
Progress tracking for incomplete questionnaires
Assessment result calculation
Frontend attention telemetry storage
Management dashboard aggregation
Management activity score storage
Cache-backed read APIs
```

Age categories:

```text
age < 11        -> child
11 <= age < 16  -> adolescents
age >= 16       -> adult
```

Questions are stored with `SelfAssessmentQuestions.age_group`. Legacy `is_for_adults=true` questions map to `adult`; legacy `false` questions map to `child`.

### Filehandler

Base path:

```text
/api/filehandler/v1/filehandler/
```

Endpoints:

```text
GET  list-files
GET  save-feedback
POST update-learning-progress/
```

Responsibilities:

```text
ADHD content catalog
Assessment and management content listing
Age-group based content filtering
Progress-based locked/unlocked day calculation
Feedback storage
S3 upload helpers where enabled
```

`list-files` filters by:

```text
authenticated user's age group
is_management=true|false
unlocked days from progress
```

### Progresstracker

Base path:

```text
/api/progresstracker/v1/progress-track/
```

Endpoints:

```text
POST save-daily-status
GET  goals
POST goals
PUT  goals/<goal_id>
PATCH goals/<goal_id>
```

Responsibilities:

```text
Daily progress records
Course day completion state
User goals and ratings
FaceAttentionSession storage
ManagementActivitySession storage
Management cache invalidation signals
```

### Articles

Base path:

```text
/api/articles/v1/
```

Endpoints:

```text
GET list
```

Responsibilities:

```text
Paginated article listing
Status/featured/search filters
Redis-backed article response cache
Article cache invalidation signals
```

### Websocket

The legacy face-detection websocket endpoint has been removed. The backend must not receive webcam frames or run OpenCV/MediaPipe/dlib attention detection.

Current architecture:

```text
Frontend performs detection
Frontend calculates final attention score and telemetry
Backend validates shape/ranges
Backend stores submitted telemetry
```

## Database Architecture

The default database engine is PostgreSQL.

Connection settings:

```text
DB_NAME
DB_USER
DATABASE_PASSWORD or DB_PASSWORD
DB_HOST
DB_PORT
```

Important tables and ownership:

```text
Users
  Custom auth user, profile, soft-delete flags, assessment score, onboarding flags

OAuthAccount
  Social login provider link for a user. Supported providers: google, facebook, apple

PasswordResetOTP
  Hashed OTP and reset-token state for password reset

SelfAssessmentQuestions
  Question bank with category and age_group

SelfAssessmentResult
  One assessment attempt/result for a user

SelfAssessmentResponse
  Per-question answer linked to an assessment result

AdhdContent
  Assessment/management content catalog: video, document, file, activity

FeedbackReview
  User feedback for AI assessment/content experience

FaceAttentionSession
  Frontend-submitted attention score and telemetry

ManagementActivitySession
  Frontend-submitted management activity score telemetry

ProgressTracker
  User/day/file progress record

UserAssessmentDetails
  Course-level progress summary and last completed day

UserGoal
  User-created goals and ratings

Article
  Article CMS records
```

## Redis Architecture

Redis is used for two separate backend concerns:

```text
1. Django cache through django_redis
2. Django Channels layer through channels_redis
```

Django cache settings:

```text
BACKEND: django_redis.cache.RedisCache
LOCATION: REDIS_CACHE_URL, default redis://127.0.0.1:6379/1
KEY_PREFIX: adhd
```

Channels layer settings:

```text
BACKEND: channels_redis.core.RedisChannelLayer
HOST: 127.0.0.1:6379
```

Redis health check:

```bash
redis-cli ping
```

Expected:

```text
PONG
```

## Cache Behaviour

Cached API responses keep the same response structure as uncached responses.

Default cache timeout:

```text
15 minutes
```

Cached APIs:

```text
GET /api/assessment/v1/self-assessment/get-questions
GET /api/assessment/v1/self-assessment/fetch-result
GET /api/assessment/v1/self-assessment/progress
GET /api/assessment/v1/management/latest-week
GET /api/articles/v1/list
```

Flow:

```text
Request arrives
Cache key is generated from user/version/query params
If cache hit: return Redis response
If cache miss: query DB, build response, store in Redis
```

Invalidation is signal-based. Related database changes bump a cache version key. Old Redis entries may remain until timeout, but the API stops using them because the generated key changes.

Assessment invalidation:

```text
SelfAssessmentQuestions save/delete   -> question cache version bump
SelfAssessmentResult save/delete      -> that user's result/progress cache version bump
SelfAssessmentResponse save/delete    -> that user's result/progress cache version bump
```

Management invalidation:

```text
FaceAttentionSession save/delete      -> that user's management cache version bump
ManagementActivitySession save/delete -> that user's management cache version bump
ProgressTracker save/delete           -> that user's management cache version bump
UserAssessmentDetails save/delete     -> that user's management cache version bump
AdhdContent management save/delete    -> global management cache version bump
```

Article invalidation:

```text
Article save/delete -> article list cache version bump
```

Manual cache clear after deployment when cache-key fields or response fields change:

```bash
python manage.py shell
```

```python
from django.core.cache import cache
cache.clear()
```

## Authentication And Security

Authentication uses SimpleJWT.

Requests to protected APIs must include:

```http
Authorization: Bearer <access_token>
```

JWT settings:

```text
Access token lifetime: 20 days
Refresh token lifetime: 50 days
User id claim: user_id
Authentication rule: active_not_deleted_user_authentication_rule
```

Inactive and soft-deleted users are rejected:

```text
is_active=false -> rejected
is_deleted=true -> rejected
```

Security hardening:

```text
X_FRAME_OPTIONS = SAMEORIGIN
SECURE_CONTENT_TYPE_NOSNIFF = True
Debug Toolbar only loads in DEBUG development settings
Production secrets fail fast when missing
Frontend cannot submit user_id for ownership-sensitive score/progress APIs
Account deletion requires current password validation
```

## Account Deletion Compliance

Public page for Google Play:

```text
https://attention.truefoxaiinc.com/account-deletion/
```

Local route:

```text
GET /account-deletion/
GET /delete-account/
```

API:

```text
POST /api/users/v1/users/delete-account
```

Request:

```json
{
  "action": "delete",
  "password": "CurrentPassword123!"
}
```

The API uses the authenticated JWT user. Clients must not send `user_id`.

## Self-Assessment Scoring

Response scale:

```text
0 = Never
1 = Rarely
2 = Sometimes
3 = Often
4 = Very Often
```

Normal questions:

```text
scored_value = response
```

Reverse-scored category `N`:

```text
scored_value = 4 - response
```

Final score:

```text
Raw Total = sum(scored values)
TenScore = round((Raw Total / max_possible_score) * 10)
```

Result label:

```text
0-4  -> Severe difficulty
5-6  -> Moderate difficulty
7-8  -> Mild difficulty
9-10 -> Satisfactory to strong
```

Scores are calculated only when all active questions for the user's current `age_group` are answered.

## Frontend Attention Score Submission

Endpoint:

```text
POST /api/assessment/v1/ai-assessment/save-score
```

The backend only stores frontend-generated telemetry. It does not perform webcam frame processing, OpenCV detection, MediaPipe detection, gaze detection, yawning detection, or score calculation.

Important rules:

```text
file_id is required
user is always request.user
numeric fields are range validated
management files must match user's age group
locked lessons are rejected
management file score save can update learning progress
```

## Management Activity Score Submission

Endpoint:

```text
POST /api/assessment/v1/management/activity-score
```

Supported activity codes:

```text
memory_flip
target_pop
focus_hunt
sequence_recall
colour_conflict
task_switch
```

The score is submitted by the frontend and stored in `ManagementActivitySession`.

## Public Pages

```text
/attention-minder-support/  App Store support contact page
/account-deletion/  Google Play account deletion instructions
/delete-account/    Alias for account deletion page
```

## API Documentation

Swagger UI:

```text
/api/docs/
```

Example:

```text
https://attention.truefoxaiinc.com/api/docs/
```

## Running With Docker

Start all services:

```bash
docker-compose up --build
```

API docs:

```text
http://127.0.0.1:8000/api/docs/
```

## Running Natively

Create virtual environment:

```bash
python -m venv venv
```

Activate on Windows:

```powershell
.\venv\Scripts\activate
```

Activate on Linux/macOS:

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

Run development server:

```bash
python manage.py runserver
```

Run ASGI/Daphne:

```bash
daphne -b 0.0.0.0 -p 8000 project_adhd.asgi:application
```

## Deployment Checklist

```text
1. Pull latest code
2. Activate venv
3. Install/update dependencies
4. Run migrations
5. Collect static files
6. Clear Redis cache if cache keys/response fields changed
7. Restart Daphne/systemd service
8. Check /api/docs/
9. Check /attention-minder-support/
10. Check /account-deletion/
11. Check Redis and database connectivity
```

Commands:

```bash
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart adhd
```

Manual Daphne:

```bash
daphne -b 0.0.0.0 -p 8000 project_adhd.asgi:application
```

## Useful Commands

Run checks:

```bash
python manage.py check
```

Show migrations:

```bash
python manage.py showmigrations
```

Run tests:

```bash
python -m pytest
```

Create superuser:

```bash
python manage.py createsuperuser
```

Collect static files:

```bash
python manage.py collectstatic --noinput
```

## Troubleshooting

### DisallowedHost

Add the domain without protocol:

```env
ALLOWED_HOSTS=attention.truefoxaiinc.com
```

For browser requests also add HTTPS origin:

```env
CSRF_TRUSTED_ORIGINS=https://attention.truefoxaiinc.com
CORS_ALLOWED_ORIGINS=https://attention.truefoxaiinc.com
```

### Column does not exist after code deploy

Run migrations:

```bash
python manage.py migrate
```

Then restart the server.

### Redis connection fails

Check Redis:

```bash
redis-cli ping
```

Check `REDIS_CACHE_URL`.

### Cached response looks stale

Most cache invalidation is signal-based. For deployment-level changes, clear Redis once:

```python
from django.core.cache import cache
cache.clear()
```

### Unauthorized response

Check:

```text
Authorization header exists
Bearer token is valid
User is_active=true
User is_deleted=false
JWT signing key matches server
```

### Password reset email not received

Check:

```text
EMAIL_HOST
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD app password
DEFAULT_FROM_EMAIL
Spam folder
SMTP provider limits
```

## Development Rules

```text
Do not accept user_id from frontend for protected ownership operations.
Use request.user from JWT.
Do not reintroduce backend webcam frame processing.
Do not reintroduce OpenCV/MediaPipe/dlib detection into backend request paths.
Keep cached and uncached response structures identical.
Run migrations whenever model fields change.
Keep secrets out of Git.
```
# Learning content API

Management and assessment learning material is exposed through the authenticated
content API. Existing `/api/filehandler/v1/filehandler/list-files` clients remain
supported; new clients should use the endpoints below.

```text
GET  /api/content/v1/contents?section=management&page=1&page_size=20
GET  /api/content/v1/contents/{content_id}
POST /api/content/v1/contents/{content_id}/submit
GET  /api/content/v1/attempts/{attempt_id}/questions
POST /api/content/v1/attempts/{attempt_id}/submit
GET  /api/content/v1/contents/{content_id}/attempt-history
```

The list endpoint returns published content for the authenticated user's age
group, together with lock, subscription, question, and completion metadata. Full
article blocks are returned only by the detail endpoint. The detail response also
includes questions and answer keys for practice-mode presentation; the legacy
attempt-question endpoint does not expose answer keys.

Submit answers using option IDs:

```json
{
  "face_attention_session_id": 13800,
  "answers": [
    {
      "question_id": 10,
      "selected_option_ids": [31]
    }
  ]
}
```

The content submit endpoint links the result to the authenticated user's matching
FaceAttentionSession, creates the attempt, validates multiple answers, calculates
the score, and updates completion in one request. Submitting a completed
attempt again through the attempt-ID endpoint is idempotent and does not create
duplicate answers or progress.
Day 1 is free; management content from Day 2 onward follows the existing active
subscription and day-unlock rules.

In Django Admin, choosing `article` as the content type displays the CKEditor 5
news-style editor and hides video/activity-only inputs. The editor supports
headings, controlled font sizes and colors, lists, links, tables, quotes, and
staff-only image uploads. Saved HTML is sanitized by the backend before storage.
The detail API returns new rich-text articles as:

```json
{
  "article": {
    "format": "html",
    "html": "<h1>Article headline</h1><p>Article content...</p>"
  }
}
```

Legacy structured JSON articles remain readable during migration.

After deployment, apply the additive migrations:

```bash
python manage.py migrate
sudo systemctl restart adhd
```
