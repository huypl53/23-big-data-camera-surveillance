import logging
import time
from abc import ABC
from typing import List

from kafka.consumer.fetcher import ConsumerRecord
from ratelimit import limits, sleep_and_retry

from exceptions.usi_exceptions import BadConsumerConfigException

from kafka_stream_writer import KafkaStreamWriter
from model.worker_dto import DeadLetterDTO, SinkRecordDTO
from stream_writers.stream_writer import StreamWriter, get_stream_writers
from transformers.transformer import get_transformer

ONE_SECOND = 1
CALLS = 20


class SinkTask(ABC):
    def __init__(self, config: dict):
        self.sink_configs = config.get("sink_configs")
        if self.sink_configs is None:
            raise BadConsumerConfigException("Missing Sink Config.")
        self.config = config
        processor_cls_path = self.sink_configs.get("transformer_cls")
        if not processor_cls_path:
            raise BadConsumerConfigException(
                "sink_configs.transformer_cls is a mandatory config"
            )
        self.stream_transformer = get_transformer(processor_cls_path, self.sink_configs)
        self.operation_extractor = None
        stream_writer_cls_paths: List[str] = self.sink_configs.get("stream_writers")
        if not stream_writer_cls_paths or len(stream_writer_cls_paths) == 0:
            raise BadConsumerConfigException(
                "sink_configs.stream_writers is a mandatory config"
            )

        # TODO: should Write to HDFS
        self.sink_stream_writers: List[StreamWriter] = get_stream_writers(
            stream_writer_cls_paths, self.sink_configs
        )

        # if config.get("dlq_config") is not None:
        self.dlq_stream_writer: KafkaStreamWriter[DeadLetterDTO] = KafkaStreamWriter(
            config.get("dlq_config")
        )

        self.retries = self.sink_configs.get("num_retries", 3)
        self.retry_delay_seconds = self.sink_configs.get("retry_delay_seconds", 1)

    def write_to_sink(self, sink_record_dto_list: List[SinkRecordDTO]):
        for stream_writer in self.sink_stream_writers:
            retries = 0
            while retries <= self.retries:
                try:
                    stream_writer.write(sink_record_dto_list)
                    break
                except Exception as e:
                    if retries == self.retries:
                        raise e
                    retries = retries + 1
                    logging.error(
                        f"{type(stream_writer)} - Failed with exception: {e}, retrying "
                        f"attempt"
                        f" {retries}"
                    )
                    time.sleep(self.retry_delay_seconds)

    @sleep_and_retry
    @limits(calls=CALLS, period=1)
    def process(self, consumer_records: List[ConsumerRecord]):
        for consumer_record in consumer_records:
            try:
                sink_record_dto: SinkRecordDTO = self.stream_transformer.transform(
                    consumer_record
                )
                sink_record_dto_list: List[SinkRecordDTO] = [sink_record_dto]
            except Exception as e:
                logging.error(
                    consumer_record.key,
                    consumer_record.value,
                    consumer_record.topic,
                    consumer_record.partition,
                    "TRANSFORM",
                    e,
                    consumer_record.offset,
                )
                continue
            try:
                self.produce(
                    sink_record_dto.message,
                )
            except Exception as e:
                self.log_failed(
                    consumer_record.key,
                    consumer_record.value,
                    consumer_record.topic,
                    consumer_record.partition,
                    "PRODUCE_RESULTS",
                    e,
                    consumer_record.offset,
                )

            try:
                self.write_to_sink(sink_record_dto_list)
            except Exception as e:
                self.log_failed(
                    consumer_record.key,
                    consumer_record.value,
                    consumer_record.topic,
                    consumer_record.partition,
                    "SINK_UPDATE",
                    e,
                    consumer_record.offset,
                )
                continue

    def log_failed(
        self,
        key: str,
        message: str,
        topic: str,
        partition: int,
        failed_at: str,
        error: Exception,
        offset: int,
    ):
        logging.warning(
            f"failed to {failed_at} key: {key} and message: {message}, in topic {topic} "
            f"having offset {offset}, with error: {error}"
        )

    def produce(
        self,
        message: str,
    ):
        try:
            if self.dlq_stream_writer is not None:
                self.dlq_stream_writer.write([message])
        except Exception as e:
            logging.error(f"Failed to write to DLQ: {e}")
