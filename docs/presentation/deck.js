// MediSimplify review deck (13 slides), same minimal style as the FinWise deck. Usage:
//   node deck.js <out.pptx>            full deck
//   ONLY=7 node deck.js <out.pptx>     just slide 7 (for previews)
// Every number comes from evaluation/results/ or the test suite (see notes on each slide).
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("./apply_theme.js");

const OUT = process.argv[2];
const ONLY = process.env.ONLY ? Number(process.env.ONLY) : null;
const ASSETS = path.join(__dirname, "assets");

const THEME = {
  name: "MediSimplify Minimal",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1A1A1A", lt1: "FFFFFF", dk2: "1A1A1A", lt2: "F4F4F5",
    accent1: "0F766E", accent2: "A1A1AA", accent3: "D4D4D8", accent4: "B42318", accent5: "6B7280", accent6: "3F3F46",
    hlink: "0F766E", folHlink: "6B7280",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = "Richan Abraham J R, Sourav Ghosh";
pres.title = "MediSimplify – Project Review";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const INK = C.text1, MUTED = C.accent5, ACCENT = C.accent1;

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({ title: "PLAIN", background: { color: C.background1 }, objects: [] });
pres.defineSlideMaster({
  title: "CONTENT", background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.62, w: 8.8, h: 0.6, fontFace: THEME.headFontFace, fontSize: 28, bold: true, color: INK, align: "left", valign: "top", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 9.0, y: 5.15, w: 0.4, h: 0.25, fontSize: 9, color: MUTED, align: "right" },
});

// ------------------------------------------------------------------ helpers
const slides = [];
const add = (fn, notes) => slides.push({ fn, notes });
const txt = (s, text, o) => s.addText(text, { margin: 0, isTextBox: true, color: INK, fontSize: 14, valign: "top", ...o });
function content(s, title, label) {
  txt(s, label, { x: 0.6, y: 0.32, w: 6, h: 0.25, fontSize: 11, color: MUTED });
  s.addText(title, { placeholder: "title" });
}
const rule = (s, x, y, w) => s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: HEX.accent3, width: 0.75 } });
const vrule = (s, x, y, h) => s.addShape(pres.shapes.LINE, { x, y, w: 0, h, line: { color: HEX.accent3, width: 0.75 } });
function column(s, x, y, w, head, lines, o = {}) {
  txt(s, head, { x, y, w, h: 0.35, fontSize: 15, bold: true, color: o.headColor ?? INK });
  txt(s, lines.map((t, i) => ({ text: t, options: { breakLine: i < lines.length - 1 } })), { x, y: y + 0.45, w, h: o.h ?? 1.6, fontSize: o.size ?? 13, color: o.color ?? MUTED, paraSpaceAfter: 7 });
}
const figure = (s, n, label, x, y, w, color = ACCENT) => {
  txt(s, n, { x, y, w, h: 0.6, fontSize: 30, bold: true, color });
  txt(s, label, { x, y: y + 0.62, w, h: 0.5, fontSize: 12, color: MUTED });
};
const frame = (s, file, x, y, w, h) => {
  s.addImage({ path: path.join(ASSETS, file), x, y, w, h });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { type: "none" }, line: { color: HEX.accent3, width: 0.75 } });
};

// ================================================================== slides
// 1. Title
add(s => {
  s.addImage({ path: path.join(ASSETS, "logo.png"), x: 0.6, y: 0.5, w: 2.6, h: 0.43 });
  txt(s, "MediSimplify", { x: 0.6, y: 1.55, w: 8.8, h: 0.75, fontSize: 40, bold: true });
  txt(s, "Converting Medical Reports into Patient-Friendly Summaries Using Prompt Engineering and Retrieval-Augmented Generation", { x: 0.6, y: 2.35, w: 8.2, h: 0.85, fontSize: 18, color: C.accent6 });
  rule(s, 0.6, 3.55, 8.8);
  txt(s, [{ text: "Richan Abraham J R", options: { bold: true, breakLine: true } }, { text: "URK23CS1086", options: { color: MUTED } }], { x: 0.6, y: 3.75, w: 4, h: 0.6, fontSize: 13 });
  txt(s, [{ text: "Sourav Ghosh", options: { bold: true, breakLine: true } }, { text: "URK23CS1084", options: { color: MUTED } }], { x: 4.6, y: 3.75, w: 4.8, h: 0.6, fontSize: 13 });
  txt(s, "Mini Project · October 2026", { x: 0.6, y: 4.85, w: 8.8, h: 0.3, fontSize: 11, color: MUTED });
}, "Introduce both team members. One line: MediSimplify reads a PDF lab report, keeps every value exactly as printed, and explains each result in plain language using trusted, cited references, with safety checks before anything is shown.");

