// Development only: npm install --no-save lucide, then node docs/build_icons.cjs.
const fs = require("node:fs");
const path = require("node:path");
const lucide = require("lucide");
const icons = {
  layers: "Layers",
  lock: "Lock",
  github: "ExternalLink",
  "refresh-cw": "RefreshCw",
  "user-check": "UserCheck",
  search: "Search",
  list: "List",
  upload: "Upload",
  "arrow-right": "ArrowRight",
  square: "Square",
  download: "Download",
  "scan-line": "ScanLine",
  "shield-check": "ShieldCheck",
};
const symbols = Object.entries(icons).map(([id, key]) => {
  const shapes = lucide[key]
    .map(
      ([tag, attrs]) =>
        `<${tag} ${Object.entries(attrs)
          .map(([k, v]) => `${k}="${v}"`)
          .join(" ")}/>`,
    )
    .join("");
  return `<symbol id="${id}" viewBox="0 0 24 24">${shapes}</symbol>`;
});
fs.writeFileSync(
  path.join(__dirname, "../voi_mapper/static/icons.svg"),
  '<svg xmlns="http://www.w3.org/2000/svg">' + symbols.join("") + "</svg>\n",
);
