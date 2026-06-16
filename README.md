# ADHD-Minder Backend API

This is a Django REST Framework (DRF) based backend application for ADHD assessment and progress tracking. It provides a robust API for user authentication, self-assessment questionnaires, scoring, real-time attention tracking, and file handling.

## 🚀 Features

- **Custom Authentication**: JWT-based authentication using `SimpleJWT` with OTP password reset flow.
- **Assessments & Scoring**: Modular models to handle ADHD self-assessment questions, responses, and automatic scoring across different cognitive categories (Reading Focus, Visual Tracking, Auditory/Listening).
- **Progress Tracking & WebSockets**: Integration with Django Channels and Redis to support real-time features, paired with Machine Learning libraries (MediaPipe/OpenCV) for face/attention tracking sessions.
- **API Documentation**: Auto-generated interactive Swagger UI documentation powered by `drf-yasg`.
- **Cloud Storage**: Configured to handle media uploads securely using AWS S3 buckets.
- **Dockerized Environment**: Ready-to-use `docker-compose.yml` to orchestrate the Django backend alongside MySQL and Redis databases.

## 🛠️ Technology Stack

- **Framework**: Django 5.x & Django REST Framework (DRF)
- **Database**: MySQL (Default via Docker) / SQLite (Fallback)
- **WebSockets**: Django Channels with Redis backing
- **Machine Learning**: MediaPipe, OpenCV, dlib (for real-time face tracking)
- **Authentication**: JWT (JSON Web Tokens)
- **Cloud**: AWS S3 (Media), Firebase (Admin)
- **Containerization**: Docker & Docker Compose

## 📁 Project Structure

The project follows a modular Django app structure located in the `/apps/` directory:
- `users`: Custom User model and profile management.
- `authentication`: Login, registration, and OTP logic.
- `assessment`: Models for assessment questions, responses, and result scoring.
- `progresstracker`: Tracking user's progress and attention sessions.
- `websocket`: Real-time bi-directional communication channels.
- `filehandler`: Uploading and managing documents/files.

## ⚙️ Local Development Setup

### Option 1: Using Docker (Recommended)
Make sure Docker Desktop is running.
```bash
docker-compose up --build
```
The API will be available at `http://127.0.0.1:8000/api/docs/`

### Option 2: Native Setup (Without Docker)
1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: You may need Visual Studio C++ build tools installed on Windows to build dependencies like `dlib` and `face-recognition`).*
3. Setup the database and run the server:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py runserver
   ```

## 📝 API Documentation
Once the server is running, visit:
- **Swagger UI**: `http://localhost:8000/api/docs/`

## 📊 Code Quality & Improvements
- **Model Structuring**: The project effectively uses Abstract classes and well-segregated apps.
- **Future Improvements**: Transition naive datetime instances (`datetime.now()`) to timezone-aware instances (`timezone.now()`) and move all hardcoded fallback secrets into secure `.env` files.

## WebSocket Face Detection API

The WebSocket API is used for live face/attention tracking during a video or file session.
It receives camera frames from the client, analyzes concentration, and sends live feedback
back to the app. When the session ends, it can update the user's learning progress.

### Connect

Pass the JWT access token as a query parameter:

```text
ws://localhost:8000/ws/face-detection/?token=ACCESS_TOKEN
```

Production example:

```text
ws://13.217.234.177/ws/face-detection/?token=ACCESS_TOKEN
```

If the token is valid, the first response includes the authenticated `user_id`.

```json
{
  "type": "connection_established",
  "message": "WebSocket ready - Send frame as base64 for full analysis",
  "session_id": "33a3c4f9",
  "user_id": 12,
  "auth_format": "ws://host/ws/face-detection/?token=access_token",
  "expected_format": {
    "type": "validate_face",
    "frame_base64": "base64_encoded_image",
    "face": {
      "x": "int",
      "y": "int",
      "width": "int",
      "height": "int"
    },
    "frame": {
      "width": "int",
      "height": "int"
    },
    "is_assessment": false
  },
  "endcall_format": {
    "type": "endcall",
    "filetype": "video|file",
    "day_completed": "int",
    "order_number": "int"
  }
}
```

If `user_id` is `null`, the token was not provided or could not be authenticated.
Live validation can still respond, but progress updates and score saving require an
authenticated user.

### Send Face Validation Data

Send camera frames as base64 images. The `face` object should contain the face bounding
box detected on the client.

```json
{
  "type": "validate_face",
  "frame_base64": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
  "face": {
    "x": 120,
    "y": 80,
    "width": 180,
    "height": 180
  },
  "frame": {
    "width": 640,
    "height": 480
  },
  "is_assessment": false
}
```

The server processes every fifth frame to reduce CPU usage. Frames in between may receive
the last calculated response.

### Validation Response

```json
{
  "type": "validation_result",
  "result": {
    "face_detected": true,
    "concentration_level": "high",
    "concentration_score": 7,
    "message": "Good concentration",
    "validation_passed": true,
    "metrics": {
      "gaze_ratio": 0.95,
      "drowsy_state": 0.1
    },
    "engagement": {
      "inattention_duration": 0
    },
    "feedback": {
      "show_recommendations": true,
      "alert_level": "high",
      "action_required": false,
      "inattention_duration": 0
    }
  },
  "session_metrics_count": 1,
  "user_id": 12
}
```

### Ping

```json
{
  "type": "ping"
}
```

Response:

```json
{
  "type": "pong",
  "timestamp": "2026-06-16T09:16:02.123456"
}
```

### End Session And Update Progress

Send this when the user completes a video or file:

```json
{
  "type": "endcall",
  "filetype": "video",
  "day_completed": 1,
  "order_number": 1
}
```

For a file completion:

```json
{
  "type": "endcall",
  "filetype": "file",
  "day_completed": 1,
  "order_number": 1
}
```

Response:

```json
{
  "type": "endcall_processed",
  "session_id": "33a3c4f9",
  "user_id": 12,
  "metrics_count": 10,
  "filetype": "video",
  "day_completed": 1,
  "order_number": 1,
  "progress_updated": true,
  "message": "Session ended successfully"
}
```

After this response, the server closes the socket.

### Client Flow

```text
1. Connect with token.
2. Wait for connection_established.
3. Repeatedly send validate_face with base64 frame data.
4. Read validation_result responses for live feedback.
5. Send endcall after the video/file is completed.
6. Read endcall_processed and let the socket close.
```
