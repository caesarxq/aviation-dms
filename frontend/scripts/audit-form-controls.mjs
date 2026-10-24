import fs from "node:fs";
import path from "node:path";

const root = path.resolve("src");
const failures = [];
let total = 0;

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full);
    else if (entry.isFile() && full.endsWith(".tsx") && !full.endsWith(".test.tsx")) inspect(full);
  }
}

function inspect(file) {
  const source = fs.readFileSync(file, "utf8");
  const controlPattern = /<(input|select|textarea)\b([\s\S]*?)(?:\/>|<\/\1>)/g;
  for (const match of source.matchAll(controlPattern)) {
    total += 1;
    const attrs = match[2];
    const line = source.slice(0, match.index).split("\n").length;
    const hasId = /\bid\s*=/.test(attrs);
    const hasName = /\bname\s*=/.test(attrs);
    const hasLabel = /\baria-label\s*=/.test(attrs);
    if (!hasId && !hasName && !hasLabel) {
      failures.push(`${path.relative(process.cwd(), file)}:${line} <${match[1]}> requires id/name or aria-label`);
    }
  }
}

walk(root);
console.log(`Audited ${total} controls.`);
if (failures.length) {
  console.error(`Found ${failures.length} controls without stable identification:`);
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log("All controls have id/name or aria-label.");
}
