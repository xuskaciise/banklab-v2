from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm

from . import services
from .models import Institution, PlatformRole, User


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("name",)


class StaffOrStudentCreationForm(UserCreationForm):
    """Students get the initial password automatically; staff must be given one."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "institution", "full_name", "phone", "platform_role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].required = False
        self.fields["password2"].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("platform_role") == PlatformRole.STUDENT:
            try:
                services.initial_password(cleaned.get("phone", ""))
            except services.ValidationFailed as exc:
                raise forms.ValidationError(exc.message) from exc
        elif not cleaned.get("password1"):
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
        # New students, and users whose role just became student, start with the initial
        # password (last 4 phone digits) and must change it at first login.
        became_student = obj.platform_role == PlatformRole.STUDENT and (
            not change or (form is not None and "platform_role" in form.changed_data)
        )
        if became_student:
            obj.set_password(services.initial_password(obj.phone))
            obj.must_change_password = True
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
