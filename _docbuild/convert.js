// Conversor Markdown -> DOCX (focado nos recursos usados em INSTALACAO.md/MANUAL.md).
// Suporta: títulos (#/##/###), parágrafos, listas (-, 1.), citações (>), regras (---),
// tabelas (| ... |), blocos de código (```), e inline **negrito** e `código`.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, LevelFormat, BorderStyle, WidthType, ShadingType,
} = require("docx");

const INPUT = process.argv[2] || "../INSTALACAO.md";
const OUTPUT = process.argv[3] || "../INSTALACAO.docx";
const CONTENT_WIDTH = 9360; // US Letter, margens de 1"

const src = fs.readFileSync(INPUT, "utf8").replace(/\r\n/g, "\n");
const lines = src.split("\n");

// ---------- inline: links, **negrito**, `código` ----------
function inlineRuns(text, base = {}) {
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1"); // [txt](url) -> txt
  const runs = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) runs.push(mk(text.slice(last, m.index), base));
    const tok = m[0];
    if (tok.startsWith("**")) runs.push(mk(tok.slice(2, -2), { ...base, bold: true }));
    else runs.push(mk(tok.slice(1, -1), { ...base, code: true }));
    last = re.lastIndex;
  }
  if (last < text.length) runs.push(mk(text.slice(last), base));
  if (runs.length === 0) runs.push(mk("", base));
  return runs;
}
function mk(t, o = {}) {
  return new TextRun({
    text: t, bold: !!o.bold, italics: !!o.italic,
    color: o.color, font: o.code ? "Consolas" : undefined, size: o.size,
  });
}

// ---------- parser por blocos ----------
const children = [];
let numBlock = 0;        // id do bloco de lista numerada atual
const numRefsUsed = new Set();
let prevWasNum = false;

function tableBlock(start) {
  const rows = [];
  let i = start;
  while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(lines[i]); i++; }
  const parse = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
  const header = parse(rows[0]);
  const body = rows.slice(2).map(parse); // pula a linha separadora (---)
  const ncols = header.length;
  const colW = Math.floor(CONTENT_WIDTH / ncols);
  const widths = Array.from({ length: ncols }, (_, k) => (k === ncols - 1 ? CONTENT_WIDTH - colW * (ncols - 1) : colW));
  const border = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const mkCell = (txt, w, head) => new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    margins: { top: 60, bottom: 60, left: 120, right: 120 },
    shading: head ? { type: ShadingType.CLEAR, fill: "D5E8F0" } : undefined,
    children: [new Paragraph({ children: inlineRuns(txt, head ? { bold: true } : {}) })],
  });
  const trs = [new TableRow({ tableHeader: true, children: header.map((c, k) => mkCell(c, widths[k], true)) })];
  for (const r of body) trs.push(new TableRow({ children: header.map((_, k) => mkCell(r[k] || "", widths[k], false)) }));
  children.push(new Table({ width: { size: CONTENT_WIDTH, type: WidthType.DXA }, columnWidths: widths, rows: trs }));
  children.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
  return i;
}

function codeBlock(start) {
  let i = start + 1;
  const code = [];
  while (i < lines.length && !/^```/.test(lines[i])) { code.push(lines[i]); i++; }
  for (const cl of code) {
    children.push(new Paragraph({
      shading: { type: ShadingType.CLEAR, fill: "F3F4F6" },
      spacing: { before: 0, after: 0 },
      children: [new TextRun({ text: cl || " ", font: "Consolas", size: 18 })],
    }));
  }
  children.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
  return i + 1; // pula o ``` final
}

for (let i = 0; i < lines.length; ) {
  const line = lines[i];
  const t = line.trim();

  if (/^```/.test(t)) { i = codeBlock(i); prevWasNum = false; continue; }
  if (/^\s*\|.*\|\s*$/.test(line)) { i = tableBlock(i); prevWasNum = false; continue; }

  if (t === "---") {
    children.push(new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "999999", space: 1 } }, spacing: { after: 120 }, children: [] }));
    prevWasNum = false; i++; continue;
  }
  if (t === "") { i++; prevWasNum = false; continue; }

  let m;
  if ((m = t.match(/^(#{1,4})\s+(.*)$/))) {
    const lvl = m[1].length;
    const heading = [HeadingLevel.TITLE, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][lvl - 1];
    children.push(new Paragraph({ heading, children: inlineRuns(m[2]) }));
    prevWasNum = false; i++; continue;
  }
  if ((m = t.match(/^>\s?(.*)$/))) {
    children.push(new Paragraph({ indent: { left: 360 }, spacing: { after: 60 },
      border: { left: { style: BorderStyle.SINGLE, size: 12, color: "9CA3AF", space: 8 } },
      children: inlineRuns(m[1], { italic: true, color: "4B5563" }) }));
    prevWasNum = false; i++; continue;
  }
  if ((m = t.match(/^[-*]\s+(.*)$/))) {
    children.push(new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: inlineRuns(m[1]) }));
    prevWasNum = false; i++; continue;
  }
  if ((m = t.match(/^(\d+)\.\s+(.*)$/))) {
    if (!prevWasNum) { numBlock++; }
    const ref = "num" + numBlock;
    numRefsUsed.add(numBlock);
    children.push(new Paragraph({ numbering: { reference: ref, level: 0 }, children: inlineRuns(m[2]) }));
    prevWasNum = true; i++; continue;
  }
  // parágrafo normal
  children.push(new Paragraph({ spacing: { after: 100 }, children: inlineRuns(t) }));
  prevWasNum = false; i++;
}

// configs de numeração (uma por bloco numerado, p/ reiniciar em 1)
const numbering = { config: [
  { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 600, hanging: 280 } } } }] },
]};
for (const id of numRefsUsed) {
  numbering.config.push({ reference: "num" + id, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 600, hanging: 320 } } } }] });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 40, bold: true, color: "1F3864" }, paragraph: { spacing: { after: 240 } } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, color: "1F4E79" }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 25, bold: true, color: "2E75B6" }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, color: "2E75B6" }, paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering,
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUTPUT, buf); console.log("Gerado:", OUTPUT, buf.length, "bytes"); });
