/**
 * This is not a production server yet!
 * This is only a minimal backend to get started.
 */

import express from 'express';
import * as path from 'path';
import http from 'http';
import { Kafka, logLevel } from 'kafkajs';
import fs from 'fs';

const app = express();
const server = http.createServer(app);

import WebSocket, { WebSocketServer } from 'ws';

const AI_KAFKA_HOST = process.env.AI_KAFKA_HOST || '10.16.208.13';
const KAFKA_PORT1 = process.env.AI_KAFKA_PORT1 || '9092';
const KAFKA_PORT2 = process.env.AI_KAFKA_PORT2 || '9093';
const KAFKA_PORT3 = process.env.AI_KAFKA_PORT3 || '9094';
const AI_TOPIC = process.env.AI_TOPIC || 'ai-streaming';
const API_PORT = parseInt(process.env.API_PORT) || 5000;

app.use('/assets', express.static(path.join(__dirname, 'assets')));

app.get('/api', (req, res) => {
  res.send({ message: 'Welcome to be-gateway!' });
});

// const wss = new WebSocketServer({ port: API_PORT, host: '0.0.0.0' });
const wss = new WebSocketServer({ server });

const kafka_topic = AI_TOPIC;

const kafka = new Kafka({
  logLevel: logLevel.INFO,
  clientId: 'query-app',
  brokers: [KAFKA_PORT1, KAFKA_PORT2, KAFKA_PORT3].map(
    (p) => `${AI_KAFKA_HOST}:${p}`
  ),
});

const consumer = kafka.consumer({ groupId: 'query-app-group' });

const run = async () => {
  await consumer.connect();
  await consumer.subscribe({ topic: kafka_topic, fromBeginning: true });
  await consumer.run({
    // eachBatch: async ({ batch }) => {
    //   console.log(batch)
    // },
    eachMessage: async ({ topic, partition, message }) => {
      const prefix = `${topic}[${partition} | ${message.offset}] / ${message.timestamp}`;
      // console.log(`- ${prefix} ${message.key}#${message.value}`);
      const { value: bufferValue } = message;
      const stringValue = bufferValue.toString();
      const img = JSON.parse(stringValue)?.['image'];
      fs.writeFile(`./data/${partition}.jpg`, img, (err) => {
        console.log({ err });
      });
      console.log(`- ${prefix} ${message.key}#${stringValue.slice(0, 224)}...`);
      wss.clients.forEach(function each(client) {
        if (client.readyState === WebSocket.OPEN) {
          client.send(stringValue);
        }
      });
    },
  });
};

run().catch((e) => console.error(`[example/consumer] ${e.message}`, e));

const errorTypes = ['unhandledRejection', 'uncaughtException'];
const signalTraps = ['SIGTERM', 'SIGINT', 'SIGUSR2'];

errorTypes.forEach((type) => {
  process.on(type, async (e) => {
    try {
      console.log(`process.on ${type}`);
      console.error(e);
      await consumer.disconnect();
      process.exit(0);
    } catch (_) {
      process.exit(1);
    }
  });
});

signalTraps.forEach((type) => {
  process.once(type, async () => {
    try {
      await consumer.disconnect();
    } finally {
      process.kill(process.pid, type);
    }
  });
});

// wss.on('connection', function connection(ws) {
//   ws.on('error', console.error);

//   ws.on('message', function message(data, isBinary) {
//     wss.clients.forEach(function each(client) {
//       if (client.readyState === WebSocket.OPEN) {
//         client.send(data, { binary: isBinary });
//       }
//     });
//   });
// });

const port = API_PORT || 5000;
server.listen(port, 'localhost', null, () => {
  console.log(`We don't want to Listen at http://localhost:${port}/api`);
});
server.on('error', console.error);

console.log({ wss });