// 2. Problem
add(s => {
  content(s, "Lab reports are written for doctors, not patients", "Problem");
  txt(s, "Glucose, Fasting     128     H     mg/dL     70 - 99", { x: 0.6, y: 1.55, w: 8.8, h: 0.45, fontSize: 17, fontFace: "Courier New" });
  txt(s, "Is 128 bad? What does H mean? What is this test for?", { x: 0.6, y: 2.05, w: 8.8, h: 0.35, fontSize: 14, color: ACCENT });
  [["Medical jargon", "Test names and abbreviations mean little to most patients"], ["Flags and ranges", "Ranges differ by lab, age and layout; flags are easy to misread"], ["Unsafe shortcuts", "Generic chatbots can change values, diagnose or falsely reassure"]].forEach(([h, d], i) => {
    column(s, 0.6 + i * 3.0, 2.85, 2.6, h, [d], { h: 0.75 });
  });
  rule(s, 0.6, 4.05, 8.8);
  txt(s, "Goal: explain each result in plain language, keep every value exactly as printed, cite trusted sources and never diagnose.", { x: 0.6, y: 4.2, w: 8.8, h: 0.7, fontSize: 15 });
}, "A report line like this is clear to a doctor but not to a patient. The words are technical, the ranges vary by lab and age, and asking a generic chatbot is risky because it can change numbers, suggest a diagnosis or say everything is fine. Our goal is plain-language explanations that stay faithful to the report and to trusted sources.");

// 3. Objectives
add(s => {
  content(s, "Objectives", "Objectives and scope");
  const objs = ["Extract test results from PDFs exactly as printed", "Retrieve trusted background from a curated MedlinePlus library",
    "Compare zero-shot, few-shot and RAG-enhanced prompting", "Return structured, cited summaries as JSON",
    "Check every summary for changed values and unsafe wording", "Evaluate reproducibly on synthetic reports"];
  objs.forEach((t, i) => {
    const x = 0.6 + (i % 2) * 4.5, y = 1.55 + Math.floor(i / 2) * 0.85;
    txt(s, `0${i + 1}`, { x, y, w: 0.5, h: 0.4, fontSize: 16, bold: true, color: ACCENT });
    txt(s, t, { x: x + 0.55, y, w: 3.75, h: 0.7, fontSize: 14 });
  });
  rule(s, 0.6, 4.25, 8.8);
  txt(s, [{ text: "Scope  ", options: { bold: true } }, { text: "educational prototype · digitally generated PDFs · synthetic test data · not medical advice", options: { color: MUTED } }], { x: 0.6, y: 4.4, w: 8.8, h: 0.4, fontSize: 13 });
}, "Six objectives that map onto the pipeline: faithful extraction, trusted retrieval, three prompting strategies, structured output, safety validation and a reproducible evaluation. The scope is deliberately limited: an educational prototype tested on synthetic reports, not a diagnostic tool.");

