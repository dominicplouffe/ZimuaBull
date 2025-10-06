#!/usr/bin/env bash
set -e

# wait for Postgres (external) if you like - but only if not using SQLite
if [ -n "$BULL_HOSTNAME" ] && [ -n "$BULL_PORT" ] && [ "$ENV" != "local" ]; then
  echo "Waiting for Postgres at ${BULL_HOSTNAME}:${BULL_PORT}..."
  timeout=30
  counter=0
  until nc -z $BULL_HOSTNAME $BULL_PORT; do
    sleep 0.1
    counter=$((counter + 1))
    if [ $counter -ge $((timeout * 10)) ]; then
      echo "Timeout waiting for Postgres. Check connection settings."
      echo "BULL_HOSTNAME=$BULL_HOSTNAME"
      echo "BULL_PORT=$BULL_PORT"
      exit 1
    fi
  done
  echo "Postgres is ready!"
fi

# wait for Redis
if [ -n "$REDIS_HOST" ] && [ -n "$REDIS_PORT" ]; then
  echo "Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
  until nc -z $REDIS_HOST $REDIS_PORT; do
    sleep 0.1
  done
fi

# migrations + static
echo "Apply migrations and collect static files"
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# dispatch to the right command
case "$1" in
  web)
    exec gunicorn core.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers 3 \
      --log-level info
    ;;
  celery)
    exec celery -A core worker --loglevel=info
    ;;
  beat)
    exec celery -A core beat --loglevel=info --scheduler=django_celery_beat.schedulers:DatabaseScheduler
    ;;
  *)
    # pass through any other command, e.g. "bash"
    exec "$@"
    ;;
esac