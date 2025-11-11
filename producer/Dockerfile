FROM python:3.13-slim

WORKDIR /app

# Instala dependencias del sistema (si fueran necesarias)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements y instala paquetes Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código
COPY producer.py .

# Comando que se ejecuta al arrancar el contenedor
CMD ["python", "producer.py"]