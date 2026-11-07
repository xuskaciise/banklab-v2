from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Institution, User


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "full_name", "platform_role", "is_active")
    list_filter = ("platform_role", "is_active")
    search_fields = ("username", "full_name", "phone")
    ordering = ("username",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Profile", {"fields": ("institution", "full_name", "phone", "platform_role")}),
        (
            "Status",
            {
                "fields": (
                    "must_change_password",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "institution",
                    "full_name",
                    "phone",
                    "platform_role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
