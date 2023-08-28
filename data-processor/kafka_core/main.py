import logging
from consumer_manager import ConsumerWorkerManager

logging.basicConfig(
    format="%(asctime)s-%(process)d-%(levelname)s: %(message)s", level=logging.INFO
)

cwm = ConsumerWorkerManager()

if __name__ == "__main__":
    cwm.start_all_workers()
    pass
