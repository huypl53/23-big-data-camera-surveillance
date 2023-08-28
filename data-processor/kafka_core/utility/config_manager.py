import copy
import json
import os
import pprint
import logging

# from src import WORKER_CONFIG_PATH, ROOT_SRC_DIR
from exceptions.usi_exceptions import BadInput
from utility.common_util import singleton

# ENV = os.environ.get("env", "dev")
# AWS_REGION = os.environ.get("aws_region", "")

WORKER_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "consumer.json"
)


@singleton
class ConfigManager:
    def __init__(self):
        self._worker_config = None
        self._load_consumer_config()

    def _load_consumer_config(self) -> None:
        # with open(ROOT_SRC_DIR + WORKER_CONFIG_PATH, "r") as f:
        with open(WORKER_CONFIG_PATH, "r") as f:
            self._worker_config = json.load(f)

            DOCKER_KAFKA_HOST = os.environ.get("DOCKER_KAFKA_HOST")
            KAFKA_PORT1 = os.environ.get("KAFKA_PORT1")
            KAFKA_PORT2 = os.environ.get("KAFKA_PORT2")
            KAFKA_PORT3 = os.environ.get("KAFKA_PORT3")

            TOPIC_NAME = os.environ.get("KAFKA_TOPIC")
            bootstrap_servers = [
                "{}:{}".format(DOCKER_KAFKA_HOST, port)
                for port in [KAFKA_PORT1, KAFKA_PORT2, KAFKA_PORT3]
            ]

            self._worker_config[0]["bootstrap_servers"] = bootstrap_servers
            self._worker_config[0]["topic_name"] = TOPIC_NAME

            AI_TOPIC = os.environ.get("AI_TOPIC")
            self._worker_config[0]["dlq_config"][
                "bootstrap_servers"
            ] = bootstrap_servers
            self._worker_config[0]["dlq_config"]["topic_name"] = AI_TOPIC

            logging.info("Worker config: ")
            pprint.pprint(self._worker_config)

    def get_worker_config(self) -> list:
        return copy.deepcopy(self._worker_config)

    def get_worker_config_by_name(self, name: str) -> dict:
        for config in self._worker_config:
            if config["consumer_name"] == name:
                return config

        raise BadInput(f"Consumer name: {name}, is not configured.")
