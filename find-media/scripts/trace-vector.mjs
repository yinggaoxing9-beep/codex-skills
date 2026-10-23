// Thin adapter: local RGB decoding + official ColorLayout extraction. No network.
import sharp from "sharp";
import { ColorLayout } from "trace.moe-id";
sharp.cache(false);
sharp.concurrency(1);
try {
  const { data, info } = await sharp(process.argv[2]).rotate()
    .resize({ width: 320, height: 320, fit: "inside", withoutEnlargement: true })
    .flatten({ background: "#000000" }).removeAlpha().raw()
    .toBuffer({ resolveWithObject: true });
  const vector = ColorLayout.extract({ data, width: info.width, height: info.height, channels: 3 });
  if (vector.length !== 33 || !vector.every(Number.isFinite)) throw new Error("invalid vector");
  process.stdout.write(JSON.stringify({ vector, dimensions: [info.width, info.height],
    processing: ["exif_orientation", "resize_inside_320", "flatten_black"],
    library: "trace.moe-id@2.0.0" }));
} catch (error) {
  process.stderr.write("local_vector_failed: " + error.message + "\n");
  process.exitCode = 2;
}
