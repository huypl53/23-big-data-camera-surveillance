import itertools
import logging
import threading
import time
import os
import uuid
from typing import Dict, List
import json

import ray
from kafka import KafkaConsumer
from ray.actor import ActorHandle

from exceptions.usi_exceptions import BadInput
from ser_des_util import get_ser_des
from sink_task import SinkTask
from utility.common_util import singleton
from utility.config_manager import ConfigManager

# USERNAME = os.environ.get('APP_USERNAME', 'admin')
# PASSWORD = os.environ.get('APP_PASSWORD', 'admin')

WORKER_NUM_CPUS = os.environ.get("WORKER_NUM_CPUS", 0.25)

SASL_USERNAME = os.environ.get("SASL_USERNAME", None)
SASL_PASSWORD = os.environ.get("SASL_PASSWORD", None)
SECURITY_PROTOCOL = os.environ.get("SECURITY_PROTOCOL", "PLAINTEXT")
SASL_MECHANISM = os.environ.get("SASL_MECHANISM")
RAY_HEAD_ADDRESS = os.environ.get("RAY_HEAD_ADDRESS", "auto")
LOCAL_MODE = os.environ.get("LOCAL_MODE", "Y")

logging.info(
    json.dumps(
        {
            "WORKER_NUM_CPUS": WORKER_NUM_CPUS,
            "SASL_USERNAME": SASL_USERNAME,
            "SASL_PASSWORD": SASL_PASSWORD,
            "SECURITY_PROTOCOL": SECURITY_PROTOCOL,
            "SASL_MECHANISM": SASL_MECHANISM,
            "RAY_HEAD_ADDRESS": RAY_HEAD_ADDRESS,
            "LOCAL_MODE": LOCAL_MODE,
        }
    )
)

TWO_MINUTES = 2
MAX_RESTARTS_REMOTE_WORKER = 10

if LOCAL_MODE == "Y":
    ray.init()
else:
    ray.init(address=RAY_HEAD_ADDRESS)

logging.info(
    """This cluster consists of
    {} nodes in total
    {} CPU resources in total
""".format(
        len(ray.nodes()), ray.cluster_resources()["CPU"]
    )
)


@singleton
class ConsumerWorkerManager:
    def __init__(self):
        self.consumer_worker_container: Dict[str, List[ActorHandle]] = {}
        self.config_manager = ConfigManager()
        self.worker_configs = self.config_manager.get_worker_config()
        self.init_container()

    def init_container(self) -> None:
        for worker_config in self.worker_configs:
            self.consumer_worker_container[worker_config.get("consumer_name")] = []

    def stop_all_workers(self):
        for worker_name, worker_actors in self.consumer_worker_container.items():
            for worker_actor in worker_actors:
                # wait on the future to stop the consumers
                ray.get(worker_actor.stop_consumer.remote())

                ray.kill(worker_actor)
            self.consumer_worker_container[worker_name] = []

        logging.info("All consumer workers stopped.")

    def get_all_running_consumer(self):
        result: List[Dict] = []
        for worker_config in self.worker_configs:
            worker: dict = {}
            consumer_name = worker_config.get("consumer_name")
            worker["consumer_name"] = consumer_name
            worker["total_num_workers"] = worker_config.get("number_of_workers")
            if consumer_name in self.consumer_worker_container:
                worker["num_workers_running"] = len(
                    self.consumer_worker_container.get(consumer_name)
                )
                worker["status"] = "RUNNING"
            else:
                worker["num_workers_running"] = 0
                worker["status"] = "STOPPED"

            result.append(worker)

        return result

    def start_all_workers(self):
        started_flag = False
        for worker_config in self.worker_configs:
            # start consumer only if the consumer workers are not running
            if (
                len(
                    self.consumer_worker_container.get(
                        worker_config.get("consumer_name")
                    )
                )
                == 0
            ):
                started_flag = True
                num_workers: int = worker_config.get("number_of_workers", 1)
                i = 1
                for _ in itertools.repeat(None, num_workers):
                    w_name = worker_config.get("consumer_name") + "-" + str(i)
                    worker_actor: ActorHandle = ConsumerWorker.options(
                        name=w_name, max_concurrency=2
                    ).remote(worker_config, w_name)
                    i = i + 1
                    worker_actor.run.remote()
                    self.consumer_worker_container[
                        worker_config.get("consumer_name")
                    ].append(worker_actor)
        if not started_flag:
            raise BadInput(f"All Consumers already running")
        logging.info("All consumer workers started.")

    def start_worker(self, name: str) -> None:
        if name not in self.consumer_worker_container:
            raise BadInput(f"Failed to start. Worker {name} not found.")

        if (
            name in self.consumer_worker_container
            and len(self.consumer_worker_container.get(name)) > 0
        ):
            raise BadInput("Consumer already running.")

        worker_config: dict = self.config_manager.get_worker_config_by_name(name)
        num_workers = worker_config.get("number_of_workers", 1)

        i = 1
        for _ in itertools.repeat(None, num_workers):
            w_name = name + "-" + str(i)
            worker_actor = ConsumerWorker.options(
                name=w_name, max_concurrency=2
            ).remote(worker_config, w_name)
            i = i + 1
            self.consumer_worker_container[name].append(worker_actor)
            worker_actor.run.remote()
        logging.info(f"{num_workers} workers of worker group {name} started.")

    def stop_worker(self, name: str) -> None:
        if name not in self.consumer_worker_container:
            raise BadInput(f"Failed to stop. Worker {name} not found.")

        worker_actors = self.consumer_worker_container[name]

        if len(worker_actors) == 0:
            raise BadInput(f"Worker not running.")

        for worker_actor in worker_actors:
            # wait on the future before killing actors, so that the consumers are terminated
            # gracefully
            ray.get(worker_actor.stop_consumer.remote())

            ray.kill(worker_actor)
        self.consumer_worker_container[name] = []
        logging.info(f"{name} consumer worker stopped.")


