from django.db import models
from django.utils.translation import gettext_lazy as _



class StatusChoices(models.TextChoices):
    Active    = 'Active', _('Active')
    Inactive  = 'Inactive', _('Inactive')
    Pending   = 'Pending', _('Pending')

class AbstractDateFieldMix(models.Model):
    created_by    = models.ForeignKey('users.Users', on_delete=models.SET_NULL, related_name='%(class)s_created', null=True, blank=True)
    modified_by   = models.ForeignKey('users.Users', on_delete=models.SET_NULL, related_name='%(class)s_modified', null=True, blank=True)
    created_date  = models.DateTimeField(_('created_date'), auto_now_add=True, editable=False, blank=True, null=True)
    modified_date = models.DateTimeField(_('modified_date'), auto_now=True, editable=False, blank=True, null=True)
    status        = models.CharField(_('Status'),max_length=50,choices=StatusChoices.choices,default=StatusChoices.Active)

    class Meta:
        abstract = True