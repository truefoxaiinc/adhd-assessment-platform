# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import OAuthAccount, Users, PasswordResetOTP


@admin.register(Users)
class UsersAdmin(ModelAdmin, DjangoUserAdmin):
    list_display = (
        'id',
        'email',
        'username',
        'account_status',
        'staff_status',
        'is_first',
        'is_last',
        'dob',
        'gender',
        'country',
        'last_login',
    )
    list_display_links = ('id', 'email', 'username')
    list_filter = (
        'last_login',
        'dob',
        'is_verified',
        'is_admin',
        'is_staff',
        'is_superuser',
        'is_deleted',
        'is_first',
        'is_last',
    )
    search_fields = ('email', 'username')
    ordering = ('-id',)
    raw_id_fields = ('groups', 'user_permissions')
    readonly_fields = ('last_login',)
    list_per_page = 25

    @admin.display(description='Account')
    def account_status(self, obj):
        if obj.is_deleted:
            return format_html('<span class="text-red-700 font-semibold">Deleted</span>')
        if obj.is_verified:
            return format_html('<span class="text-green-700 font-semibold">Verified</span>')
        return format_html('<span class="text-amber-700 font-semibold">Pending</span>')

    @admin.display(description='Role')
    def staff_status(self, obj):
        if obj.is_superuser:
            return format_html('<span class="text-purple-700 font-semibold">Superuser</span>')
        if obj.is_admin:
            return format_html('<span class="text-blue-700 font-semibold">Admin</span>')
        if obj.is_staff:
            return format_html('<span class="text-slate-700 font-semibold">Staff</span>')
        return format_html('<span class="text-slate-500">User</span>')

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Profile', {'fields': ('dob', 'gender', 'country', 'height', 'weight', 'profile_image')}),
        ('Permissions', {
            'fields': (
                'is_verified',
                'is_admin',
                'is_staff',
                'is_superuser',
                'is_deleted',
                'is_first',
                'is_last',
                'groups',
                'user_permissions',
            )
        }),
        ('Important dates', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(ModelAdmin):
    list_display = ('id', 'user', 'is_verified', 'is_used', 'created_at', 'expires_at', 'verified_at', 'used_at')
    list_filter = ('is_verified', 'is_used', 'created_at', 'expires_at')
    search_fields = ('user__email', 'user__username')
    date_hierarchy = 'created_at'
    list_per_page = 25


@admin.register(OAuthAccount)
class OAuthAccountAdmin(ModelAdmin):
    list_display = ('id', 'user', 'provider', 'provider_subject', 'email', 'email_verified', 'created_at', 'updated_at')
    list_filter = ('provider', 'email_verified', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__username', 'provider_subject', 'email')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