// 4. Existing approaches
add(s => {
  content(s, "Why existing approaches fall short", "Existing approaches");
  const rows = [["Search engines", "Generic pages; the patient must match each result alone"], ["Generic AI chatbots", "Can alter values, invent facts, diagnose or falsely reassure"],
    ["Patient portals", "Show numbers and flags with little explanation"], ["Rule-based explainers", "Fixed text per test, no link to the actual report"], ["Fine-tuned medical models", "Need large labelled datasets and heavy compute"]];
  rows.forEach(([m, p], i) => {
    const y = 1.55 + i * 0.66;
    txt(s, m, { x: 0.6, y, w: 3.6, h: 0.5, fontSize: 15, bold: true, valign: "middle" });
    txt(s, p, { x: 4.4, y, w: 5.0, h: 0.5, fontSize: 14, color: MUTED, valign: "middle" });
    if (i < rows.length - 1) rule(s, 0.6, y + 0.58, 8.8);
  });
}, "Five common ways people try to understand a report, and the main gap in each. Search and portals leave the patient to connect the dots. General chatbots are fluent but can change values or make unsafe claims. Rule-based text ignores the actual report, and fine-tuned models need data and compute a student project does not have. MediSimplify combines a general model with retrieval and strict checks.");

// 5. How it works
add(s => {
  content(s, "How MediSimplify works", "Proposed methodology");
  const L = [["Extract", "Read the PDF; copy each test, value, unit and range exactly as printed"], ["Retrieve", "Find matching MedlinePlus passages with local embeddings and ChromaDB"],
    ["Explain", "Gemini writes a structured, cited summary from the facts and passages"], ["Check", "Validate values, citations and wording before showing the summary"]];
  L.forEach(([h, d], i) => {
    const x = 0.6 + i * 2.25;
    txt(s, `0${i + 1}`, { x, y: 1.6, w: 1, h: 0.5, fontSize: 26, bold: true, color: ACCENT });
    txt(s, h, { x, y: 2.2, w: 2.0, h: 0.35, fontSize: 16, bold: true });
    txt(s, d, { x, y: 2.65, w: 1.95, h: 1.3, fontSize: 13, color: MUTED });
  });
  rule(s, 0.6, 4.2, 8.8);
  txt(s, "Next.js web app · FastAPI backend · PyMuPDF · Sentence Transformers + ChromaDB · Gemini 3.5 Flash-Lite", { x: 0.6, y: 4.35, w: 8.8, h: 0.4, fontSize: 12, color: MUTED });
}, "Four stages. Extraction copies values verbatim and flags missing or conflicting data. Retrieval searches 20 public-domain MedlinePlus pages using test names only. Gemini returns JSON in a fixed schema with citation IDs. The validator checks the output against the report and the retrieved passages before the user sees it. Only structured test results are sent to the model, never names or report text.");

// 6. Prompting strategies
add(s => {
  content(s, "Three prompting strategies, compared fairly", "Prompt engineering");
  column(s, 0.6, 1.55, 2.7, "Zero-shot", ["Instructions only", "Rules: copy values, cite sources, never diagnose"], { h: 1.6 });
  vrule(s, 3.45, 1.6, 1.9);
  column(s, 3.65, 1.55, 2.7, "Few-shot", ["Instructions", "+ two reviewed example answers"], { h: 1.6 });
  vrule(s, 6.5, 1.6, 1.9);
  column(s, 6.7, 1.55, 2.7, "RAG-enhanced", ["Instructions and examples", "+ retrieved MedlinePlus passages to cite"], { h: 1.6, headColor: ACCENT });
  rule(s, 0.6, 3.95, 8.8);
  txt(s, "Same report facts, JSON schema, model and settings (temperature 0.2, seed 42), so only the prompt changes.", { x: 0.6, y: 4.1, w: 8.8, h: 0.7, fontSize: 15 });
}, "All three strategies share the same system instructions, report facts, output schema and generation settings, so differences come from the prompt alone. Few-shot adds two reviewed examples written from synthetic values. RAG adds the retrieved passages, which the model must cite by ID. Report text is wrapped in delimiters and treated as data, so instructions hidden in a report are ignored.");

