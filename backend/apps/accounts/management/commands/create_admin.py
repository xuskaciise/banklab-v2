import os
from getpass import getpass

from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the first admin user. Password from env ADMIN_PASSWORD or prompt."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--full-name", required=True)
        parser.add_argument("--phone", required=True)

    def handle(self, *args, **opts):
        username = opts["username"]
        if User.objects.filter(username=username).exists():
            raise CommandError("Username already exists")
        password = os.environ.get("ADMIN_PASSWORD") or getpass("Password: ")
        if len(password) < services.MIN_PASSWORD_LENGTH:
            raise CommandError(
                f"Password must be at least {services.MIN_PASSWORD_LENGTH} characters"
            )
        try:
            services.initial_password(opts["phone"])  # validates phone
        except services.AccountsError as e:
            raise CommandError(e.message) from e
        user = User.objects.create_superuser(
            username=username,
            password=password,
            full_name=opts["full_name"],
            phone=opts["phone"],
        )
        self.stdout.write(self.style.SUCCESS(f"Admin '{user.username}' created"))
