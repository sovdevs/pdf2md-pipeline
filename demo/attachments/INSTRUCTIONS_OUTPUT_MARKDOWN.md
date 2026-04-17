# Instructions for producing Markdown files from PDFs (regulatory / planning documents)

*Italian version: [ISTRUZIONI_OUTPUT_MARKDOWN.md](ISTRUZIONI_OUTPUT_MARKDOWN.md)*

This document describes **what to deliver** and **how** the text must be structured, without requiring knowledge of any downstream system. The goal is a file that is **faithful to the PDF**, **well ordered**, and **reusable** for archiving, lookup by articles and paragraphs, searchable tables, and correct citations.

---

## 1. Purpose of the work

- Convert the **official PDF** (or certified copy) into one or more **Markdown** files (`.md`).
- **Do not** summarise or paraphrase the legal text: the content must match the source document, except for obvious typos if explicitly agreed.
- Markdown makes the text **structured** (headings, lists, tables) so it can be indexed, searched by section, and linked to legal references reliably.

---

## 2. File format

| Aspect | Rule |
|--------|------|
| Encoding | **UTF-8** |
| Extension | `.md` |
| File name | Avoid odd characters; prefer `Body_Type_Year_part.md` (e.g. `MunicipalityX_NTA_2025_part1.md`) |
| One instrument per file | One PDF = one `.md`, unless otherwise agreed (e.g. separate volumes with clear names) |

---

## 3. YAML front matter (required header)

At the beginning of the file, before the body, insert a block between two `---` lines with **YAML** metadata:

- **Required (minimum):**
  - `titolo` (or `title`): official title as on the cover / header
  - `ente` or `comune`: issuing administration or body (e.g. municipality name)
  - `tipo`: type of instrument (e.g. NTA, building code, council resolution, determination)
  - `anno`: main year of the instrument (four digits)

- **Recommended if present on the PDF:**
  - `jurisdiction`: full territorial label (e.g. “Municipality of …”)
  - `riferimento_approvazione`: resolution, determination, regional decision, number and date
  - `data_adozione` / `data_approvazione`: human-readable date (e.g. 2025-03-15)
  - `url`: only if it is an official URL or a database URL specified by the client

Example structure (fields adapted to the actual instrument):

```yaml
---
titolo: Official title of the instrument
comune: MUNICIPALITY NAME
tipo: NTA
anno: 2025
jurisdiction: Municipality of NAME
---
```

Immediately after the second `---`, the document’s **main title** as a `# Title...` line (see section 4).

---

## 4. Heading hierarchy (Markdown)

- Use only Markdown heading lines: `#`, `##`, `###`, `####`.
- **Logical order:** do not skip levels (after `#` use `##`, then `###`, etc.).
- Align headings with the **table of contents / structure** of the instrument (Titles, Chapters, Articles, Annexes).
- The top-level heading (`#`) must appear **once** as the document title (after the front matter).

---

## 5. Articles, paragraphs, lists

- Keep **numbering and letters** as in the PDF (Art. 12, paragraph 3, `1)`, `a)`).
- Do not invent articles or paragraphs missing from the source.
- Break paragraphs for readability; avoid uninterrupted walls of text where the PDF structure is clear.
- For bullet lists use `- `; for numbered lists use `1.` `2.` only if consistent with the original.

---

## 6. Tables

Tables must use **pipe** syntax (GitHub Flavored Markdown compatible):

- First row: column headers.
- Second row: separator with `|---|` (at least as many segments as columns).
- Each following row: one logical row of the table.

**Merged cells or complex layout in the PDF:**

- Repeat the “parent” cell value on subsequent rows, or
- Add an **explicit note** below the table, e.g. `*Note: in the PDF rows X–Y were merged / the table continued on page N.*`

If the table **cannot** be reconstructed reliably:

- Use a **structured list** or a **monospaced block** (indented with four spaces or wrapped in ` ``` ` lines) with hand-aligned columns, plus a note explaining the compromise.

---

## 7. Images and figures

- Export images from the PDF into a **dedicated subfolder** (e.g. `instrument_name_images/`) next to the `.md` or as agreed with the client.
- In Markdown use **paths relative** to the `.md` file, e.g. `![Short caption](instrument_name_images/page12_fig3.png)`.
- Below the image, if the PDF has a **caption**, copy it as a normal paragraph.
- If the image is unreadable or decorative only, state it, e.g. `*Figure present in PDF; text not extractable.*`

---

## 8. Do (summary)

- Preserve order and numbering of the official text.
- Include complete YAML front matter for required fields.
- Use `#` / `##` / `###` headings consistent with the instrument’s structure.
- Use pipe tables where possible; add notes when the PDF does not map 1:1.
- Extract images, use relative links, include captions.
- Flag **unreadable** pages or doubtful spots (list at end of file or HTML comment `<!-- ... -->` if the client allows).

---

## 9. Don’t (common PDF extraction mistakes)

- **False headings:** do not put `##` on a line that is not a heading in the PDF (e.g. splitting a sentence so “… Commission for” + next line “Landscape.” become two headings).
- **Page numbers** in the body as headings (`## 6`, `## 7`): remove from normal flow or move to a note if they must be tracked.
- **Repeated** page headers (logo, “Regulation…”, repeated title) on every page: in Markdown consolidate to **one** header or add a note “repeated boilerplate omitted”.
- **Glued text** without spaces between words from automatic extraction: fix spacing (Italian or local language rules as appropriate).
- **Replacing** legal text with paraphrase or summary: not allowed unless under a separate written mandate.

*(Historical outputs with these flaws may exist in internal archives: they are not the model to follow.)*

---

## 10. Delivery checklist

Before sending the work, verify:

- [ ] File is UTF-8 with a clear file name.
- [ ] Initial YAML block includes at least `titolo`, `ente`/`comune`, `tipo`, `anno`.
- [ ] One main `#` title after the front matter.
- [ ] Heading hierarchy `#` → `##` → `###` without arbitrary skips.
- [ ] **At least 3 pages** spot-checked (start, one page with table or list, end) against the PDF.
- [ ] Each table: consistent rows; notes if there were merged cells or breaks.
- [ ] Each image: file present, working relative path, caption if any.
- [ ] List of **unreadable pages** or items left as TODO.

---

## 11. Example files in this folder

In the same folder as this document you will find two **reference examples** (municipal instruments already derived from PDFs and considered suitable as models):

| File | What to notice |
|------|------------------|
| `NTA_PdR_PdS_MarianoComense_2025_primaparte.md` | YAML front matter, `#` / `##` / `###` / `####` hierarchy, articles, definitions, lists. |
| `tabella_oneri_costo_2026.md` | `##` sections, pipe tables, explanatory text and notes around tables. |

Use these files as **visual and structural references**, not as text to edit: the content is for illustration only.

---

## 12. Operational contacts

Any questions about priorities (absolute fidelity vs readability), allowed extraction tools, or delivery format (zip, folder layout) should be raised with the **client** before working on long documents or low-quality scans.
