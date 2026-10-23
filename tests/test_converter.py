"""Regression tests for content preservation and common PDF layout failures."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "code_to_pdf.py"

class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.out = self.root / "out"
        self.out.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def convert(self, name, content, mode="handout", extra=()):
        source = self.root / name
        source.write_text(content, encoding="utf-8")
        cmd = [sys.executable, str(SCRIPT), "--mode", mode, "--output-dir", str(self.out), *extra, str(source)]
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
        pdf = self.out / f"{source.stem}.pdf"
        self.assertTrue(pdf.exists() and pdf.stat().st_size > 1000)
        with pdf.open("rb") as handle:
            reader = PdfReader(handle)
            pages = list(reader.pages)
            text = "\n".join(page.extract_text() or "" for page in pages)
        self.assertTrue(text.strip(), "PDF should contain selectable text")
        return pdf, text, len(pages)

    def test_output_block_does_not_delete_code_after_it(self):
        src = '#include <iostream>\nint main(){return 0;}\n/*\nOutput:\nHello\n*/\nint helper(){return 42;}\n'
        _, text, _ = self.convert("after.cpp", src)
        self.assertIn("Sample output", text)
        self.assertIn("Hello", text)
        self.assertIn("int helper()", text)
        self.assertIn("42", text)

    def test_unicode_is_embedded_and_extractable(self):
        src = '// café naïve π → “quotes”\nint main(){ return 0; }\n'
        _, text, _ = self.convert("unicode.cpp", src)
        for word in ("café", "naïve", "π", "→", "quotes"):
            self.assertIn(word, text)

    def test_long_lines_are_not_truncated(self):
        ending = "END_OF_LONG_STRING_SENTINEL"
        src = 'int main(){ const char* value = "' + ("verylongword" * 15) + ending + '"; return 0; }\n'
        _, text, _ = self.convert("long.cpp", src)
        self.assertIn(ending, "".join(text.split()))

    def test_no_output_marker_keeps_all_source(self):
        src = 'int main(){ return 0; }\n// normal comment\n'
        _, text, _ = self.convert("normal.cpp", src)
        self.assertIn("normal comment", text)
        self.assertNotIn("Sample output", text)

    def test_exact_mode_preserves_output_comment(self):
        src = 'int main(){ return 0; }\n/*\nOutput:\nactual output\n*/\n'
        _, text, _ = self.convert("exact.cpp", src, mode="exact")
        self.assertIn("Output:", text)
        self.assertIn("actual output", text)

    def test_multipage_source_has_running_header_and_footer(self):
        src = "\n".join(f"int value_{i} = {i};" for i in range(120))
        _, text, pages = self.convert("many.cpp", src)
        self.assertGreater(pages, 1)
        self.assertIn("CONTINUED", text)
        self.assertIn("value_119", text)


    def test_shell_command_and_program_output_have_separate_sections(self):
        src = r'''int main(){return 0;}
/*
Output:
PS C:\Users\student\project> g++ main.cpp -o main ; .\main
Hello from program
Value: 42
*/
'''
        _, text, _ = self.convert("command_split.cpp", src)
        self.assertIn("Build & run", text)
        self.assertIn("Program output", text)
        self.assertIn("g++ main.cpp", text)
        self.assertIn("Hello from program", text)
        self.assertIn("Value: 42", text)

    def test_descriptive_title_is_present_without_redundant_banner(self):
        src = "#include <iostream>\nint main(){ int n=5; return n; }\n"
        _, text, _ = self.convert("factorial.cpp", src)
        self.assertIn("Factorial", text)
        self.assertNotIn("PRACTICAL HANDOUT", text)
        self.assertNotIn("CPP SOURCE CODE", text)

    def test_command_path_redaction_is_handout_only(self):
        src = r'''int main(){return 0;}
/*
Output:
PS C:\Users\student\project> .\main
Saved to C:\Users\student\report.txt
ok
*/
'''
        _, handout, _ = self.convert("private.cpp", src, extra=("--hide-local-paths",))
        self.assertIn("%USERPROFILE%", handout)
        self.assertNotIn("C:\\Users\\student", handout)
        _, exact, _ = self.convert("private_exact.cpp", src, mode="exact", extra=("--hide-local-paths",))
        self.assertIn("C:\\Users\\student", exact)

    def test_crlf_and_tabs_are_preserved_as_visible_indentation(self):
        src = "int main() {\r\n\treturn 0;\r\n}\r\n"
        _, text, _ = self.convert("tabs.cpp", src)
        self.assertIn("return 0", text)
        self.assertIn("int main", text)


    def test_batch_duplicate_basenames_do_not_overwrite_each_other(self):
        first_dir=self.root / "alpha"
        second_dir=self.root / "beta"
        first_dir.mkdir(); second_dir.mkdir()
        first=first_dir / "main.cpp"; second=second_dir / "main.cpp"
        first.write_text("int alpha(){return 1;}\n", encoding="utf-8")
        second.write_text("int beta(){return 2;}\n", encoding="utf-8")
        cmd=[sys.executable,str(SCRIPT),"--output-dir",str(self.out),str(first),str(second)]
        subprocess.run(cmd,check=True,capture_output=True,text=True)
        pdfs=sorted(self.out.glob("*.pdf"))
        self.assertEqual(len(pdfs),2)
        extracted=[]
        for pdf in pdfs:
            with pdf.open("rb") as handle:
                extracted.extend(page.extract_text() or "" for page in PdfReader(handle).pages)
        combined_text="\n".join(extracted)
        self.assertIn("alpha",combined_text)
        self.assertIn("beta",combined_text)


    def test_long_output_transcript_splits_across_pages(self):
        lines="\n".join(f"output-line-{i:03d}: value={i}" for i in range(220))
        src="int main(){return 0;}\n/*\nOutput:\n"+lines+"\n*/\n"
        _, text, pages = self.convert("long_output.cpp", src)
        self.assertGreater(pages, 1)
        self.assertIn("output-line-000", text)
        self.assertIn("output-line-219", text)

    def test_python_line_comment_output_block_is_separated(self):
        src = "def main():\n    print('hello')\n\n# Output:\n# hello\n# value: 42\n# End Output\n\ndef helper():\n    return 7\n"
        _, text, _ = self.convert("example.py", src)
        self.assertIn("Sample output", text)
        self.assertIn("hello", text)
        self.assertIn("value: 42", text)
        self.assertIn("def helper", text)
        self.assertNotIn("End Output", text)

    def test_generates_pdf_only_and_does_not_modify_source(self):
        source = self.root / "copy_me.py"
        payload = b"# Output:\r\n# hello\r\n# End Output\r\nprint('hi')\r\n"
        source.write_bytes(payload)
        cmd = [sys.executable, str(SCRIPT), "--mode", "handout", "--output-dir", str(self.out), str(source)]
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
        self.assertTrue((self.out / "copy_me.pdf").exists())
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["copy_me.pdf"])
        self.assertEqual(source.read_bytes(), payload)

    def test_metadata_banner_is_removed(self):
        _, text, _ = self.convert("sample.py", "print('hello')\n")
        self.assertNotIn("PRACTICAL HANDOUT", text)
        self.assertNotIn("EXACT SOURCE", text)

    def test_empty_source_still_generates_pdf(self):
        _, text, pages = self.convert("empty.cpp", "")
        self.assertIn("Empty Source File", text)
        self.assertEqual(pages, 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
