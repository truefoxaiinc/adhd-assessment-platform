from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string

@shared_task
def send_otp_email_task(email, otp):
    subject = 'Your ADHD Minder password reset code'
    text_body = (
        f'Your ADHD Minder password reset code is: {otp}\n\n'
        'This code will expire in 10 minutes.\n\n'
        'If you did not request this password reset, you can safely ignore this email.\n\n'
        'Thanks,\n'
        'ADHD Minder Team'
    )
    html_body = render_to_string(
        'users/emails/password_reset_otp.html',
        {'otp': otp},
    )

    message = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)
