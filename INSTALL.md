# Install struction

## Kafka

```bash
cd ./zk-kafka/
docker-compose -f zk-kafka-docker-compose.yml up
```

### Producer

```bash
cd ./zk-kafka/producer
docker-compose -f producer-docker-compose.yml up
```

Copy videos to ./zk-kafka/producer/videos
