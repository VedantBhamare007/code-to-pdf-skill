---
name: code-to-pdf
description: Convert source-code files and programming practicals in many languages into readable PDFs with optional sample-output sections.
---

# Code-to-PDF

Create readable PDFs from source code using the bundled converter at `scripts/code_to_pdf.py`. Resolve that path relative to this `SKILL.md`, not the user's working directory.

## Choose a mode

- Use `exact` (default) when the PDF should show the complete source listing.
- Use `handout` for student practicals. It can infer a topic title and separate a clearly marked output block.
- Use `--combine` only when one PDF for multiple inputs is requested.

## Output blocks

In handout mode, separate a marked output block from the displayed source. Keep source before and after the block, and retain original line numbers.

- Block-comment languages: put `Output:` inside a closed `/* ... */` comment.
- Line-comment languages: comment `Output:`, every transcript line, and a final `End Output` line with the same prefix. Supported prefixes: `#`, `//`, `--`, `%`, `;`, and `REM`.
- Recognizable terminal prompts may be split into build/run commands and program output. Treat this as heuristic; ambiguous formats may remain together.

If no supported marker is found, render the source normally. Never guess missing output or claim that a supplied transcript matches the program.

## Rendering

- Use Pygments lexers when available and plain text otherwise.
- Default to A4 portrait and 9.5 pt code. Landscape is useful for wide source; font size can be set from 7.5 to 12 pt.
- Preserve indentation and source ordering. Wrap long lines without dropping characters; continuation rows should be visibly indented.
- Keep content legible across as many pages as needed. Use line numbers, a restrained syntax palette, a light code panel, and quiet page footers.
- Use bundled DejaVu fonts when available and fall back gracefully if fonts cannot load.
- Give the PDF a useful title and avoid overwriting outputs in batch mode with duplicate basenames.

## Privacy and limitations

`--hide-local-paths` masks some Windows user-path prefixes in handout transcripts. It is not a secret scanner. Unicode coverage depends on available font glyphs, and PDFs are not tagged for PDF/UA accessibility.

## Workflow

1. Identify each input file and use its extension for syntax highlighting.
2. Choose the mode and output location requested by the user.
3. Generate the requested PDF or PDFs.
4. Confirm each PDF exists and is non-empty. When tools permit, extract text and render pages to inspect layout, line numbering, output separation, and page breaks.
5. After converter changes, run `python -m unittest discover -s tests -v`.
6. Report checks performed and limitations accurately; do not claim visual inspection unless it was performed.

## Commands

```bash
python scripts/code_to_pdf.py example.py
python scripts/code_to_pdf.py --mode handout example.py
python scripts/code_to_pdf.py --mode handout --hide-local-paths example.py
python scripts/code_to_pdf.py --mode handout example.py other.cpp app.js
python scripts/code_to_pdf.py --combine --mode handout example.py other.cpp
python scripts/code_to_pdf.py --mode handout --landscape wide.sql
python scripts/code_to_pdf.py --mode handout --font-size 10 example.cpp
```
