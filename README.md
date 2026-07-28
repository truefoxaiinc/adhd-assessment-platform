# ADHD-Minder Backend

ADHD-Minder is a Django REST Framework backend for the Attention Minder mobile app. It handles authentication, user profile management, self-assessment questionnaires, learning progress, ADHD content delivery, frontend-submitted attention scores, management activity scores, articles, payments, cache-backed dashboards, and Google Play account deletion compliance.

The backend is intentionally API-first. Face and attention detection are performed in the frontend; the backend stores the final telemetry submitted by the app.

## Current Production URLs

```text
API docs:              https://attention.truefoxaiinc.com/api/docs/
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
Stripe
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
        +-- /api/payments/          -> apps.payments
        +-- /api/docs/              -> Swagger
        +-- /account-deletion/      -> public Google Play deletion page
        |
        v
Services / serializers / permissions
        |
        +-- PostgreSQL for persistent data
        +-- Redis for API response cache and Channels layer
        +-- S3 for media/file storage when configured
        +-- SMTP for password reset OTP email
        +-- Stripe for subscription/payment features
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
    payments/          Stripe customer, checkout, billing portal, subscription, webhook
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

STRIPE_SECRET_KEY=your_stripe_secret
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
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
Google/Facebook social login
Account deactivation and soft deletion
Goal flags such as is_first and is_last
```

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

### Payments

Base paths:

```text
/api/payments/
/api/payments/v1/payments/
```

Endpoints:

```text
POST create-checkout-session/
GET  subscription/
POST create-billing-portal-session/
POST webhook/
```

Responsibilities:

```text
Stripe customer tracking
Checkout sessions
Billing portal sessions
Subscription state
Payment invoices
Stripe webhook event idempotency
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
  Social login provider link for a user

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

StripeCustomer
Subscription
PaymentInvoice
StripeWebhookEvent
  Payment and subscription records
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
/account-deletion/  Google Play account deletion instructions
/delete-account/    Alias for account deletion page
/payment/success/   Stripe payment success landing page
/payment/cancel/    Stripe payment cancel landing page
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
9. Check /account-deletion/
10. Check Redis and database connectivity
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
