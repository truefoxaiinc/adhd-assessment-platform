from django.db.models import Avg
from django.urls import reverse


def dashboard_callback(request, context):
    from apps.articles.models import Article
    from apps.assessment.models import ADHDDocument, SelfAssessmentQuestions, SelfAssessmentResult
    from apps.filehandler.models import AdhdContent, FeedbackReview
    from apps.progresstracker.models import FaceAttentionSession, ProgressTracker
    from apps.users.models import Users

    metrics = [
        {
            "label": "Total users",
            "value": Users.objects.filter(is_deleted=False).count(),
            "caption": "Active account records",
            "icon": "group",
            "url": reverse("admin:users_users_changelist"),
        },
        {
            "label": "Assessment results",
            "value": SelfAssessmentResult.objects.count(),
            "caption": "Completed screenings",
            "icon": "assignment_turned_in",
            "url": reverse("admin:assessment_selfassessmentresult_changelist"),
        },
        {
            "label": "Attention sessions",
            "value": FaceAttentionSession.objects.count(),
            "caption": "Tracked focus sessions",
            "icon": "visibility",
            "url": reverse("admin:progresstracker_faceattentionsession_changelist"),
        },
        {
            "label": "Content assets",
            "value": AdhdContent.objects.count(),
            "caption": "Videos, documents, and files",
            "icon": "folder_open",
            "url": reverse("admin:filehandler_adhdcontent_changelist"),
        },
    ]

    avg_concentration = FaceAttentionSession.objects.aggregate(
        value=Avg("concentration_score")
    )["value"]

    operations = [
        {
            "label": "Verified users",
            "value": Users.objects.filter(is_verified=True, is_deleted=False).count(),
        },
        {
            "label": "Active questions",
            "value": SelfAssessmentQuestions.objects.filter(is_active=True).count(),
        },
        {
            "label": "Published articles",
            "value": Article.objects.filter(status="published").count(),
        },
        {
            "label": "Completed progress items",
            "value": ProgressTracker.objects.filter(is_day_completed=True).count(),
        },
        {
            "label": "Documents",
            "value": ADHDDocument.objects.count(),
        },
        {
            "label": "Feedback entries",
            "value": FeedbackReview.objects.count(),
        },
    ]

    quick_actions = [
        {
            "label": "Add assessment question",
            "icon": "add_circle",
            "url": reverse("admin:assessment_selfassessmentquestions_add"),
        },
        {
            "label": "Upload ADHD content",
            "icon": "upload_file",
            "url": reverse("admin:filehandler_adhdcontent_add"),
        },
        {
            "label": "Create article",
            "icon": "edit_note",
            "url": reverse("admin:articles_article_add"),
        },
        {
            "label": "Review feedback",
            "icon": "reviews",
            "url": reverse("admin:filehandler_feedbackreview_changelist"),
        },
    ]

    unverified_users = Users.objects.filter(is_verified=False, is_deleted=False).count()
    draft_articles = Article.objects.filter(status="draft").count()
    inactive_questions = SelfAssessmentQuestions.objects.filter(is_active=False).count()
    incomplete_progress = ProgressTracker.objects.filter(is_day_completed=False).count()
    low_focus_sessions = FaceAttentionSession.objects.filter(concentration_score__lt=50).count()

    needs_attention = [
        {
            "label": "Unverified users",
            "value": unverified_users,
            "caption": "Accounts waiting for verification",
            "icon": "person_alert",
            "url": f"{reverse('admin:users_users_changelist')}?is_verified__exact=0",
            "level": "warning" if unverified_users else "success",
        },
        {
            "label": "Draft articles",
            "value": draft_articles,
            "caption": "Content not yet published",
            "icon": "edit_document",
            "url": f"{reverse('admin:articles_article_changelist')}?status__exact=draft",
            "level": "warning" if draft_articles else "success",
        },
        {
            "label": "Inactive questions",
            "value": inactive_questions,
            "caption": "Assessment questions disabled",
            "icon": "quiz",
            "url": f"{reverse('admin:assessment_selfassessmentquestions_changelist')}?is_active__exact=0",
            "level": "neutral" if inactive_questions else "success",
        },
        {
            "label": "Incomplete progress",
            "value": incomplete_progress,
            "caption": "Progress rows still open",
            "icon": "pending_actions",
            "url": f"{reverse('admin:progresstracker_progresstracker_changelist')}?is_day_completed__exact=0",
            "level": "warning" if incomplete_progress else "success",
        },
        {
            "label": "Low focus sessions",
            "value": low_focus_sessions,
            "caption": "Concentration score below 50",
            "icon": "priority_high",
            "url": reverse("admin:progresstracker_faceattentionsession_changelist"),
            "level": "danger" if low_focus_sessions else "success",
        },
    ]

    verified_users = Users.objects.filter(is_verified=True, is_deleted=False).count()
    published_articles = Article.objects.filter(status="published").count()
    archived_articles = Article.objects.filter(status="archived").count()
    management_content = AdhdContent.objects.filter(is_management=True).count()
    assessment_content = AdhdContent.objects.filter(is_management=False).count()
    completed_progress = ProgressTracker.objects.filter(is_day_completed=True).count()

    chart_rows = [
        {
            "label": "Verified users",
            "value": verified_users,
            "total": verified_users + unverified_users,
        },
        {
            "label": "Published articles",
            "value": published_articles,
            "total": published_articles + draft_articles + archived_articles,
        },
        {
            "label": "Management content",
            "value": management_content,
            "total": management_content + assessment_content,
        },
        {
            "label": "Completed progress",
            "value": completed_progress,
            "total": completed_progress + incomplete_progress,
        },
    ]

    for row in chart_rows:
        row["percent"] = round((row["value"] / row["total"]) * 100) if row["total"] else 0

    context.update(
        {
            "dashboard_metrics": metrics,
            "dashboard_operations": operations,
            "dashboard_quick_actions": quick_actions,
            "dashboard_needs_attention": needs_attention,
            "dashboard_chart_rows": chart_rows,
            "dashboard_avg_concentration": (
                f"{avg_concentration:.1f}" if avg_concentration is not None else "0.0"
            ),
            "dashboard_recent_sessions": FaceAttentionSession.objects.select_related("user")
            .order_by("-created_at")[:5],
        }
    )

    return context
