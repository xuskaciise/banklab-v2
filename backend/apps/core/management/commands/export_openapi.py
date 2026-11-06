import json

from django.core.management.base import BaseCommand

from config.api import api


class Command(BaseCommand):
    help = "Print the OpenAPI schema as JSON to stdout (used to generate frontend types)."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(api.get_openapi_schema(), indent=2))
