import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const runtime = "nodejs";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const ALLOWED_ROOTS = [
  path.resolve(PROJECT_ROOT, "workspace", "output_tabs"),
  path.resolve(PROJECT_ROOT, "workspace", "input_stems"),
];

function isPathInside(child: string, parent: string): boolean {
  const relative = path.relative(parent, child);
  return Boolean(relative) && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

export async function GET(req: NextRequest) {
  const requested = req.nextUrl.searchParams.get("file");
  let candidatePath = requested;

  if (!candidatePath) {
    const outputTabsDir = path.resolve(PROJECT_ROOT, "workspace", "output_tabs");
    if (fs.existsSync(outputTabsDir)) {
      const files = fs.readdirSync(outputTabsDir);
      const gp5 = files.find((f) => f.toLowerCase().endsWith(".gp5"));
      if (gp5) {
        candidatePath = path.join(outputTabsDir, gp5);
      }
    }
  }

  if (!candidatePath) {
    return NextResponse.json({ status: "error", message: "No tab file found." }, { status: 404 });
  }

  if (!path.isAbsolute(candidatePath)) {
    candidatePath = path.resolve(PROJECT_ROOT, candidatePath);
  }

  if (!fs.existsSync(candidatePath)) {
    return NextResponse.json({ status: "error", message: "Tab file does not exist." }, { status: 404 });
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
      { status: "error", message: "File is outside allowed directories." },
      { status: 403 }
    );
  }

  const fileBuffer = fs.readFileSync(filePath);
  const filename = path.basename(filePath);

  return new NextResponse(fileBuffer, {
    status: 200,
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}
