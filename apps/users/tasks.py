from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_otp_email_task(email, otp):
    send_mail(
        'Password Reset OTP',
        f'Your OTP for password reset is: {otp}. This OTP is valid for 10 minutes.',
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )
