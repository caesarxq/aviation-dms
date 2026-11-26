#!/usr/bin/env node
/**
 * Bundle-size guardrail for the KFL Aviation DMS frontend.
 *
 * After `npm run build`, this script checks that no single JS chunk in
 * `dist/assets` exceeds the configured gzipped size limit. Exits non-zero if
 * any chunk is over budget, so CI can fail a PR that introduces a large
 * dependency or a page that bundles too much code.
 *
 * Vendor/shared chunks (react, prosemirror, react-query, ui shell, utils)
 * are reported but not failed against the page-chunk limit, since they are
 * shared libraries used across many pages.
 *
 * Usage:
 *   npm run build
 *   node scripts/check-bundle-size.js [--max-kb 100]
 */

import { gzipSync } from "node:zlib";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const MAX_KB = parseInt(process.env.MAX_CHUNK_KB || "100", 10);
const DIST_DIR = join(process.cwd(), "dist", "assets");

// Shared library / vendor chunks — reported but not failed against the
// page-chunk limit.
const VENDOR_PREFIXES = [
  "prosemirror-",
  "react-",
  "react-dom",
  "query-",
  "ui-",
  "utils-",
];

function isVendor(file) {
  return VENDOR_PREFIXES.some((prefix) => file.startsWith(prefix));
}

async function main() {
  const files = await readdir(DIST_DIR);
  const jsFiles = files.filter((f) => f.endsWith(".js"));

  let failures = 0;

  for (const file of jsFiles) {
    const fullPath = join(DIST_DIR, file);
    const contents = await readFile(fullPath);
    const compressed = gzipSync(contents);
    const sizeKB = compressed.length / 1024;

    if (sizeKB > MAX_KB) {
      if (isVendor(file)) {
        console.warn(
          "VENDOR CHUNK (over limit, informational): " +
            file +
            " is " +
            sizeKB.toFixed(1) +
            " KB gzipped (limit: " +
            MAX_KB +
            " KB)",
        );
      } else {
        console.error(
          "BUNDLE SIZE VIOLATION: " +
            file +
            " is " +
            sizeKB.toFixed(1) +
            " KB gzipped (limit: " +
            MAX_KB +
            " KB)",
        );
        failures += 1;
      }
    } else {
      console.log("OK: " + file + " is " + sizeKB.toFixed(1) + " KB gzipped");
    }
  }

  if (failures > 0) {
    console.error("\n" + failures + " bundle size violation(s) found.");
    process.exit(1);
  }

  console.log(
    "\nAll " +
      jsFiles.length +
      " JS chunks are within the " +
      MAX_KB +
      " KB gzipped limit (vendor chunks reported separately).",
  );
}

main().catch(function (err) {
  console.error("Bundle size check failed:", err);
  process.exit(1);
});
