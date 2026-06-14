web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn vaultERP.wsgi --log-file - --bind 0.0.0.0:$PORT
