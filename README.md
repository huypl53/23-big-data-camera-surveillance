# This is for leanring

## Docker syntax

- When you use multiple Compose files, you must make sure all paths in the files are relative to the base Compose file. This is required because extend files need not be valid Compose files. Extend files can contain small fragments of configuration. Tracking which fragment of a service is relative to which path is difficult and confusing, so to keep paths easier to understand, all paths must be defined relative to the base file.

- `env_file` directive is sometimes ignored if it is followed by `environment` directive
- in Producer, I set `network_mode: "host"` for container to access external services

## Kafka

- client (producer/consumer)

## OpenCV2

- ubuntu's `ffmpeg` package is neccessary
- cv2 only considers simple file path (without special characters)
