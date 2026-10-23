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

1. Identify each input file, keep its exact name and path, and use its extension for syntax highlighting. Quote paths that contain spaces.
2. Choose exact or handout mode and the output location requested by the user. The default output folder is `pdf_output/`.
3. Generate one PDF per input (normally `<input-name>.pdf`; duplicate basenames receive a disambiguating suffix), or `combined_code.pdf` when `--combine` is requested. Explain the output location in your response.
4. Confirm each PDF exists and is non-empty. When tools permit, extract text and render pages to inspect layout, line numbering, output separation, and page breaks.
5. After converter changes, run `python -m unittest discover -s tests -v`.
6. Report checks performed and limitations accurately; do not claim visual inspection unless it was performed.

## Usage examples

Run commands from the repository root. Replace the example filenames with the actual input paths. Relative paths use the current folder; quote paths that contain spaces.

Exact mode is the default and creates `pdf_output/example.pdf`:

```powershell
python scripts/code_to_pdf.py example.py
```

Create a handout PDF in a chosen folder:

```powershell
python scripts/code_to_pdf.py --mode handout --output-dir ./pdf_output example.py
```

Convert several files to separate PDFs. This creates `first.pdf`, `second.pdf`, and `app.pdf` in `pdf_output`:

```powershell
python scripts/code_to_pdf.py --mode handout --output-dir ./pdf_output first.py second.cpp app.js
```

Combine those inputs into `pdf_output/combined_code.pdf`:

```powershell
python scripts/code_to_pdf.py --combine --mode handout --output-dir ./pdf_output first.py second.cpp app.js
```

A clear request to an AI assistant is: “Use the Code-to-PDF skill to create separate handout PDFs for `first.py` and `second.cpp` in the `pdf_output` folder.”
