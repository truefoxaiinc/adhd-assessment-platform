from django.db.models import Sum, Case, When, IntegerField, Q
from apps.assessment.models import SelfAssessmentResponse,SelfAssessmentResult
from apps.progresstracker.models import UserAssessmentDetails

class ResultService:
    def __init__(self,instance,is_adult=False):
        self.instance         = instance
        self.is_adult         = is_adult
        self.initial_query    = SelfAssessmentResponse.objects.filter(Q(result_entry=self.instance))
        self.confirm_adhd     = False

    def find_program_duration(self, tenscore):
        match tenscore:
            case _ if tenscore >= 0 and tenscore <= 4:
                return 3
            case _ if tenscore >= 5 and tenscore <= 6:
                return 2 
            case _ if tenscore >= 7:
                return 1
            case _:
                return 3
            
    def calculate_selfassessment(self):
        totals = self.initial_query.aggregate(
            raw_total=Sum(
                Case(
                    When(Q(question__is_for_adults=self.is_adult), then='response'),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            read_focus_total=Sum(
                Case(
                    When(Q(question__is_for_adults=self.is_adult) & Q(question__category='RF'), then='response'),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            visual_tracking_total=Sum(
                Case(
                    When(Q(question__is_for_adults=self.is_adult) & Q(question__category='VT'), then='response'),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            audio_listening_total=Sum(
                Case(
                    When(Q(question__is_for_adults=self.is_adult) & Q(question__category='AL'), then='response'),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )
        raw_total = totals['raw_total'] or 0
        tenscore = round((raw_total/84)*10) 

        program_duration =  self.find_program_duration(tenscore)

        instance = SelfAssessmentResult.objects.filter(id=self.instance.id).first()
        instance.raw_total                = raw_total
        instance.tenscore                 = tenscore
        instance.read_focus_total         = totals['read_focus_total'] or 0
        instance.visual_tracking_total    = totals['visual_tracking_total'] or 0
        instance.audio_listening_total    = totals['audio_listening_total'] or 0
        instance.program_duration         = program_duration
        instance.save()

        assessment_instance = UserAssessmentDetails.objects.filter(user=instance.user).first()
        if assessment_instance is None:
            assessment_instance  = UserAssessmentDetails()
        
        assessment_instance.user            = instance.user
        assessment_instance.course_duration = program_duration * 30
        assessment_instance.save()

        return  instance

 