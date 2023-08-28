import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from consumer_manager import ConsumerWorkerManager

logging.basicConfig(
    format="%(asctime)s-%(process)d-%(levelname)s: %(message)s", level=logging.INFO
)

cwm = ConsumerWorkerManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cwm.start_all_workers()
    yield


app = FastAPI(lifespan=lifespan)

if __name__ == "__main__":
    pass
