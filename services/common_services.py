from django.urls import reverse
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import  JsonResponse
from django.db.models import Q
from helpers.helper import get_object_or_none
from django.contrib import messages

""" Common function for generate breadcrumbs"""
class BreadcrumbMixin:
    def __init__(self):
        self.context = {}
    def generate_breadcrumbs(self, breadcrumb_items):
        self.context['breadcrumbs'] = [
            {"name": "Home", "route": reverse('reports:dashboard'), 'active': False},
        ] + breadcrumb_items


""" Common function for all delete and status change from listing screen"""
def common_status_change(self,request,model):
   ids            = request.POST.getlist('ids[]')
   statusvalue    = request.POST.get('statusvalue')
   if statusvalue != "deleteRows":
      status      = 'Active' if request.POST.get('status') =='true' else 'Inactive'
      model.objects.filter(id__in=ids).update(status=status)
   else:
      model.objects.filter(id__in=ids).delete()

""" Common function for delete"""
def delete_handler(self,request,model):
    ids = request.POST.get('ids')
    if ids:
        instance = get_object_or_none(model,id=ids)
        if instance:
            instance.delete()

def existence_checker(self,request,checking_model,checking_field,checking_message,multi_delete):
    statusvalue    = request.POST.get('statusvalue')
    if multi_delete and statusvalue == "deleteRows":
        ids            = request.POST.getlist('ids[]')
        exist_flag = checking_model.objects.filter(**{f"{checking_field}__in": ids})
        if exist_flag.exists():
            response_data = {
                "message": checking_message,  
                "status_code": 409,  
                "data": '' 
            }
            return JsonResponse(response_data, status=200)
    elif not multi_delete and statusvalue != "deleteRows" :
        ids           = request.POST.get('ids')
        data_exist    = checking_model.objects.filter(**{checking_field: ids})
        if data_exist:
            response_data = {
                "message": checking_message,  
                "status_code": 409,  
                "data": '' 
            }
            return JsonResponse(response_data, status=200) 
        

""" Common view for delete and status change function calling section"""
@method_decorator(login_required, name='dispatch')
class BasicView(View):
    handler_function    = None  # To be defined in subclasses
    model               = None
    checking_model      = None
    checking_field      = None
    checking_message    = None
    multi_delete        = False

    def __init__(self, **kwargs):
        self.response_format = {"status_code": 101, "message": "", "error": ""}
        super().__init__(**kwargs)

    def post(self, request, *args, **kwargs):
        try:
            if self.handler_function:
                if self.checking_field and self.checking_model and self.checking_message:
                    existence_response = existence_checker(self, request, self.checking_model, self.checking_field,self.checking_message,self.multi_delete)
                    if existence_response:  
                        return existence_response
                data = self.handler_function(request, self.model)
                if data:
                    return JsonResponse(data, status=200)

                self.response_format['status_code'] = 200
                self.response_format['message'] = 'Success'
                self.response_format['success'] = True
            else:   
                raise NotImplementedError("Handler function not defined.")

        except Exception as e:
            self.response_format['message'] = 'error'
            self.response_format['error'] = str(e)

        return JsonResponse(self.response_format, status=200)

def set_response(status_code, message="", error="", data=""):
    return {
        "status_code": status_code,
        "message": message,
        "error": error,
        "data": data
    }

class DatatableServices:
    @staticmethod
    def filter_by_search(queryset, search_term):
        if search_term:
            return queryset.filter(
                Q(name__icontains=search_term) |
                Q(category__icontains=search_term) |
                Q(domain__icontains=search_term) |
                Q(code__icontains=search_term)
            )
        return queryset

    @staticmethod
    def filter_by_status(queryset, status):
        if status == 'active':
            return queryset.filter(status='Active')
        elif status == 'inactive':
            return queryset.filter(status='Inactive')
        return queryset

    @staticmethod
    def order_queryset(queryset, sort_field):
        if sort_field :
            return queryset.order_by(f'-{sort_field}') 
        else:
            return queryset

def _handle_duplicate_error(request, message: str) -> dict:
    """Handle the error when a duplicate title is found."""
    error_format = {
        'status': 409,  # HTTP status code for conflict
        'message': message
    }
    
    # Add error message to Django messages framework if request is available
    if request:
        messages.error(request,message)
    
    return error_format

def _common_response(request, status,message,result):
    response_format = {
        'status': status,
        'message': message
    }
    if request:
        match result:
            case 'success':
                messages.success(request, response_format['message'])
            case 'error':
                messages.error(request, response_format['message'])
    
    return JsonResponse(response_format, status=200)


        