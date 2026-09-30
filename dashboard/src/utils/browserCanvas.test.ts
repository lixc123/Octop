import { describe, expect, it } from "vitest";
import { getCanvasCoords } from "./browserCanvas";

function canvasFixture() {
  const canvas = document.createElement("canvas");
  Object.defineProperty(canvas, "width", { value: 1280 });
  Object.defineProperty(canvas, "height", { value: 800 });
  Object.defineProperty(canvas, "getBoundingClientRect", {
    value: () => ({
      left: 10,
      top: 20,
      width: 720,
      height: 500,
      right: 730,
      bottom: 520,
      x: 10,
      y: 20,
      toJSON: () => ({}),
    }),
  });
  return canvas;
}

describe("getCanvasCoords", () => {
  it("maps through contain letterbox offsets", () => {
    const canvas = canvasFixture();

    // 1280x800 fitted into 720x500 is 720x450, leaving 25px bars vertically.
    expect(getCanvasCoords(canvas, { clientX: 10, clientY: 45 })).toEqual({
      x: 0,
      y: 0,
    });
    expect(getCanvasCoords(canvas, { clientX: 370, clientY: 270 })).toEqual({
      x: 640,
      y: 400,
    });
  });

  it("clamps pointer coordinates that land in the letterbox bars", () => {
    const canvas = canvasFixture();

    expect(getCanvasCoords(canvas, { clientX: 370, clientY: 20 })).toEqual({
      x: 640,
      y: 0,
    });
  });
});
