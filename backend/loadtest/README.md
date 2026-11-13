# Load test (100-200 students)

Run against a throwaway database; financial records cannot be deleted.

    # 1. fresh DB + migrations (example: separate database on the dev Postgres)
    export DATABASE_URL=postgres://<user>:<pw>@<host>:5432/banklab_loadtest
    python manage.py migrate
    # 2. seed 200 students in 4 banks (writes loadtest/students.csv, no passwords)
    LOADTEST_PASSWORD=<choose> python manage.py seed_loadtest --students 200
    # 3. run (headless 5 min, 200 users, 10 new users/s)
    LOADTEST_PASSWORD=<same> locust -f loadtest/locustfile.py --host http://localhost:8000 \
        -u 200 -r 10 -t 5m --headless

`python manage.py seed_loadtest --teardown` archives the LOADTEST session and deactivates its
users (the ledger rows stay). Drop the database afterwards. All students share one IP, so the
login throttle (failures only) is not triggered by correct logins.
