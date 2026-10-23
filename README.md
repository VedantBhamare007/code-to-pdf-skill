# Code-to-PDF

A platform-independent Python utility for turning source files into readable, print-ready PDFs, with reusable guidance for AI coding assistants in `SKILL.md`. Pygments highlights supported languages; unknown extensions use plain text. The layout includes line numbers, wrapped long lines, and page numbers.

## Requirements

- Python 3.10 or newer
- Dependencies listed in `requirements.txt`

Install them from the project folder:

```bash
python -m pip install -r requirements.txt
```

## Use with an AI coding assistant

Assistants that support skills or custom project instructions can use `SKILL.md` as the workflow guide. Follow that platform's instructions for adding a skill, and keep `SKILL.md`, `scripts/`, `fonts/`, and `requirements.txt` together. If the assistant does not support skills, ask it to follow `SKILL.md` and run the Python commands below.

The assistant needs access to Python and the dependencies listed above. If it cannot load skills, provide `SKILL.md` as instructions or use the converter directly.

## Use as a Python utility

Convert a source file to a PDF in `pdf_output/`:

```bash
python scripts/code_to_pdf.py example.py
```

Create a practical handout, convert several files, or combine them into one PDF:

```bash
python scripts/code_to_pdf.py --mode handout example.py
python scripts/code_to_pdf.py --mode handout first.py second.cpp app.js
python scripts/code_to_pdf.py --combine --mode handout first.py second.cpp
```

Useful options:

```bash
python scripts/code_to_pdf.py --output-dir ./documents example.py
python scripts/code_to_pdf.py --landscape wide_table.sql
python scripts/code_to_pdf.py --font-size 10 example.cpp
python scripts/code_to_pdf.py --no-line-numbers example.js
python scripts/code_to_pdf.py --mode handout --hide-local-paths example.py
```

Exact mode is the default and renders the complete source listing. Handout mode uses a topic-led title and can move a marked sample output block into a separate section. The converter does not run the source program, so any included output must be supplied in the source file.

## Mark sample output in handout mode

For block-comment languages, put `Output:` inside a closed `/* ... */` comment:

```cpp
/*
Output:
Hello, world!
*/
```

For line-comment languages, use matching comment prefixes and close the block with `End Output`:

```python
# Output:
# Hello, world!
# End Output
```

Supported line-comment prefixes include `#`, `//`, `--`, `%`, `;`, and `REM`. Recognized terminal prompts may be separated into build/run commands and program output; this detection is heuristic.

## Notes

- Long source lines wrap, and PDFs may use as many pages as needed.
- Bundled DejaVu fonts support many common characters, but not every script or emoji.
- `--hide-local-paths` replaces some Windows user-path prefixes in handout transcripts; review PDFs for private information before sharing.
- PDF text is searchable and selectable. PDFs are not tagged for PDF/UA accessibility compliance.

## Tests

Run the regression suite:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs this suite on pushes and pull requests.

## Project files

```text
code-to-pdf-skill/
├── .github/workflows/tests.yml
├── .gitignore
├── LICENSE
├── README.md
├── SKILL.md
├── requirements.txt
├── scripts/code_to_pdf.py
├── tests/test_converter.py
└── fonts/
    ├── DejaVuSans.ttf
    ├── DejaVuSans-Bold.ttf
    ├── DejaVuSansMono.ttf
    ├── DejaVuSansMono-Bold.ttf
    └── LICENSE-DejaVu.txt
```

The project is licensed under MIT; see `LICENSE`. The bundled fonts have separate terms in `fonts/LICENSE-DejaVu.txt`.
