from django.http import JsonResponse
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

def get_response(message="", result=None, status=False, status_code=200):
    return {
        "status": status,
        "status_code": status_code,
        "message": message,
        "data": result or {},
    }


def get_safe_error_response(message, code):
    return {
        "success": False,
        "message": message,
        "code": code,
    }


def get_error_message(error_dict):
    if isinstance(error_dict, list):
        if not error_dict:
            return "Request failed"
        response = error_dict[0]
        if isinstance(response, (dict, list)):
            return get_error_message(response)
        return response

    if not isinstance(error_dict, dict) or not error_dict:
        return "Request failed"

    response = error_dict[next(iter(error_dict))]
    if isinstance(response, dict):
        response = get_error_message(response)
    elif isinstance(response, list):
        response_message = response[0]
        if isinstance(response_message, dict):
            response = get_error_message(response_message)
        else:
            response = response[0]
    return response


def get_exception_code(exc, status_code):
    if isinstance(exc, ValidationError):
        return "VALIDATION_ERROR"
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return "AUTHENTICATION_ERROR"
    if isinstance(exc, PermissionDenied):
        return "PERMISSION_DENIED"
    if isinstance(exc, NotFound):
        return "NOT_FOUND"
    if isinstance(exc, MethodNotAllowed):
        return "METHOD_NOT_ALLOWED"
    if isinstance(exc, ParseError):
        return "PARSE_ERROR"
    if isinstance(exc, Throttled):
        return "RATE_LIMITED"
    if status_code >= 500:
        return "INTERNAL_ERROR"
    return "API_ERROR"


def get_safe_error_message(exc, error_data, status_code):
    if status_code >= 500:
        return "Internal server error"

    if isinstance(exc, ValidationError):
        return "Validation error"

    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return "Authentication credentials were not provided or are invalid"

    if isinstance(exc, PermissionDenied):
        return "You do not have permission to perform this action"

    if isinstance(error_data, dict) and "detail" in error_data:
        return str(error_data["detail"])

    if isinstance(error_data, (dict, list)) and error_data:
        return str(get_error_message(error_data))

    return "Request failed"


def safe_exception_response(exc, *, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, context=None):
    return Response(
        get_safe_error_response("Internal server error", "INTERNAL_ERROR"),
        status=status_code,
    )


def handle_exception(exc, context):
    error_response = exception_handler(exc, context)
    if error_response is None:
        return safe_exception_response(exc, context=context)

    status_code = error_response.status_code
    error_response.data = get_safe_error_response(
        get_safe_error_message(exc, error_response.data, status_code),
        get_exception_code(exc, status_code),
    )
    return error_response





class ExceptionMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)
        if response.status_code == 500:
            response = get_response(
                message="Internal server error, please try again later",
                status_code=response.status_code
            )
            return JsonResponse(response, status=response['status_code'])

        if response.status_code == 404 and "Page not found" in str(response.content):
            response = get_response(
                message="Page not found, invalid url",
                status_code=response.status_code
            )
            return JsonResponse(response, status=response['status_code'])

        return response