@ray.remote(
    max_restarts=MAX_RESTARTS_REMOTE_WORKER,
    max_task_retries=MAX_RESTARTS_REMOTE_WORKER,
    num_cpus=WORKER_NUM_CPUS,
)
class ConsumerWorker:
    def __init__(self, config: dict, worker_name: str):
        # creating a separate logging for individual worker. As they only need to print in stdout
        # or stderr
        logging.basicConfig(level=logging.INFO)
        self.consumer_name = config.get("consumer_name")
        self.worker_name = worker_name
        self.config = config
        self.stop_worker = False
        self.auto_offset_reset = "earliest"
        self.poll_timeout_ms = 1000
        self.sink_task: SinkTask = SinkTask(config)
        self.is_closed = False
        # set to double of poll_timeout_ms because - in the next iteration of poll, thread will
        # attempt to stop kafka consumer
        self.consumer_stop_delay_seconds = 2 * self.poll_timeout_ms / 1000
        self.consumer = KafkaConsumer(
            bootstrap_servers=self.config.get("bootstrap_servers"),
            # client_id=CLIENT_ID,
            group_id=self.consumer_name,
            key_deserializer=get_ser_des(
                self.config.get("key_deserializer", "STRING_DES")
            ),
            value_deserializer=get_ser_des(
                self.config.get("value_deserializer", "JSON_DES")
            ),
            auto_offset_reset=self.auto_offset_reset,
            enable_auto_commit=self.config.get("enable_auto_commit", True),
            max_poll_records=self.config.get("max_poll_records", 50),
            max_poll_interval_ms=self.config.get("max_poll_interval_ms", 600000),
            security_protocol=SECURITY_PROTOCOL,
            sasl_mechanism=SASL_MECHANISM,
            sasl_plain_username=SASL_USERNAME,
            sasl_plain_password=SASL_PASSWORD,
            consumer_timeout_ms=1000,
        )
        self.consumer.subscribe([self.config.get("topic_name")])
        logging.info(f"Started consumer worker {self.worker_name}")

    def stop_consumer(self) -> None:
        logging.info(f"Stopping consumer worker {self.worker_name}")
        self.stop_worker = True

        # give time for the consumer to stop gracefully
        time.sleep(self.consumer_stop_delay_seconds)
        logging.info(f"Stopped consumer worker {self.worker_name}")

    def closed(self):
        return self.is_closed

    def run(self) -> None:
        while not self.stop_worker:
            tp_records_dict = self.consumer.poll(timeout_ms=self.poll_timeout_ms)

            if tp_records_dict is None or len(tp_records_dict.items()) == 0:
                continue
            try:
                for topic_partition, consumer_records in tp_records_dict.items():
                    self.sink_task.process(consumer_records)

                # consumer.commit() not work with zookeeper
                # https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html#kafka.KafkaConsumer.commit
                # self.consumer.commit()

                if self.stop_worker:
                    self.consumer.close()
                    self.is_closed = True
                    break
            except BaseException as e:
                logging.error("Error while running consumer worker!")
                logging.error(e)
