# 🌦️ Sistema de Gestión de Logs Meteorológicos

Un prototipo completo de sistema distribuido para recolectar, procesar y almacenar datos de estaciones meteorológicas usando Python, RabbitMQ y PostgreSQL.

## 📋 Características principales

- **Producer**: Genera datos meteorológicos simulados y los publica en RabbitMQ
- **Consumer**: Procesa mensajes, valida datos y los guarda en PostgreSQL
- **Durabilidad**: Todos los mensajes persisten en disco
- **Ack manual**: `prefetch_count=1` para procesamiento ordenado y garantizado
- **Validación**: Rango de temperaturas, humedad, velocidad del viento
- **Escalabilidad**: Múltiples consumidores pueden procesare mensajes en paralelo
- **Monitoreo**: Logs detallados y dashboard de RabbitMQ
- **Docker**: Todo en contenedores con volúmenes persistentes

## 📦 Requisitos

- **Docker Desktop** (incluye Docker y Docker Compose)
- **Git** (para clonar el repo)
- **Git Bash** o terminal (Mac/Linux)

No necesitas Python instalado localmente (usa los contenedores).

## 🚀 Instalación rápida

### 1. Descargar el proyecto

```bash
# Abre Git Bash o terminal y ejecuta:
git clone https://github.com/tuusuario/weather-logs.git
cd weather-logs
```

O descarga el ZIP y extrae.

### 2. Levantar los servicios

```bash
# Asegúrate de estar en la carpeta weather-logs
# Luego ejecuta:
docker compose up --build

# Esto tarda 2-3 minutos la primera vez
```

Deberías ver logs como:
```
postgres_1      | database system is ready to accept connections
rabbitmq_1      | node started with kernel pid
producer_1      | ✓ Conectado a RabbitMQ
consumer_1      | ✓ Conectado a PostgreSQL
consumer_1      | ✓ Escuchando mensajes...
```

### 3. Verificar que funciona

Abre otra terminal y ejecuta:

```bash
# Ver logs en tiempo real
docker compose logs -f consumer

# Ver logs solo del producer
docker compose logs -f producer

# Ver logs solo de RabbitMQ
docker compose logs -f rabbitmq
```

## 🔍 Interfaces web

### RabbitMQ Management Dashboard

- **URL**: http://localhost:15672
- **Usuario**: rabbit
- **Contraseña**: rabbitpass

Aquí ves:
- Exchange `weather_exchange` (durable)
- Cola `weather_queue` (durable)
- Mensajes en cola, consumidores activos, tasas de throughput

## 📊 Estructura de datos

### Tabla `weather_logs`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | SERIAL | ID único del registro |
| `station_id` | TEXT | Identificador de la estación (station_1, station_2, etc) |
| `timestamp` | TIMESTAMPTZ | Fecha/hora del registro |
| `temperature_c` | NUMERIC | Temperatura en Celsius |
| `humidity_percent` | NUMERIC | Humedad relativa (0-100%) |
| `wind_speed_ms` | NUMERIC | Velocidad del viento (m/s) |
| `raw_payload` | JSONB | JSON original del mensaje |
| `status` | TEXT | Estado ('ok', 'invalid', 'out_of_range') |
| `processed_at` | TIMESTAMPTZ | Cuándo se guardó |

## 🛠️ Comandos útiles

### Docker Compose

```bash
# Levantar servicios
docker compose up --build

# Levantar en background
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f

# Detener servicios
docker compose down

# Detener y eliminar volúmenes (pierde datos)
docker compose down -v

# Reiniciar un servicio específico
docker compose restart consumer

# Ver estado de contenedores
docker compose ps

# Ejecutar comando dentro de un contenedor
docker compose exec consumer python -c "print('Hola')"
```

### Dentro de PostgreSQL

```sql
-- Contar registros
SELECT COUNT(*) FROM weather_logs;

-- Ver últimos 10 registros
SELECT station_id, timestamp, temperature_c, humidity_percent FROM weather_logs 
ORDER BY timestamp DESC LIMIT 10;

-- Registros inválidos
SELECT * FROM weather_logs WHERE status != 'ok';

-- Estadísticas por estación
SELECT station_id, COUNT(*) as count, AVG(temperature_c) as avg_temp
FROM weather_logs 
WHERE status = 'ok'
GROUP BY station_id;

-- Deletear todos los registros (cuidado!)
TRUNCATE weather_logs;
```

### RabbitMQ CLI

```bash
# Ver estado de RabbitMQ
docker compose exec rabbitmq rabbitmq-diagnostics status

# Ver colas
docker compose exec rabbitmq rabbitmq-diagnostics list_queues name consumers messages

# Purgar una cola (elimina mensajes)
docker compose exec rabbitmq rabbitmqctl purge_queue weather_queue
```

## 📈 Validaciones implementadas

El consumer valida:

- **Temperatura**: debe estar entre -100°C y 100°C
- **Humedad**: debe estar entre 0% y 100%
- **Viento**: no puede ser negativo (si viene en el mensaje)
- **Campos obligatorios**: station_id, temperature_c, humidity_percent

Si un mensaje falla validación, se guarda en BD con `status='invalid'` o `status='out_of_range'` para auditoría.

## 🔧 Modificar la configuración

### Cambiar frecuencia de mensajes

Edita `producer/producer.py`, línea ~110:
```python
time.sleep(2)  # Cambiar 2 a otro valor (segundos)
```

### Cambiar cantidad de estaciones

Edita `producer/producer.py`, línea ~85:
```python
station_id = f"station_{random.randint(1, 5)}"  # Cambiar 5 a otro número
```

### Cambiar rangos de temperatura

Edita `producer/producer.py`, línea ~87:
```python
temperature_c = round(random.uniform(-10, 40), 2)  # Cambiar -10 y 40
```

Edita `consumer/consumer.py`, línea ~145:
```python
if temp < -100 or temp > 100:  # Cambiar límites
```

### Cambiar prefetch (procesamiento concurrente)

Edita `consumer/consumer.py`, línea ~120:
```python
ch.basic_qos(prefetch_count=1)  # 1 = secuencial, 5 = hasta 5 simultáneos
```

⚠️ Cambiar a más de 1 puede procesar mensajes en desorden.

## 🎯 Escalabilidad

### Agregar más consumidores

En `docker-compose.yml`, copia el bloque `consumer:` y créalo como `consumer3:`, `consumer4:`, etc.

Luego:
```bash
docker compose up --build
```

Cada consumidor procesará mensajes en paralelo. Con `prefetch_count=1`, se distribuyen equitativamente.

## 🔐 Seguridad

⚠️ **Esto es un prototipo**. Para producción:

- Cambiar todas las contraseñas (`weatherpass`, `rabbitpass`)
- Usar TLS/SSL para PostgreSQL y RabbitMQ
- No exponer puertos 5432, 5672, 15672 al público
- Usar Docker Secrets o Kubernetes Secrets para credenciales
- Implementar autenticación en cualquier API REST

## 🐛 Troubleshooting

### "Error: Connection refused"

```bash
# Reinicia Docker Desktop y espera 30 segundos
# Luego:
docker compose up --build
```

### "PostgreSQL: role does not exist"

```bash
# Reinicia con volúmenes limpios
docker compose down -v
docker compose up --build
```

### "RabbitMQ: connection_closed_abnormally"

Producer/consumer no pueden conectar. Verifica que RabbitMQ esté healthy:
```bash
docker compose ps
# rabbitmq debe mostrar "healthy"
```

### Ver más detalles de error

```bash
docker compose logs --tail=50 consumer  # Últimas 50 líneas
docker compose logs consumer 2>&1 | grep -i error
```

## 📹 Demostración (script de vídeo)

1. **Mostrar estructura**
   ```bash
   ls -la
   cat docker-compose.yml
   ```

2. **Levantar stack**
   ```bash
   docker compose up --build
   # Esperar 1-2 minutos
   ```

3. **Verificar RabbitMQ**
   - Abrir http://localhost:15672 en navegador
   - Mostrar exchange y cola

4. **Verificar logs**
   ```bash
   docker compose logs -f consumer
   ```

5. **Consultar BD**
   ```bash
   psql -h localhost -U weather -d weatherdb
   SELECT * FROM weather_logs LIMIT 5;
   \q
   ```

6. **Detener y verificar persistencia**
   ```bash
   docker compose down
   docker compose up -d
   # Esperar 30 segundos
   psql -h localhost -U weather -d weatherdb
   SELECT COUNT(*) FROM weather_logs;  # Debe mostrar todos los registros anteriores
   ```

## 📚 Estructura del proyecto

```
weather-logs/
├── producer/
│   ├── Dockerfile
│   ├── producer.py
│   └── requirements.txt
├── consumer/
│   ├── Dockerfile
│   ├── consumer.py
│   └── requirements.txt
├── db/
│   └── init.sql
├── docker-compose.yml
├── README.md
└── docs/
    └── architecture.md
```

## 🎓 Conceptos aprendidos

- **Message Broker**: RabbitMQ, exchanges, colas, routing
- **Durabilidad**: Mensajes persistentes, volúmenes Docker
- **Ack manual**: Garantizar procesamiento exitoso
- **Validación**: Input validation y manejo de errores
- **Escalabilidad**: Múltiples consumidores
- **Containers**: Docker, Docker Compose
- **Bases de datos**: PostgreSQL, schemas, índices

## 📖 Referencias útiles

- [RabbitMQ Python Pika](https://pika.readthedocs.io/)
- [psycopg2 PostgreSQL](https://www.psycopg.org/)
- [Docker Compose](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## 📝 Licencia

Este proyecto es de código abierto. Úsalo y modifícalo libremente.

---

¡Éxito! 🚀
