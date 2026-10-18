import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { Readable } from "stream";

export const runtime = "nodejs";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const STEM_ROOT = path.resolve(PROJECT_ROOT, "workspace", "input_stems");

export async function GET(req: NextRequest) {
  const requested = req.nextUrl.searchParams.get("file");
  if (!requested) return NextResponse.json({ status: "error", message: "file is required" }, { status: 400 });

  const candidatePath = path.resolve(PROJECT_ROOT, "workspace", requested);
  const relative = path.relative(STEM_ROOT, candidatePath);
  if (!relative || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    return NextResponse.json({ status: "error", message: "Only generated stem files can be streamed." }, { status: 403 });
  }
  if (!fs.existsSync(candidatePath)) return NextResponse.json({ status: "error", message: "Stem audio file not found." }, { status: 404 });
  const filePath = fs.realpathSync(candidatePath);
  const realRelative = path.relative(fs.realpathSync(STEM_ROOT), filePath);
  if (!realRelative || realRelative.startsWith(`..${path.sep}`) || path.isAbsolute(realRelative)) {
    return NextResponse.json({ status: "error", message: "Stem audio file is outside the allowed directory." }, { status: 403 });
  }
  if (!/\.wav$/i.test(filePath) || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    return NextResponse.json({ status: "error", message: "Stem audio file not found." }, { status: 404 });
  }

  const stat = fs.statSync(filePath);
  const range = req.headers.get("range");
  const headers = new Headers({
    "Content-Type": "audio/wav",
    "Accept-Ranges": "bytes",
    "Cache-Control": "no-store",
  });
  if (range) {
    const match = /^bytes=(\d*)-(\d*)$/.exec(range);
    if (!match) return new NextResponse(null, { status: 416 });
    const start = match[1] ? Number(match[1]) : 0;
    const end = match[2] ? Math.min(Number(match[2]), stat.size - 1) : stat.size - 1;
    if (start > end || start >= stat.size) return new NextResponse(null, { status: 416 });
    headers.set("Content-Range", `bytes ${start}-${end}/${stat.size}`);
    headers.set("Content-Length", String(end - start + 1));
    return new NextResponse(Readable.toWeb(fs.createReadStream(filePath, { start, end })) as ReadableStream, { status: 206, headers });
  }

  headers.set("Content-Length", String(stat.size));
  return new NextResponse(Readable.toWeb(fs.createReadStream(filePath)) as ReadableStream, { status: 200, headers });
}
