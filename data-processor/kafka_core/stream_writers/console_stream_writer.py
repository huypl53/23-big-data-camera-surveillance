import logging
from typing import List

from model.worker_dto import SinkRecordDTO
from stream_writers.stream_writer import StreamWriter


class ConsoleStreamWriter(StreamWriter):
    def write(self, streams: List[SinkRecordDTO]) -> None:
        """
        Writes processed records read from kafka to Elastic search
        :param streams: List of SinkRecordDTO - transformed data to be written to ES
        :return: None
        """
        for sink_record_dto in streams:
            logging.info(
                f" Key: {sink_record_dto.key} - value: {sink_record_dto.message}"[:224]
            )

    def close(self) -> None:
        pass
