# 1. Usar una versión oficial y ligera de Python
FROM python:3.10-slim

# 2. Configurar el entorno para que no genere basura y los logs sean limpios
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Crear una carpeta de trabajo dentro del cerebro del NAS
WORKDIR /app

# 4. Copiar e instalar los requerimientos del hospital
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar todo el código de tu laptop al contenedor
COPY . /app/

# ---> AGREGA ESTA LÍNEA: Empaqueta las imágenes para producción
RUN python manage.py collectstatic --noinput

# 6. Exponer el puerto que usaremos
EXPOSE 8000

# 7. La orden de encendido con el motor industrial Gunicorn
CMD ["gunicorn", "sitme_core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]