import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { Readable } from "stream";

export const runtime = "nodejs";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const ALLOWED_ROOTS = [
  path.resolve(PROJECT_ROOT, "workspace", "input_stems"),
  path.resolve(PROJECT_ROOT, "workspace", "output_audio"),
  path.resolve(PROJECT_ROOT, "workspace", "source_songs"),
];

function isPathInside(child: string, parent: string): boolean {
  const relative = path.relative(parent, child);
  return Boolean(relative) && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

export async function GET(req: NextRequest) {
  const requested = req.nextUrl.searchParams.get("file");
  if (!requested) {
    return NextResponse.json({ status: "error", message: "file is required" }, { status: 400 });
  }

  let candidatePath = requested;
  if (!path.isAbsolute(candidatePath)) {
    candidatePath = path.resolve(PROJECT_ROOT, "workspace", requested);
  }

  if (!fs.existsSync(candidatePath)) {
    return NextResponse.json({ status: "error", message: "Audio file not found." }, { status: 404 });
  }

  const filePath = fs.realpathSync(candidatePath);
  const isAllowed = ALLOWED_ROOTS.some((root) => {
    try {
      const realRoot = fs.realpathSync(root);
      return isPathInside(filePath, realRoot) || filePath === realRoot;
    } catch {
      return false;
    }
  });

  if (!isAllowed) {
    return NextResponse.json(
      { status: "error", message: "Audio file is outside the allowed directories." },
      { status: 403 }
    );
  }

  if (!/\.(wav|mp3|flac|ogg)$/i.test(filePath) || !fs.statSync(filePath).isFile()) {
    return NextResponse.json({ status: "error", message: "Invalid audio file type." }, { status: 400 });
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
    return new NextResponse(Readable.toWeb(fs.createReadStream(filePath, { start, end })) as ReadableStream, {
      status: 206,
      headers,
    });
  }

  headers.set("Content-Length", String(stat.size));
  return new NextResponse(Readable.toWeb(fs.createReadStream(filePath)) as ReadableStream, {
    status: 200,
    headers,
  });
}
