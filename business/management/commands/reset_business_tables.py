from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "One-time cleanup: drops stale business_* tables and clears their migration history."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            tables = [
                'business_businessfavorite',
                'business_businessanalyticsevent',
                'business_businesspayment',
                'business_businesssubscription',
                'business_businessverificationdocument',
                'business_businessreview',
                'business_businessinquiry',
                'business_businessgalleryimage',
                'business_businessproduct',
                'business_businessstaffmember',
                'business_businessstaff',
                'business_subscriptionplan',
                'business_business',
            ]
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                self.stdout.write(f"Dropped {table}")
            cursor.execute("DELETE FROM django_migrations WHERE app='business';")
            self.stdout.write("Cleared business migration history")
        self.stdout.write(self.style.SUCCESS("Done."))
        