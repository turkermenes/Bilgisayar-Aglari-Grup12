export type Point = { x: number; y: number };

type Options = {
  width: number;
  height: number;
  minDistPx?: number;
  maxAttemptsPerNode?: number;
  landThreshold?: number; 
};


export async function generateLandPositions(
  imageUrl: string,
  nodeIds: string[],
  opts: Options
): Promise<Record<string, Point>> {
  const {
    width,
    height,
    minDistPx = 18,
    maxAttemptsPerNode = 5000,
    landThreshold = 220
  } = opts;

  const img = await loadImage(imageUrl);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D context not available");

  
  drawImageCover(ctx, img, 0, 0, width, height);

  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;

  const positions: Record<string, Point> = {};
  const placed: Point[] = [];

  const isLand = (x: number, y: number) => {
    const ix = Math.max(0, Math.min(width - 1, Math.floor(x)));
    const iy = Math.max(0, Math.min(height - 1, Math.floor(y)));
    const idx = (iy * width + ix) * 4;
    const r = data[idx];
    const g = data[idx + 1];
    const b = data[idx + 2];
    const a = data[idx + 3];

    if (a < 10) return false;

 
    return r >= landThreshold && g >= landThreshold && b >= landThreshold;
  };

  const dist2 = (p1: Point, p2: Point) => {
    const dx = p1.x - p2.x;
    const dy = p1.y - p2.y;
    return dx * dx + dy * dy;
  };

  
  const pad = 20;
  const xmin = pad;
  const xmax = width - pad;
  const ymin = pad;
  const ymax = height - pad;

  for (const id of nodeIds) {
    let attempt = 0;
    let found: Point | null = null;

    let dynamicMinDist = minDistPx;
    const minDistFloor = 8;

    while (attempt < maxAttemptsPerNode && !found) {
      attempt++;

      const x = randomBetween(xmin, xmax);
      const y = randomBetween(ymin, ymax);

      if (!isLand(x, y)) continue;

      const candidate = { x, y };

   
      let ok = true;
      const minD2 = dynamicMinDist * dynamicMinDist;
      for (const p of placed) {
        if (dist2(candidate, p) < minD2) {
          ok = false;
          break;
        }
      }

      if (ok) {
        found = candidate;
        break;
      }

     
      if (attempt % 1000 === 0 && dynamicMinDist > minDistFloor) {
        dynamicMinDist = Math.max(minDistFloor, dynamicMinDist - 2);
      }
    }

    
    if (!found) {
      found = { x: randomBetween(xmin, xmax), y: randomBetween(ymin, ymax) };
    }

    positions[id] = found;
    placed.push(found);
  }

  return positions;
}

function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous"; 
    img.onload = () => resolve(img);
    img.onerror = (e) => reject(new Error(`Failed to load image: ${url}`));
    img.src = url;
  });
}


 
function drawImageCover(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  x: number,
  y: number,
  w: number,
  h: number
) {
  const imgRatio = img.width / img.height;
  const boxRatio = w / h;

  let drawW = w;
  let drawH = h;
  let offsetX = 0;
  let offsetY = 0;

  if (imgRatio > boxRatio) {
    
    drawH = h;
    drawW = h * imgRatio;
    offsetX = (w - drawW) / 2;
  } else {
 
    drawW = w;
    drawH = w / imgRatio;
    offsetY = (h - drawH) / 2;
  }

  ctx.drawImage(img, x + offsetX, y + offsetY, drawW, drawH);
}
