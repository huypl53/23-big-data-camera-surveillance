# FROM hdgigante/python-opencv:4.7.0-ubuntu
FROM python:3.9.18-slim-bullseye

ARG WORK_DIR
WORKDIR ${WORK_DIR}

COPY lib ./lib
RUN /bin/bash -c "apt update && apt install --fix-missing ffmpeg -y && pip install kafka-python opencv-python==4.7.0.72 opencv-contrib-python==4.7.0.72 numpy==1.25.2"