// 7. Safety
add(s => {
  content(s, "Every summary is checked before it is shown", "Safety validation");
  [["Values", "Value, unit and range copied exactly; no invented tests"], ["Citations", "Every cited passage was actually retrieved"], ["Abnormal results", "Listed only if flagged or outside the printed range"],
    ["Language", "No diagnosis, treatment advice or false reassurance"], ["Privacy", "Only test results reach the model, never report text"]].forEach(([h, d], i) => {
    const y = 1.55 + i * 0.6;
    txt(s, h, { x: 0.6, y, w: 1.8, h: 0.4, fontSize: 14, bold: true, valign: "middle" });
    txt(s, d, { x: 2.45, y, w: 3.4, h: 0.4, fontSize: 13, color: MUTED, valign: "middle" });
  });
  vrule(s, 6.15, 1.6, 2.85);
  figure(s, "57 / 60", "reworded unsafe sentences caught on a held-out set (was 3)", 6.5, 1.5, 2.8);
  figure(s, "1 / 30", "safe sentences wrongly flagged", 6.5, 2.75, 2.8);
  figure(s, "Hidden", "a summary that fails is not shown as-is", 6.5, 3.85, 2.8, INK);
}, "The validator compares the summary with the extracted facts and the retrieved passages. A changed value, an invented test or a citation to a passage that was not retrieved fails the summary, and so does diagnostic, treatment or falsely reassuring language. We measured the language check on a held-out set of 90 sentences written before the rules were tuned: it now catches 57 of 60 unsafe sentences, up from 3, and flags 1 of 30 safe ones. Both sets were written by the same author, so this is likely optimistic.");

// 8. Results
add(s => {
  content(s, "Live results with Gemini", "Evaluation · 9 synthetic reports × 3 strategies");
  const labels = ["Zero-shot", "Few-shot", "RAG"];
  s.addChart(pres.charts.BAR, [
    { name: "Passed", labels, values: [0, 9, 4] },
    { name: "Passed with warnings", labels, values: [9, 0, 5] },
    { name: "Failed", labels, values: [0, 0, 0] },
  ], {
    x: 0.45, y: 1.4, w: 5.6, h: 3.55, barDir: "col", barGrouping: "stacked", chartColors: [HEX.accent1, HEX.accent3, HEX.accent4],
    showValue: true, dataLabelPosition: "ctr", dataLabelFontSize: 10, dataLabelFontFace: "+mn-lt", dataLabelColor: "1A1A1A", dataLabelFormatCode: "0;;;",
    valAxisMinVal: 0, valAxisMaxVal: 9, valAxisMajorUnit: 3, valAxisLabelFontSize: 10, valAxisLabelFontFace: "+mn-lt", valAxisLabelColor: HEX.accent5,
    catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", catAxisLabelColor: HEX.accent5,
    valAxisLineShow: false, catAxisLineShow: true, valGridLine: { color: "EEEEEE", size: 0.5 }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendFontSize: 10, legendFontFace: "+mn-lt", legendColor: HEX.accent5,
    showTitle: true, title: "Validation outcome per report", titleFontSize: 11, titleFontFace: "+mn-lt", titleColor: HEX.accent5,
  });
  vrule(s, 6.3, 1.5, 3.4);
  figure(s, "100%", "values, units and ranges copied exactly by every strategy", 6.6, 1.45, 2.8);
  figure(s, "1.0 → 0", "unsourced background sentences per test, zero-shot vs RAG", 6.6, 2.6, 2.8);
  figure(s, "95%", "of RAG citations point to the right reference page", 6.6, 3.75, 2.8);
}, "Live run with gemini-3.5-flash-lite on 9 synthetic reports. No strategy changed a value or used unsafe language. Zero-shot added unsourced background to almost every test, so all its summaries carry warnings. Few-shot passed every check, but mainly because it explains very little. RAG is the only strategy that explains what each test measures with cited MedlinePlus sources; its warnings come from citing a passage retrieved for a neighbouring test. One run, nine reports, so the differences are descriptive only.");

