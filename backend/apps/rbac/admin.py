from django.contrib import admin

from .models import Permission, RolePermission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "category", "description")
    list_filter = ("category",)
    # Defaults change only via migrations until per-session overrides arrive in 1.3.
    has_add_permission = has_change_permission = has_delete_permission = (
        lambda self, request, obj=None: False
    )


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "scope")
    list_filter = ("role", "scope")
    has_add_permission = has_change_permission = has_delete_permission = (
        lambda self, request, obj=None: False
    )
