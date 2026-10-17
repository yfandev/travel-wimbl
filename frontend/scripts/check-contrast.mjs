// Fails if any className pairs gold text with a white background or white text with a gold background.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const roots = ["app", "components"];
const files = roots.flatMap(function walk(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? walk(p) : /\.(tsx|ts)$/.test(f) ? [p] : [];
  });
});

const bad = [];
for (const file of files) {
  for (const [, cls] of readFileSync(file, "utf8").matchAll(/className=\{?[`"]([^`"]+)[`"]/g)) {
    const t = cls.split(/\s+/);
    if ((t.includes("text-gold") && (t.includes("bg-white") || !t.some((c) => c.startsWith("bg-")))) || (t.includes("text-white") && t.includes("bg-gold")))
      bad.push(`${file}: ${cls}`);
  }
}
if (bad.length) { console.error("Gold/white contrast violations:\n" + bad.join("\n")); process.exit(1); }
console.log(`Contrast rule OK (${files.length} files).`);
