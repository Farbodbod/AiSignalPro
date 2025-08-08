# file: backend/core/management/commands/wait_for_db.py

import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

class Command(BaseCommand):
    """Django command to wait for the database to be available"""

    def handle(self, *args, **options):
        self.stdout.write("Waiting for database...")
        db_conn = None
        attempts = 0
        max_attempts = 30 # 30 attempts * 2 seconds = 1 minute timeout
        
        while not db_conn and attempts < max_attempts:
            try:
                db_conn = connections['default']
                # The connection is lazy, so we need to perform a query
                db_conn.cursor() 
            except OperationalError:
                self.stdout.write("Database unavailable, waiting 2 seconds...")
                attempts += 1
                time.sleep(2)

        if db_conn:
            self.stdout.write(self.style.SUCCESS("Database available!"))
        else:
            self.stdout.write(self.style.ERROR("Database not available after multiple attempts. Exiting."))
            exit(1)
