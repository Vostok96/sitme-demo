version: '3.8'

services:
  sitme_web:
    build: .
    container_name: sitme_produccion
    restart: always
    ports:
      - "8080:8000" # Esto significa: El NAS lo mostrará en el puerto 8080
    volumes:
      # Esta línea es VITAL. Guarda la base de datos en tu NAS de forma permanente
      - ./db.sqlite3:/app/db.sqlite3
      - ./media:/app/media   # Para que no se pierdan los PDFs de resultados