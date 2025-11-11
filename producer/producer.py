#!/usr/bin/env python
"""
Producer de datos meteorológicos.
Genera mensajes simulados de estaciones y los publica en RabbitMQ.
"""

import os
import time
import json
import random
import logging
import uuid
from datetime import datetime, timezone
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

# ==================== Configuración ====================
RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBIT_USER = os.getenv("RABBITMQ_USER", "rabbit")
RABBIT_PASS = os.getenv("RABBITMQ_PASS", "rabbitpass")

EXCHANGE = "weather_exchange"
ROUTING_KEY = "weather.logs"

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [PRODUCER] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== Conexión a RabbitMQ ====================
def connect_rabbitmq():
    """
    Conecta a RabbitMQ con reintentos automáticos.
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
            logger.info("✓ Conectado a RabbitMQ")
            return conn, ch
        except AMQPConnectionError as e:
            logger.error(f"✗ Error conectando a RabbitMQ: {e}")
            logger.info("  Reintentando en 5 segundos...")
            time.sleep(5)

# ==================== Declarar exchange y cola ====================
def declare_exchange(ch):
    """
    Declara el exchange durable para mensajes de meteorología.
    """
    try:
        ch.exchange_declare(
            exchange=EXCHANGE,
            exchange_type='direct',
            durable=True  # Persiste después de reiniciar RabbitMQ
        )
        logger.info(f"✓ Exchange '{EXCHANGE}' declarado")
    except AMQPChannelError as e:
        logger.error(f"Error declarando exchange: {e}")

# ==================== Publicar mensaje ====================
def publish_message(ch, payload):
    """
    Publica un mensaje de forma persistente a RabbitMQ.
    
    Args:
        ch: canal de RabbitMQ
        payload: dict con datos meteorológicos
    """
    try:
        ch.basic_publish(
            exchange=EXCHANGE,
            routing_key=ROUTING_KEY,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistente: se guardan en disco
                content_type='application/json',
                message_id=str(uuid.uuid4()),  # ID único para cada mensaje
                timestamp=int(time.time() * 1000)
            )
        )
        logger.info(f"→ Publicado: {payload['station_id']} | Temp: {payload['temperature_c']}°C")
    except Exception as e:
        logger.error(f"Error publicando mensaje: {e}")

# ==================== Generar datos simulados ====================
def generate_weather_data():
    """
    Genera datos meteorológicos simulados realistas.
    
    Retorna: dict con estación, temperatura, humedad, viento
    """
    station_id = f"station_{random.randint(1, 5)}"
    
    # Temperaturas realistas según región
    temperature_c = round(random.uniform(-10, 40), 2)
    
    # Humedad entre 0 y 100%
    humidity_percent = round(random.uniform(20, 95), 2)
    
    # Velocidad del viento realista (m/s)
    wind_speed_ms = round(random.uniform(0, 25), 3)
    
    payload = {
        "station_id": station_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": temperature_c,
        "humidity_percent": humidity_percent,
        "wind_speed_ms": wind_speed_ms
    }
    
    return payload

# ==================== Loop principal ====================
def main():
    """
    Loop principal del producer.
    Conecta a RabbitMQ, declara exchange y publica mensajes continuamente.
    """
    logger.info("========== INICIANDO PRODUCER ==========")
    logger.info(f"RabbitMQ Host: {RABBIT_HOST}")
    logger.info(f"Exchange: {EXCHANGE}")
    logger.info(f"Routing Key: {ROUTING_KEY}")
    logger.info("======================================")
    
    conn = None
    reconnect_delay = 5
    
    while True:
        try:
            # Conectar a RabbitMQ
            conn, ch = connect_rabbitmq()
            
            # Declarar exchange persistente
            declare_exchange(ch)
            
            # Loop de publicación de mensajes
            message_count = 0
            while True:
                try:
                    # Generar datos
                    payload = generate_weather_data()
                    
                    # Publicar
                    publish_message(ch, payload)
                    
                    message_count += 1
                    
                    # Pausa entre mensajes (ajusta según necesidad)
                    time.sleep(2)
                    
                except KeyboardInterrupt:
                    logger.info("\n✓ Producer detenido por usuario (Ctrl+C)")
                    break
                except Exception as e:
                    logger.error(f"Error en loop de publicación: {e}")
                    break
            
            logger.info(f"Total mensajes publicados en esta sesión: {message_count}")
            
        except Exception as e:
            logger.error(f"Error fatal: {e}")
        
        finally:
            # Cerrar conexión
            if conn and not conn.is_closed:
                try:
                    conn.close()
                    logger.info("✓ Conexión RabbitMQ cerrada")
                except Exception as e:
                    logger.error(f"Error cerrando conexión: {e}")
            
            # Reintentar después de delay
            logger.info(f"Reintentando en {reconnect_delay} segundos...")
            time.sleep(reconnect_delay)

if __name__ == "__main__":
    main()