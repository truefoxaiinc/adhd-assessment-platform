from django.db.models import Q
from apps.assessment.models import SelfAssessmentResponse,SelfAssessmentResult

class ResultService:
    def __init__(self,instance,is_adult=False):
        self.instance         = instance
        self.is_adult         = is_adult
        self.initial_query    = SelfAssessmentResponse.objects.filter(Q(result_entry=self.instance))
        self.confirm_adhd     = False

    def find_result_label(self, tenscore):
        match tenscore:
            case _ if tenscore >= 0 and tenscore <= 4:
                return "Severe difficulty"
            case _ if tenscore >= 5 and tenscore <= 6:
                return "Moderate difficulty"
            case _ if tenscore >= 7 and tenscore <= 8:
                return "Mild difficulty"
            case _ if tenscore >= 9:
                return "Satisfactory to strong"
            case _:
                return "Severe difficulty"

    @staticmethod
    def get_scored_response(response):
        response_value = int(response.response or 0)
        if response.question and response.question.category == 'N':
            return 4 - response_value
        return response_value

    def calculate_selfassessment(self):
        responses = list(
            self.initial_query
            .select_related('question')
            .filter(question__is_for_adults=self.is_adult)
        )

        raw_total = 0
        read_focus_total = 0
        visual_tracking_total = 0
        audio_listening_total = 0

        for response in responses:
            scored_response = self.get_scored_response(response)
            raw_total += scored_response

            match response.question.category:
                case 'RF':
                    read_focus_total += scored_response
                case 'VT':
                    visual_tracking_total += scored_response
                case 'AL':
                    audio_listening_total += scored_response

        max_score = len(responses) * 4
        tenscore = round((raw_total / max_score) * 10) if max_score else 0

        instance = SelfAssessmentResult.objects.filter(id=self.instance.id).first()
        instance.result                   = self.find_result_label(tenscore)
        instance.raw_total                = raw_total
        instance.tenscore                 = tenscore
        instance.read_focus_total         = read_focus_total
        instance.visual_tracking_total    = visual_tracking_total
        instance.audio_listening_total    = audio_listening_total
        instance.save()

        return  instance

 
