import os
import logging
import base64
import json

from kafka import KafkaProducer
from kafka.errors import KafkaError

import cv2

logging.basicConfig(
    format="%(asctime)s-%(process)d-%(levelname)s: %(message)s", level=logging.INFO
)

TOPIC = os.environ.get("KAFKA_TOPIC")
DOCKER_KAFKA_HOST = os.environ.get("DOCKER_KAFKA_HOST")
KAFKA_PORT1 = os.environ.get("KAFKA_PORT1")
KAFKA_PORT2 = os.environ.get("KAFKA_PORT2")
KAFKA_PORT3 = os.environ.get("KAFKA_PORT3")
VIDEO_PATHS = os.environ.get("VIDEO_PATHS")

logging.info(
    "Starting with config: {}".format(
        json.dumps(
            {
                "TOPIC": TOPIC,
                "DOCKER_KAFKA_HOST": DOCKER_KAFKA_HOST,
                "KAFKA_PORT1": KAFKA_PORT1,
                "KAFKA_PORT2": KAFKA_PORT2,
                "KAFKA_PORT3": KAFKA_PORT3,
                "VIDEO_PATHS": VIDEO_PATHS,
            }
        )
    )
)
if not DOCKER_KAFKA_HOST:
    logging.error("Exit producer due to DOCKER_KAFKA_HOST is undefined... ")
    exit

logging.info("Streaming kafka on topic: {}".format(TOPIC))

bootstrap_servers = []
for port in [KAFKA_PORT1, KAFKA_PORT2, KAFKA_PORT3]:
    if not port:
        continue
    bootstrap_servers.append("{0}:{1}".format(DOCKER_KAFKA_HOST, port))

if not len(bootstrap_servers) or not DOCKER_KAFKA_HOST:
    logging.error("Empty env variables for bootstrap_servers")
    exit
producer = KafkaProducer(
    bootstrap_servers=bootstrap_servers,
    api_version=(2, 5, 0),
    retries=2,
    value_serializer=lambda m: json.dumps(m).encode("utf-8"),
)


def on_send_success(record_metadata):
    print(record_metadata.topic)
    print(record_metadata.partition)
    print(record_metadata.offset)


def on_send_error(excp):
    logging.error("I am an errback", exc_info=excp)
    # handle exception


while True:
    for root, dir, files in os.walk(VIDEO_PATHS):
        file_paths = [os.path.join(root, f) for f in files]
        for file_path, file_name in zip(file_paths, files):
            cap = cv2.VideoCapture(file_path)
            logging.info(
                "Streaming file {}, isOpened: {}".format(file_path, cap.isOpened())
            )
            sent_num = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    # logging.error("Error on reading file {}".format(file_path))
                    break

                # print("frame size: {}".format(frame.shape))
                _, buffer = cv2.imencode(".jpg", frame)
                buffer_as_text = base64.b64encode(buffer).decode()
                msg_object = {"id_camera": file_name, "content": buffer_as_text}

                sent_num += 1
                producer.send(TOPIC, msg_object).add_errback(on_send_error)

                # producer.send(TOPIC, msg_object).add_callback(
                #     on_send_success
                # ).add_errback(on_send_error)

            logging.info("Sent {} frames".format(sent_num))
            cap.release()

            os.remove(file_path)


# producer.flush()
