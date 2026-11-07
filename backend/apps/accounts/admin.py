from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm

from .models import Institution, PlatformRole, User


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("name",)


class StaffOrStudentCreationForm(UserCreationForm):
    """Students have no password; staff must be given one."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "institution", "full_name", "phone", "platform_role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].required = False
        self.fields["password2"].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("platform_role") != PlatformRole.STUDENT and not cleaned.get("password1"):
            raise forms.ValidationError("Staff users need a password.")
        return cleaned


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "full_name", "platform_role", "is_active")
    list_filter = ("platform_role", "is_active")
    search_fields = ("username", "full_name", "phone")
    ordering = ("username",)
    add_form = StaffOrStudentCreationForm

    def save_model(self, request, obj, form, change):
        if obj.platform_role == PlatformRole.STUDENT:
            obj.set_unusable_password()
            obj.must_change_password = False
        super().save_model(request, obj, form, change)

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
