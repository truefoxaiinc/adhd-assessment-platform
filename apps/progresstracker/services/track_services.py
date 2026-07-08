from apps.progresstracker.models import UserAssessmentDetails, ProgressTracker
from datetime import datetime, time as datetime_time, timedelta
from django.utils import timezone

class ProgressTrackerActions:

    @staticmethod
    def _next_midnight_after(completed_at):
        local_completed_at = timezone.localtime(completed_at)
        next_day = local_completed_at.date() + timedelta(days=1)
        return timezone.make_aware(
            datetime.combine(next_day, datetime_time.min),
            timezone.get_current_timezone(),
        )

    @staticmethod
    def get_days_for_the_file(user_instance):
        try:
            if not user_instance:
                return [1]

            assessment_instance   = UserAssessmentDetails.objects.filter(user=user_instance).first()
            last_completed_day    = assessment_instance.last_completed if assessment_instance else 0
            if last_completed_day not in [0, None]:
                unlocked_until = int(last_completed_day)
                if assessment_instance.last_completed_at:
                    next_unlock_time = ProgressTrackerActions._next_midnight_after(
                        assessment_instance.last_completed_at
                    )
                    if timezone.now() >= next_unlock_time:
                        unlocked_until += 1
                return list(range(1, unlocked_until + 1))
            return [1]
            
        except Exception:
            return [1]

    @staticmethod
    def get_day_completed(user_instance):
        progress_queryset = ProgressTracker.objects.filter(user=user_instance)

    
    @staticmethod
    def update_learning_progress(user_instance, filetype, day_completed, order_number):
        try:
            day_completed = int(day_completed)
            order_number = int(order_number)
            file_to_check = 'video' if filetype == 'file' else 'file'

            if order_number == 1 and day_completed > 30:
                is_day_completed = ProgressTracker.objects.filter(user=user_instance,file_type=file_to_check,day_number=day_completed).exists()
            elif order_number == 2 and day_completed <= 30 and filetype == 'video':
                is_day_completed = ProgressTracker.objects.filter(user=user_instance,file_type__in=['video','file'],order_number=1,day_number=day_completed).exists()
            elif order_number == 1 and day_completed <= 30 and filetype == 'file':
                is_day_completed = ProgressTracker.objects.filter(user=user_instance,file_type=file_to_check,order_number__in=[1,2],day_number=day_completed).exists()
            else:
                is_day_completed = False

            tracker_instance = ProgressTracker()
            tracker_instance.user         = user_instance
            tracker_instance.day_number   = day_completed
            tracker_instance.file_type    = filetype
            tracker_instance.order_number = order_number
            tracker_instance.is_day_completed = is_day_completed
            tracker_instance.save()

            assessment_instance   = UserAssessmentDetails.objects.filter(user=user_instance).first()
            if assessment_instance:
                if filetype == 'video':
                    assessment_instance.last_completed = day_completed
                    assessment_instance.last_completed_at = timezone.now()
                assessment_instance.is_day_completed = is_day_completed
                assessment_instance.save()
            else:
                UserAssessmentDetails.objects.create(
                    user=user_instance,
                    last_completed=day_completed if filetype == 'video' else None,
                    last_completed_at=timezone.now() if filetype == 'video' else None,
                    is_day_completed=is_day_completed,
                    started_on=timezone.now()
                )
            return True
        except Exception:
            return False
