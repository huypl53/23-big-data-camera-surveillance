import json

from kafka.consumer.fetcher import ConsumerRecord

from model.worker_dto import SinkRecordDTO, SinkOperation, SinkOperationType
from transformers.transformer import StreamTransformer
from utility.common_util import singleton

from ultralytics import YOLO
import base64
import cv2
import numpy as np


@singleton
class YoloTransformer(StreamTransformer):
    def __init__(self, config: dict):
        super().__init__(config)
        self.model = YOLO("yolov8n.onnx")

    def transform(self, consumer_record: ConsumerRecord) -> SinkRecordDTO:
        """
        converts message to message dict
        :param consumer_record: kafka consumer record
        :return: SinkRecordDTO
        """
        # do something here
        # message_dict: dict = json.loads(consumer_record.value)

        img_buffer = base64.b64decode(consumer_record.value["content"])
        img_np = np.frombuffer(img_buffer, dtype=np.uint8)
        img = cv2.imdecode(img_np, flags=1)
        results = self.model(img)
        message_dict = json.loads(results[0].tojson())
        sink_operation = SinkOperation(sink_operation_type=SinkOperationType.UPSERT)

        return SinkRecordDTO(
            key=consumer_record.key,
            message=message_dict,
            topic=consumer_record.topic,
            offset=consumer_record.offset,
            sink_operation=sink_operation,
            partition=consumer_record.partition,
        )
