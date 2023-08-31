import os
import json
import logging
import base64
import uuid

from kafka import KafkaConsumer
from kafka.errors import KafkaError
import numpy as np
import cv2

TOPIC = os.environ.get("KAFKA_TOPIC")
DOCKER_KAFKA_HOST = os.environ.get("DOCKER_KAFKA_HOST")
KAFKA_PORT1 = os.environ.get("KAFKA_PORT1")
KAFKA_PORT2 = os.environ.get("KAFKA_PORT2")
KAFKA_PORT3 = os.environ.get("KAFKA_PORT3")
VIDEO_PATHS = os.environ.get("VIDEO_PATHS")

if not DOCKER_KAFKA_HOST:
    logging.error("Exit producer due to DOCKER_KAFKA_HOST is undefined... ")
    exit

logging.info("Consuming kafka stream on topic: {}".format(TOPIC))

bootstrap_servers = []
for port in [KAFKA_PORT1, KAFKA_PORT2, KAFKA_PORT3]:
    if not port:
        continue
    bootstrap_servers.append("{0}:{1}".format(DOCKER_KAFKA_HOST, port))
logging.warning("bootstrap_servers: {}".format(bootstrap_servers))

# consume json messages
consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=bootstrap_servers,
    group_id="test-comsumer",
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
)

for message in consumer:
    try:
        logging.info(
            "%s:%d:%d: key=%s "
            % (
                message.topic,
                message.partition,
                message.offset,
                message.key,
            )
        )
        value = message.value
        img_buffer = base64.b64decode(value["content"])
        img_np = np.frombuffer(img_buffer, dtype=np.uint8)
        img = cv2.imdecode(img_np, flags=1)
        cv2.imwrite("/tmp/{}_{}.jpg".format(value["id_camera"], uuid.uuid4()), img)
    except KafkaError as e:
        print(e)
        logging.exception()
