FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_DEBUG=False

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "sitme_core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--forwarded-allow-ips", "*", "--access-logfile", "-", "--error-logfile", "-"]
