# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Users, PasswordResetOTP


@admin.register(Users)
class UsersAdmin(DjangoUserAdmin):
    list_display = (
        'id',
        'last_login',
        'email',
        'username',
        'dob',
        'gender',
        'country',
        'height',
        'weight',
        'is_verified',
        'is_admin',
        'is_staff',
        'is_superuser',
        'is_deleted',
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
    )
    search_fields = ('email', 'username')
    ordering = ('-id',)
    raw_id_fields = ('groups', 'user_permissions')
    readonly_fields = ('last_login',)

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
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'otp', 'created_at', 'expires_at')
    list_filter = ('user', 'created_at', 'expires_at')
    date_hierarchy = 'created_at'
