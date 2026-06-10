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
