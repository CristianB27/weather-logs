#!/usr/bin/env python
"""
Consumer de datos meteorológicos.
Consume mensajes de RabbitMQ, los valida y los guarda en PostgreSQL.
"""

import os
import time
import json
import logging
import psycopg2
from psycopg2.extras import Json
from psycopg2 import sql
from datetime import datetime, timezone
import pika
from pika.exceptions import AMQPConnectionError

# ==================== Configuración ====================
RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBIT_USER = os.getenv("RABBITMQ_USER", "rabbit")
RABBIT_PASS = os.getenv("RABBITMQ_PASS", "rabbitpass")

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_DB = os.getenv("POSTGRES_DB", "weatherdb")
PG_USER = os.getenv("POSTGRES_USER", "weather")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "weatherpass")

EXCHANGE = "weather_exchange"
QUEUE = "weather_queue"
ROUTING_KEY = "weather.logs"

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [CONSUMER] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== Conexión a PostgreSQL ====================
def connect_db():
    """
    Conecta a PostgreSQL con reintentos automáticos.
    Retorna: conexión a BD
    """
    while True:
        try:
            conn = psycopg2.connect(
                host=PG_HOST,
                dbname=PG_DB,
                user=PG_USER,
                password=PG_PASS,
                connect_timeout=5
            )
            conn.autocommit = True  # Confirmar cambios inmediatamente
            logger.info("✓ Conectado a PostgreSQL")
            return conn
        except psycopg2.OperationalError as e:
            logger.error(f"✗ Error conectando a PostgreSQL: {e}")
            logger.info("  Reintentando en 3 segundos...")
            time.sleep(3)

# ==================== Conexión a RabbitMQ ====================
def connect_rabbitmq():
    """
    Conecta a RabbitMQ y declara exchange/cola con durabilidad.
    Retorna: tupla (connection, channel)
    """
    while True:
        try:
            credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
            params = pika.ConnectionParameters(
                host=RABBIT_HOST,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
                connection_attempts=3,
                retry_delay=2
            )
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            
            # Declarar exchange durable
            ch.exchange_declare(
                exchange=EXCHANGE,
                exchange_type='direct',
                durable=True
            )
            
            # Declarar cola durable
            ch.queue_declare(
                queue=QUEUE,
                durable=True
            )
            
            # Vincular cola al exchange
            ch.queue_bind(
                queue=QUEUE,
                exchange=EXCHANGE,
                routing_key=ROUTING_KEY
            )
            
            # *** PREFETCH = 1 ***
            # Cada consumidor recibe 1 mensaje a la vez y debe procesarlo completamente
            # antes de recibir el siguiente. Esto garantiza procesamiento ordenado.
            ch.basic_qos(prefetch_count=1)
            
            logger.info("✓ Conectado a RabbitMQ")
            logger.info(f"  Exchange: {EXCHANGE} (durable)")
            logger.info(f"  Queue: {QUEUE} (durable)")
            logger.info(f"  Prefetch: 1 (procesamiento secuencial)")
            
            return conn, ch
        except AMQPConnectionError as e:
            logger.error(f"✗ Error conectando a RabbitMQ: {e}")
            logger.info("  Reintentando en 5 segundos...")
            time.sleep(5)

# ==================== Validación de datos ====================
def validate_payload(payload):
    """
    Valida que los datos meteorológicos sean realistas.
    
    Args:
        payload: dict con datos
        
    Retorna: tupla (es_valido, estado, motivo)
    """
    # Validar campos obligatorios
    if 'station_id' not in payload:
        return False, 'invalid', 'falta station_id'
    
    if 'temperature_c' not in payload:
        return False, 'invalid', 'falta temperature_c'
    
    if 'humidity_percent' not in payload:
        return False, 'invalid', 'falta humidity_percent'
    
    # Validar rangos realistas
    temp = payload.get('temperature_c')
    if not isinstance(temp, (int, float)):
        return False, 'invalid_type', 'temperatura no es numérica'
    
    if temp < -100 or temp > 100:
        return False, 'out_of_range', f'temperatura {temp}°C fuera de rango [-100, 100]'
    
    # Validar humedad
    humidity = payload.get('humidity_percent')
    if not isinstance(humidity, (int, float)):
        return False, 'invalid_type', 'humedad no es numérica'
    
    if humidity < 0 or humidity > 100:
        return False, 'out_of_range', f'humedad {humidity}% debe estar [0, 100]'
    
    # Validar viento (opcional, pero si existe debe ser >= 0)
    wind = payload.get('wind_speed_ms')
    if wind is not None:
        if not isinstance(wind, (int, float)):
            return False, 'invalid_type', 'viento no es numérico'
        if wind < 0:
            return False, 'out_of_range', f'viento {wind} m/s no puede ser negativo'
    
    # Si llega aquí, es válido
    return True, 'ok', ''