// 9. Strategy comparison (report-style table). Source: evaluation/results/2026-10-27-validator-v2/results.json
add(s => {
  content(s, "Zero-shot vs few-shot vs RAG", "Evaluation · strategy comparison");
  const cell = (text, o = {}) => ({
    text,
    options: {
      fontSize: 12, color: o.color ?? INK, bold: o.bold ?? false, align: o.align ?? "center", valign: "middle", margin: [0, 0.08, 0, 0.08], // inches (pptxgenjs reads values < 1 as inches)
      border: [{ type: "none" }, { type: "none" }, { type: "solid", color: HEX.accent3, pt: 0.75 }, { type: "none" }],
    },
  });
  const head = ["", "Zero-shot", "Few-shot", "RAG-enhanced"].map((t, i) =>
    cell(t, { bold: true, align: i ? "center" : "left", color: i === 3 ? ACCENT : INK }));
  const rows = [
    ["Checks: passed / warnings / failed", "0 / 9 / 0", "9 / 0 / 0", "4 / 5 / 0"],
    ["Values, units and ranges kept exact", "100%", "100%", "100%"],
    ["Abnormal results found", "19 of 19", "19 of 19", "18 of 19"],
    ["Explains what each test measures", "34 of 34, no source", "0 of 34", "30 of 34, cited"],
    ["Citations valid / on the right page", "–", "–", "100% / 95%"],
    ["Unsafe wording (diagnosis, advice)", "0", "0", "0"],
    ["Reading grade level", "9.1", "3.5", "6.9"],
    ["Average time · prompt tokens", "12.6 s · 925", "9.0 s · 2,428", "12.6 s · 4,702"],
  ].map(([label, ...vals]) => [cell(label, { align: "left", color: MUTED }), ...vals.map(v => cell(v))]);
  s.addTable([head, ...rows], { x: 0.6, y: 1.4, w: 8.8, colW: [3.4, 1.8, 1.8, 1.8], rowH: 0.36 });
  txt(s, "9 synthetic reports · 34 test explanations per strategy · gemini-3.5-flash-lite, temperature 0.2, seed 42 · one run",
    { x: 0.6, y: 4.85, w: 8.3, h: 0.25, fontSize: 10, color: MUTED });
}, "Same nine synthetic reports, same model and settings, only the prompt changes. All three kept every value, unit and range exact and used no unsafe wording. They differ in how much they explain and whether it is sourced: zero-shot added background to all 34 explanations without any source, few-shot added none, and RAG explained 30 of 34 with MedlinePlus citations, 95 percent of them on the right page. RAG missed one abnormal result, the low duplicate hemoglobin in the conflicting-values report. Reading grade is the Flesch-Kincaid level of the summary and explanations; few-shot is low mainly because its text is very short.");

// 10. Findings
add(s => {
  content(s, "What the comparison shows", "Evaluation · findings");
  column(s, 0.6, 1.55, 2.7, "Zero-shot: unsourced", ["Added background to all 34 explanations despite being told not to", "None of it cited; hardest to read (grade 9.1)"], { h: 1.9 });
  vrule(s, 3.45, 1.6, 2.1);
  column(s, 3.65, 1.55, 2.7, "Few-shot: safe but thin", ["Passed every check by copying the examples' style", "Restates values; explains no test"], { h: 1.9 });
  vrule(s, 6.5, 1.6, 2.1);
  column(s, 6.7, 1.55, 2.7, "RAG: most useful", ["Explained 30 of 34 tests with MedlinePlus citations", "95% on the right page; missed 1 of 19 abnormal results"], { h: 1.9, headColor: ACCENT });
  rule(s, 0.6, 4.05, 8.8);
  txt(s, [{ text: "Conclusion  ", options: { bold: true, color: ACCENT } }, { text: "RAG gives the most informative summaries with verifiable sources, at about 5× the prompt tokens of zero-shot. One run on nine reports: descriptive, not significant." }],
    { x: 0.6, y: 4.2, w: 8.8, h: 0.7, fontSize: 14 });
}, "Zero-shot ignored the instruction to leave out unsourced background, so every summary carries warnings. Few-shot looks best on the checks, but only because it copies the examples and explains almost nothing, so passing checks is not the same as being useful. RAG is the only strategy that explains what each test measures with sources a reader can verify. The cost is a longer prompt, about five times zero-shot, with similar response time. Human ratings are the next step to confirm which summaries readers find clearest.");

