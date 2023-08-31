'use client';
import React, { useEffect, useRef } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { JsonValue } from 'react-use-websocket/dist/lib/types';

type TBox = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

type TJsonMessage = JsonValue & {
  image: string;
  predictions: { name: string; class: number; confidence: number; box: TBox }[];
};
const socketUrl = 'ws://localhost:5000';

const fontStyles = [
  '#FF3838',
  '#FF9D97',
  '#FF701F',
  '#FFB21D',
  '#CFD231',
  '#48F90A',
  '#92CC17',
  '#3DDB86',
  '#1A9334',
  '#00D4BB',
  '#2C99A8',
  '#00C2FF',
  '#344593',
  '#6473FF',
  '#0018EC',
  '#8438FF',
  '#520085',
  '#CB38FF',
  '#FF95C8',
  '#FF37C7',
];
const canvasDrawText = (
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  fontStyle?: string
) => {
  if (fontStyle) ctx.fillStyle = fontStyle;
  ctx.font = '1.5rem Arial';
  ctx.fillText(text, x, y);
};

export default function CameraContent() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { lastJsonMessage } = useWebSocket<TJsonMessage>(socketUrl);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !lastJsonMessage) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    // console.log({ ctx });
    const image = new Image();

    const { image: imageBase64, predictions } = lastJsonMessage;
    image.src = `data:image/jpeg;base64,${imageBase64}`;
    const iw: number = image.naturalWidth,
      ih: number = image.naturalHeight;
    image.onload = function (e) {
      ctx?.drawImage(image, 0, 0, iw, ih, 0, 0, canvas.width, canvas.height);
    };
    predictions.forEach((pred) => {
      const {
        box: { x1, y1, x2, y2 },
      } = pred;
      canvasDrawText(
        ctx,
        `${pred.name}-${pred.confidence?.toFixed(2)}`,
        (x1 / iw) * canvas.width,
        (y1 / ih) * canvas.height - 10,
        fontStyles[pred.class]
      );
      console.log({
        x1,
        iw,
        ih,
        naturalWidth: image.naturalWidth,
        naturalHeight: image.naturalHeight,
      });
      ctx.strokeStyle = fontStyles[pred.class];
      ctx.strokeRect(
        (x1 / iw) * canvas.width,
        (y1 / ih) * canvas.height,
        ((x2 - x1) / iw) * canvas.width,
        ((y2 - y1) / ih) * canvas.height
      );
    });
  }, [lastJsonMessage]);
  return (
    <>
      {/* <div className="w-full h-full bg-red-500"> */}
      <div className="flex items-center justify-center w-full h-full bg-gray-100 ">
        <canvas
          className="w-3/4 h-3/4 m-auto border border-gray-400"
          ref={canvasRef}
          height={480 * 2}
          width={640 * 2}
        ></canvas>
      </div>
    </>
  );
}