# ==================== Insertar en BD ====================
def insert_into_db(db_conn, payload, status, error_reason=''):
    """
    Inserta un registro de meteorología en PostgreSQL.
    
    Args:
        db_conn: conexión a PostgreSQL
        payload: dict con datos
        status: estado del registro ('ok', 'invalid', 'out_of_range')
        error_reason: razón del error si aplica
    """
    try:
        cur = db_conn.cursor()
        
        # Preparar valores
        station_id = payload.get('station_id')
        timestamp = payload.get('timestamp', datetime.now(timezone.utc).isoformat())
        temperature = payload.get('temperature_c')
        humidity = payload.get('humidity_percent')
        wind = payload.get('wind_speed_ms')
        
        # Determinar estado final
        final_status = status if status == 'ok' else error_reason
        
        # Insertar
        cur.execute(
            """
            INSERT INTO weather_logs 
            (station_id, timestamp, temperature_c, humidity_percent, wind_speed_ms, raw_payload, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                station_id,
                timestamp,
                temperature,
                humidity,
                wind,
                Json(payload),
                final_status
            )
        )
        
        cur.close()
        logger.info(f"✓ Guardado: {station_id} | Temp: {temperature}°C | Status: {final_status}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error insertando en BD: {e}")
        return False

# ==================== Callback de mensaje ====================
def on_message_received(ch, method, properties, body, db_conn):
    """
    Callback ejecutado cada vez que llega un mensaje de RabbitMQ.
    
    Args:
        ch: canal
        method: metadata del método
        properties: propiedades del mensaje
        body: contenido del mensaje (JSON)
        db_conn: conexión a PostgreSQL
    """
    logger.info(f"\n← Mensaje recibido (delivery_tag: {method.delivery_tag})")
    
    try:
        # Parsear JSON
        payload = json.loads(body)
        logger.info(f"  Datos: {payload}")
        
        # Validar
        is_valid, status, reason = validate_payload(payload)
        
        if not is_valid:
            logger.warning(f"  ⚠ Validación falló: {reason}")
        else:
            logger.info(f"  ✓ Validación OK")
        
        # Guardar en BD (incluso si es inválido, para auditoría)
        insert_into_db(db_conn, payload, status, reason)
        
        # RECONOCER MENSAJE (ACK)
        # Si no hacemos ACK, el mensaje se devolverá a la cola
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"  ✓ ACK enviado (mensaje procesado)")
        
    except json.JSONDecodeError as e:
        logger.error(f"  ✗ JSON inválido: {e}")
        # ACK aun así para no atascar la cola
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except Exception as e:
        logger.error(f"  ✗ Error procesando mensaje: {e}")
        # NACK sin requeue: envía a Dead Letter Queue o descarta
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        logger.info(f"  ! NACK sin requeue enviado (mensaje descartado)")

# ==================== Loop principal ====================
def main():
    """
    Loop principal del consumer.
    """
    logger.info("========== INICIANDO CONSUMER ==========")
    logger.info(f"RabbitMQ Host: {RABBIT_HOST}")
    logger.info(f"PostgreSQL Host: {PG_HOST}")
    logger.info(f"Queue: {QUEUE}")
    logger.info("======================================")
    
    db_conn = None
    rabbit_conn = None
    
    while True:
        try:
            # Conectar a BD
            db_conn = connect_db()
            
            # Conectar a RabbitMQ
            rabbit_conn, ch = connect_rabbitmq()
            
            # Registrar callback para mensajes
            # auto_ack=False permite ACK manual
            ch.basic_consume(
                queue=QUEUE,
                on_message_callback=lambda ch, m, p, b: on_message_received(ch, m, p, b, db_conn),
                auto_ack=False
            )
            
            logger.info("✓ Escuchando mensajes...")
            logger.info("  Presiona Ctrl+C para detener\n")
            
            # Comenzar a consumir
            ch.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("\n✓ Consumer detenido por usuario (Ctrl+C)")
            break
        except Exception as e:
            logger.error(f"Error en loop principal: {e}")
            logger.info("  Reintentando en 5 segundos...")
            time.sleep(5)
        
        finally:
            # Limpiar conexiones
            if rabbit_conn and not rabbit_conn.is_closed:
                try:
                    rabbit_conn.close()
                    logger.info("✓ Conexión RabbitMQ cerrada")
                except:
                    pass
            
            if db_conn:
                try:
                    db_conn.close()
                    logger.info("✓ Conexión PostgreSQL cerrada")
                except:
                    pass

if __name__ == "__main__":
    main()