web: python manage.py migrate && python manage.py ensure_admin && python manage.py collectstatic --noinput && python -m gunicorn vaultERP.wsgi --log-file - --bind 0.0.0.0:$PORT
