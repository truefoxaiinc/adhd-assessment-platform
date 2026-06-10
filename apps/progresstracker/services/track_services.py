import trace
from apps.progresstracker.models import UserAssessmentDetails, ProgressTracker
from datetime import datetime

import logging
logger = logging.getLogger(__name__)

class ProgressTrackerActions:

    @staticmethod
    def get_days_for_the_file(user_instance):
        try:
            assessment_instance   = UserAssessmentDetails.objects.filter(user=user_instance).first()
            last_completed_day    = assessment_instance.last_completed if assessment_instance else 0
            if last_completed_day not in [0, None]:
                todays_day            = datetime.now().day
                started_day           = assessment_instance.started_on.day if assessment_instance and assessment_instance.started_on else todays_day
                difference_in_days    = todays_day - started_day
                days_required = [day for day in range(last_completed_day, difference_in_days)]
                return days_required
            return [1]
            
        except Exception as e:
            logger.error(f"Error fetching files from S3: {str(e)}")
            pass

    @staticmethod
    def get_day_completed(user_instance):
        progress_queryset = ProgressTracker.objects.filter(user=user_instance)

    
    @staticmethod
    def update_learning_progress(user_instance, filetype, day_completed, order_number):
        try:
            file_to_check = 'video' if filetype == 'file' else 'file'

            if order_number == 1 and day_completed > 30:
                is_day_completed = ProgressTracker.objects.filter(user=user_instance,filetype=file_to_check,day_number=day_completed).exists()
            elif order_number == 2 and day_completed <= 30 and filetype == 'video':
                is_day_completed = ProgressTracker.objects.filter(user=user_instance,filetype__in=['video','file'],order_number=1,day_number=day_completed).exists()
            elif order_number == 1 and day_completed <= 30 and filetype == 'file':
                is_day_completed = ProgressTracker.objects.filter(user=user_instance,filetype=file_to_check,order_number__in=[1,2],day_number=day_completed).exists()
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
                assessment_instance.last_completed = day_completed
                assessment_instance.is_day_completed = is_day_completed
                assessment_instance.save()
            else:
                UserAssessmentDetails.objects.create(
                    user=user_instance,
                    last_completed=day_completed,
                    is_day_completed=is_day_completed,
                    started_on=datetime.now()
                )
        except Exception as e:
            import traceback
            traceback.print_exc()
            pass