// 11. Built and tested
add(s => {
  content(s, "Built and tested", "Implementation");
  [["Frontend", "Next.js, TypeScript, Tailwind CSS"], ["Backend", "FastAPI, Pydantic, PyMuPDF"], ["Retrieval", "Sentence Transformers, ChromaDB, 20 MedlinePlus pages"],
    ["Language model", "Gemini 3.5 Flash-Lite with a JSON schema"], ["Evaluation", "Synthetic dataset, fault injection, replayable runs"]].forEach(([h, d], i) => {
    const y = 1.55 + i * 0.6;
    txt(s, h, { x: 0.6, y, w: 1.8, h: 0.4, fontSize: 14, bold: true, valign: "middle" });
    txt(s, d, { x: 2.45, y, w: 3.4, h: 0.4, fontSize: 13, color: MUTED, valign: "middle" });
  });
  vrule(s, 6.15, 1.6, 2.85);
  figure(s, "236", "backend tests passing", 6.5, 1.5, 2.8);
  figure(s, "16", "browser end-to-end tests", 6.5, 2.65, 2.8);
  figure(s, "29 / 30", "tests matched to the right reference page", 6.5, 3.8, 2.8);
}, "The full pipeline is implemented and public on GitHub. 236 backend tests cover extraction, retrieval, prompts, the validator, the Gemini error handling and the evaluation pipeline; 16 Playwright tests drive the web app in a real browser. On the evaluation set, extraction matched all 34 gold results exactly and retrieval picked the right MedlinePlus page for 29 of 30 covered tests.");

// 12. The app
add(s => {
  content(s, "The app", "Web application");
  frame(s, "home.png", 0.6, 1.45, 4.0, 4.0 / 2.07);
  txt(s, [{ text: "Upload a PDF or try a synthetic sample", options: { bold: true, breakLine: true } }, { text: "Processed in memory and never stored", options: { color: MUTED } }], { x: 0.6, y: 3.6, w: 4.0, h: 0.6, fontSize: 12 });
  frame(s, "results.png", 4.9, 1.45, 4.5, 4.5 / 1.311);
}, "Left: the home page, where you upload a PDF or load a synthetic sample. Right: the results view. The sidebar tracks each processing stage; the summary panel shows the chosen strategy, the validation result and each test explained with citation tags linking to MedlinePlus.");

// 13. Next steps
add(s => {
  txt(s, "Next steps", { x: 0.6, y: 0.62, w: 8.8, h: 0.6, fontSize: 28, bold: true });
  column(s, 0.6, 1.55, 2.7, "Done", ["Web app with live summaries", "RAG library and citations", "Safety validator and evaluation", "Public GitHub repository"], { h: 1.9, color: INK });
  vrule(s, 3.45, 1.6, 2.1);
  column(s, 3.65, 1.55, 2.7, "Limitations", ["No OCR for scanned reports", "Age-based ranges not compared", "Rule-based safety checks", "No human ratings yet"], { h: 1.9, color: INK });
  vrule(s, 6.5, 1.6, 2.1);
  column(s, 6.7, 1.55, 2.7, "Next", ["Human ratings of summaries", "Independent held-out safety set", "OCR and more report layouts", "Wider reference library"], { h: 1.9, color: INK });
  rule(s, 0.6, 4.05, 8.8);
  txt(s, "Thank you. Questions?", { x: 0.6, y: 4.25, w: 8.8, h: 0.6, fontSize: 24, bold: true, color: ACCENT });
}, "Summarize what is done, the honest limitations and what comes next, then invite questions.");

// ------------------------------------------------------------------ build
(async () => {
  slides.forEach(({ fn, notes }, i) => {
    if (ONLY && ONLY !== i + 1) return;
    const plain = i === 0 || i === slides.length - 1;
    const s = pres.addSlide({ masterName: plain ? "PLAIN" : "CONTENT" });
    fn(s);
    s.addNotes(notes);
  });
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT, ONLY ? `(slide ${ONLY})` : `(${slides.length} slides)`);
})();
