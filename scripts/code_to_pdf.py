#!/usr/bin/env python3
"""Convert source code files into readable, print-ready PDFs."""
from __future__ import annotations
import argparse, html, re, sys
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, TableStyle, Spacer, LongTable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Bundle fonts so output does not depend on the host machine's installed fonts.
FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
FONT_NAMES = {"regular": "Helvetica", "bold": "Helvetica-Bold", "mono": "Courier", "mono_bold": "Courier-Bold"}
try:
    if all((FONT_DIR / name).exists() for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf")):
        pdfmetrics.registerFont(TTFont("CodePDFSans", str(FONT_DIR / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("CodePDFSans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("CodePDFMono", str(FONT_DIR / "DejaVuSansMono.ttf")))
        pdfmetrics.registerFont(TTFont("CodePDFMono-Bold", str(FONT_DIR / "DejaVuSansMono-Bold.ttf")))
        FONT_NAMES = {"regular": "CodePDFSans", "bold": "CodePDFSans-Bold", "mono": "CodePDFMono", "mono_bold": "CodePDFMono-Bold"}
except Exception:
    # Keep the converter usable if a font file is missing or cannot be loaded.
    pass
try:
    from pygments import lex
    from pygments.lexers import get_lexer_for_filename, TextLexer
    from pygments.token import Token
    HAVE_PYGMENTS = True
except ImportError:
    HAVE_PYGMENTS = False

# High-contrast, print-friendly syntax palette.
# Restrained, high-contrast palette inspired by premium editorial/product design.
PALETTE = {
    "comment":"#657184", "keyword":"#7C3AED", "string":"#087F5B",
    "number":"#B45309", "function":"#155EEF", "class":"#0E7490",
    "decorator":"#9333EA", "constant":"#9A3412", "builtin":"#BE123C",
    "attribute":"#0F766E", "variable":"#334155", "identifier":"#25324B",
    "operator":"#475569", "punctuation":"#64748B", "plain":"#172033"
}
PANEL = colors.HexColor("#F7F8FA")
BORDER = colors.HexColor("#E0E4EA")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#667085")
ACCENT = colors.HexColor("#1769E0")

def category(t):
    # Test the most specific semantic token families before broad token types.
    tests = [
        (Token.Comment, "comment"),
        (Token.Keyword, "keyword"),
        (Token.Literal.String, "string"),
        (Token.Literal.Number, "number"),
        (Token.Name.Function, "function"),
        (Token.Name.Class, "class"),
        (Token.Name.Decorator, "decorator"),
        (Token.Name.Constant, "constant"),
        (Token.Name.Builtin, "builtin"),
        (Token.Name.Attribute, "attribute"),
        (Token.Name.Variable, "variable"),
        (Token.Operator, "operator"),
        (Token.Punctuation, "punctuation"),
    ]
    for test, name in tests:
        if t in test:
            return name
    # Many lexers classify identifiers simply as Name; use a readable ink color.
    if t in Token.Name:
        return "identifier"
    return "plain"

def lexer_for(path):
    if not HAVE_PYGMENTS: return None
    try: return get_lexer_for_filename(path.name, stripnl=False, ensurenl=False)
    except Exception: return TextLexer(stripnl=False, ensurenl=False)

def tokenized_lines(text, lexer):
    if not lexer: return [[(None, line)] for line in text.splitlines()]
    result=[[]]
    for t,v in lex(text, lexer):
        for piece in v.splitlines(keepends=True):
            if piece.endswith("\r\n"): body=piece[:-2]; newline=True
            elif piece.endswith(("\n","\r")): body=piece[:-1]; newline=True
            else: body=piece; newline=False
            if body: result[-1].append((t,body))
            if newline: result.append([])
    if text.endswith(("\n","\r")) and result and not result[-1]: result.pop()
    return result or [[]]

def emphasize_function_calls(lines):
    """Mark ordinary identifiers followed by '(' as function calls for display.

    This is a presentation-only refinement of Pygments tokens; it never changes
    the source text. Keywords and already-classified functions are left intact.
    """
    if not HAVE_PYGMENTS:
        return lines
    result=[]
    for line in lines:
        updated=list(line)
        for i,(tok,value) in enumerate(line):
            if tok != Token.Name or not value.strip():
                continue
            j=i+1
            while j < len(line) and line[j][1].isspace():
                j += 1
            if j < len(line) and line[j][0] in Token.Punctuation and line[j][1].lstrip().startswith("("):
                updated[i]=(Token.Name.Function,value)
        result.append(updated)
    return result


def markup_tokens(tokens):
    out=[]
    for t,v in tokens:
        cat=category(t) if t is not None else "plain"
        col=PALETTE[cat]
        # Emphasize structural tokens without relying on color alone.
        face=FONT_NAMES["mono_bold"] if cat in {"keyword", "function", "class", "builtin", "decorator"} else FONT_NAMES["mono"]
        # Keep code literal; use non-breaking spaces so indentation remains stable.
        s=html.escape(v, quote=False).replace(" ","&#160;").replace("\t","&#160;&#160;&#160;&#160;")
        out.append(f'<font name="{face}" color="{col}">{s}</font>')
    return "".join(out) or "&#160;"

def split_tokens_for_width(tokens, max_chars):
    """Split one physical source line into visual chunks without dropping characters."""
    chars=[]
    for token, value in tokens:
        chars.extend((token, ch) for ch in value)
    if len(chars) <= max_chars:
        return [tokens]
    chunks=[]
    while chars:
        if len(chars) <= max_chars:
            take=len(chars)
        else:
            # Prefer a whitespace boundary to avoid breaking identifiers and literals.
            low=max(1, max_chars // 2)
            candidates=[i+1 for i in range(low, min(max_chars, len(chars))) if chars[i][1].isspace()]
            take=candidates[-1] if candidates else max_chars
        part=chars[:take]
        chars=chars[take:]
        grouped=[]
        for token,ch in part:
            if grouped and grouped[-1][0] == token:
                grouped[-1]=(token,grouped[-1][1]+ch)
            else:
                grouped.append((token,ch))
        chunks.append(grouped)
    return chunks


def find_output_block(lines):
    """Find an explicitly marked output section in block or line-comment form.

    Supported forms:
      C-style: /*
                 Output:
                 ...
               */
      Line comments: # Output: / // Output: / -- Output: / % Output:
                     # ... (same comment prefix)
                     # End Output

    Line-comment forms require an explicit End Output marker to avoid mistaking
    ordinary comments for output or deleting following source code.
    Returns (start_index, label_index, end_index, kind).
    """
    # First support closed C-family block comments, including C/C++, Java, JS,
    # C#, Go, Rust, PHP and CSS-style comments.
    for label_i, line in enumerate(lines):
        if not re.match(r"^\s*(?:\*\s*)?Output\s*:\s*$", line, re.I):
            continue
        comment_start = None
        for j in range(label_i, -1, -1):
            if "/*" in lines[j]:
                comment_start = j
                break
            if "*/" in lines[j]:
                break
        if comment_start is not None:
            for k in range(label_i + 1, len(lines)):
                if "*/" in lines[k]:
                    return (comment_start, label_i, k, "block")

    # Support languages whose normal comments are line-based (Python, shell,
    # Ruby, SQL, R, MATLAB, etc.). Explicit End Output is required.
    for label_i, line in enumerate(lines):
        match = re.match(r"^\s*(#|//|--|%|;|REM)\s*Output\s*:\s*$", line, re.I)
        if not match:
            continue
        prefix = match.group(1)
        for end_i in range(label_i + 1, len(lines)):
            end_match = re.match(r"^\s*(#|//|--|%|;|REM)\s*End\s+Output\s*$", lines[end_i], re.I)
            if end_match and end_match.group(1).lower() == prefix.lower():
                # Only accept a contiguous run of comments between markers.
                middle = lines[label_i + 1:end_i]
                escaped_prefix = re.escape(prefix)
                if all(not x.strip() or re.match(rf"^\s*{escaped_prefix}\s?.*$", x, re.I) for x in middle):
                    return (label_i, label_i, end_i, "line:" + prefix)
                break
            if lines[end_i].strip() and not re.match(rf"^\s*{re.escape(prefix)}\s?.*$", lines[end_i], re.I):
                break
    return None

def clean_output_line(line, kind="block"):
    value=line.strip()
    if kind == "block":
        if value.startswith("*"):
            value=value[1:].lstrip()
        return value
    prefix = kind.split(":", 1)[1]
    return re.sub(r"^" + re.escape(prefix) + r"\s?", "", value, count=1, flags=re.I)

def output_display_lines(lines,block):
    _,label_i,end_i,kind=block
    transcript=[clean_output_line(x,kind) for x in lines[label_i+1:end_i]]
    while transcript and not transcript[0]: transcript.pop(0)
    while transcript and not transcript[-1]: transcript.pop()
    return transcript

def wrap_transcript_line(line, max_chars):
    """Wrap long terminal lines at spaces and visibly indent continuation lines."""
    if len(line) <= max_chars:
        return [line]
    parts=[]
    remaining=line
    while len(remaining) > max_chars:
        cut=remaining.rfind(" ", max(1, max_chars // 2), max_chars + 1)
        if cut <= 0:
            cut=max_chars
        else:
            cut += 1  # keep the break-space in the previous visual segment
        parts.append(remaining[:cut])
        remaining=remaining[cut:]
    parts.append(remaining)
    return [parts[0]] + ["    " + part for part in parts[1:]]


def styles(font_size):
    return {
      "title":ParagraphStyle("title",fontName=FONT_NAMES["bold"],fontSize=22,leading=26,textColor=INK,spaceAfter=1),
      "section":ParagraphStyle("section",fontName=FONT_NAMES["bold"],fontSize=10.5,leading=13,textColor=INK,spaceBefore=8,spaceAfter=5,keepWithNext=True),
      "num":ParagraphStyle("num",fontName=FONT_NAMES["mono"],fontSize=max(7.5,font_size-1),leading=font_size+3,textColor=colors.HexColor("#667085"),alignment=2),
      # Negative first-line indent keeps the first visual line aligned while wrapped continuations hang inward.
      "code":ParagraphStyle("code",fontName=FONT_NAMES["mono"],fontSize=font_size,leading=font_size+3.4,wordWrap="CJK",splitLongWords=True,spaceAfter=0,spaceBefore=0),
      "blankcode":ParagraphStyle("blankcode",fontName=FONT_NAMES["mono"],fontSize=1,leading=font_size+1,spaceAfter=0,spaceBefore=0),
      "blanknum":ParagraphStyle("blanknum",fontName=FONT_NAMES["mono"],fontSize=1,leading=font_size+1,textColor=colors.HexColor("#8A94A6"),alignment=2),
      "output":ParagraphStyle("output",fontName=FONT_NAMES["mono"],fontSize=font_size,leading=font_size+3.4,textColor=INK,wordWrap="CJK",splitLongWords=True,leftIndent=0,spaceAfter=1),
    }

class CodeDoc(BaseDocTemplate):
    def __init__(self,*args,footer_label="",running_title="",**kwargs):
        self.footer_label=footer_label
        self.running_title=running_title
        super().__init__(*args,**kwargs)

def decorate(canvas,doc):
    canvas.saveState(); w,h=doc.pagesize
    canvas.setStrokeColor(BORDER); canvas.setLineWidth(.55)
    canvas.line(doc.leftMargin,11*mm,w-doc.rightMargin,11*mm)
    canvas.setFont(FONT_NAMES["regular"],7.5); canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin,7.3*mm,doc.footer_label[:100])
    canvas.drawRightString(w-doc.rightMargin,7.3*mm,f"{doc.page}")
    # Multi-page documents get a quiet running title so loose pages remain identifiable.
    if doc.page > 1 and doc.running_title:
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT_NAMES["bold"],7.5)
        canvas.drawString(doc.leftMargin,h-8*mm,doc.running_title[:110])
        canvas.setFont(FONT_NAMES["regular"],7)
        canvas.drawRightString(w-doc.rightMargin,h-8*mm,"CONTINUED")
        canvas.setStrokeColor(BORDER)
        canvas.line(doc.leftMargin,h-10*mm,w-doc.rightMargin,h-10*mm)
    canvas.restoreState()

def descriptive_title(path, source):
    """Create a useful, content-led title without changing the source."""
    text = source.lower()
    rules = [
        (r"fibonacci|fibrecursive|fibiterative", "Fibonacci Series: Recursive & Iterative Methods"),
        (r"binary.?search", "Binary Search Algorithm"),
        (r"merge.?sort|mergesort", "Merge Sort Algorithm"),
        (r"quick.?sort|quicksort", "Quick Sort Algorithm"),
        (r"breadth.?first|\bbfs\b", "Breadth-First Search (BFS)"),
        (r"depth.?first|\bdfs\b", "Depth-First Search (DFS)"),
        (r"knapsack", "Knapsack Problem: Dynamic Programming"),
        (r"n.?queens|nqueens", "N-Queens Problem"),
        (r"linked.?list", "Linked List Operations"),
        (r"factorial", "Factorial: Recursive & Iterative Methods"),
        (r"prime number|isprime|primecheck", "Prime Number Check"),
        (r"palindrome", "Palindrome Check"),
        (r"stack", "Stack Operations"),
        (r"queue", "Queue Operations"),
        (r"infix|postfix|prefix", "Expression Conversion & Evaluation"),
        (r"linear.?search", "Linear Search Algorithm"),
        (r"selection.?sort", "Selection Sort Algorithm"),
        (r"insertion.?sort", "Insertion Sort Algorithm"),
        (r"bubble.?sort", "Bubble Sort Algorithm"),
        (r"heap.?sort|heapsort", "Heap Sort Algorithm"),
        (r"kruskal", "Kruskal’s Minimum Spanning Tree Algorithm"),
        (r"prim.?s.?algorithm|prim\s*\(", "Prim’s Minimum Spanning Tree Algorithm"),
        (r"bellman.?ford", "Bellman–Ford Shortest Path Algorithm"),
        (r"floyd.?warshall", "Floyd–Warshall All-Pairs Shortest Paths"),
        (r"topological.?sort|toposort", "Topological Sorting Algorithm"),
        (r"course.?schedule", "Course Schedule: Graph Traversal"),
        (r"longest.?common.?subsequence|\blcs\b", "Longest Common Subsequence (LCS)"),
        (r"edit.?distance", "Edit Distance Using Dynamic Programming"),
        (r"coin.?change", "Coin Change: Dynamic Programming"),
        (r"subset.?sum", "Subset Sum Problem"),
        (r"knight.?tour", "Knight’s Tour Problem"),
        (r"hamiltonian", "Hamiltonian Cycle Problem"),
        (r"travelling.?salesman|traveling.?salesman|\btsp\b", "Travelling Salesman Problem"),
        (r"gcd|greatest.?common.?divisor", "Greatest Common Divisor (GCD)"),
        (r"lcm|least.?common.?multiple", "Least Common Multiple (LCM)"),
        (r"doubly.?linked.?list", "Doubly Linked List Operations"),
        (r"circular.?linked.?list", "Circular Linked List Operations"),
        (r"binary.?tree", "Binary Tree Operations"),
        (r"bst|binary.?search.?tree", "Binary Search Tree Operations"),
        (r"graph", "Graph Algorithms and Traversal"),
        (r"dijkstra", "Dijkstra’s Shortest Path Algorithm"),
    ]
    for pattern, title in rules:
        if re.search(pattern, text, re.I): return title
    # Prefer a concise first meaningful comment when it looks like a topic label.
    for line in source.splitlines()[:30]:
        m = re.match(r"\s*//\s*(.{4,72})\s*$", line)
        if m:
            candidate = m.group(1).strip(" .:-")
            if candidate and not re.search(r"(method|implementation|code|program)\s*$", candidate, re.I):
                return candidate[:1].upper() + candidate[1:]
    stem = re.sub(r"[_-]+", " ", path.stem).strip()
    stem = re.sub(r"\b(pr|program|file)\s*\d+\b", "", stem, flags=re.I).strip()
    return stem.title() if stem else "Source Code Practical"

def header(path,mode,doc,st,source):
    """Minimal editorial title; omit the redundant language/mode banner."""
    title_text = descriptive_title(path, source) if mode == "handout" else path.name
    if not source.strip() and mode == "handout":
        title_text = f"{path.stem.replace('_', ' ').replace('-', ' ').title()} — Empty Source File"
    title=Paragraph(html.escape(title_text),st["title"])
    return [title,Spacer(1,8)]


def normalize_shell_command(line):
    """Remove machine-specific prompts and simplify common PowerShell wrappers."""
    prompt=re.match(r"^\s*(PS\s+.+?>|[A-Za-z]:\\[^>]*>|(?:\$|>)\s+)(.*)$",line)
    command=prompt.group(2).strip() if prompt else line.strip()
    # VS Code PowerShell commonly records: cd "path" ; if ($?) { build } ; if ($?) { run }.
    # In a handout, show the useful build/run commands rather than the user's local path
    # and shell's conditional scaffolding. This is presentation-only; the source is untouched.
    blocks=re.findall(r"\{\s*([^{}]+?)\s*\}",command)
    if blocks and re.search(r"\bif\s*\(\s*\$\?\s*\)",command):
        cleaned=[]
        for block in blocks:
            block=block.strip()
            if re.match(r"^(?:cd|Set-Location)\b",block,re.I):
                continue
            if block:
                cleaned.append(block)
        if cleaned:
            return cleaned
    # Strip a leading directory-change command when followed by a separator and a useful command.
    command=re.sub(r'^\s*(?:cd|Set-Location)\s+"[^"]*"\s*(?:;|&&)\s*', '', command, flags=re.I)
    return [command] if command else []

def split_command_output(transcript):
    """Separate recognizable shell-prompt commands from program transcript lines."""
    commands=[]
    output=[]
    prompt=re.compile(r"^\s*(?:PS\s+.+?>|[A-Za-z]:\\[^>]*>|(?:\$|>)\s+)")
    for line in transcript:
        if prompt.match(line):
            commands.extend(normalize_shell_command(line))
        else:
            output.append(line)
    while output and not output[0].strip(): output.pop(0)
    while output and not output[-1].strip(): output.pop()
    return commands,output


def terminal_panel(lines,doc,st,font_size,accent=False):
    paras=[]
    output_width=max(28,int((doc.width-25*mm)/(font_size*0.602)))
    for line in lines:
        for visual_line in wrap_transcript_line(line,output_width):
            escaped=html.escape(visual_line,quote=False).replace(" ","&#160;").replace("\t","&#160;&#160;&#160;&#160;")
            paras.append(Paragraph(escaped or "&#160;",st["output"]))
    if not paras:
        paras=[Paragraph("(No transcript text found.)",st["output"])]
    # One paragraph per row allows long transcripts to split safely across pages.
    # A single cell containing a very tall list of paragraphs can be unsplittable.
    panel=LongTable([[para] for para in paras],colWidths=[doc.width],hAlign="LEFT",splitByRow=1)
    panel.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F6F7F9")),
      ("BOX",(0,0),(-1,-1),.6,BORDER),
      ("LINEBEFORE",(0,0),(0,-1),2.2,ACCENT if accent else colors.HexColor("#AAB4C3")),
      ("LEFTPADDING",(0,0),(-1,-1),9),("RIGHTPADDING",(0,0),(-1,-1),8),
      ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),("VALIGN",(0,0),(-1,-1),"TOP")]))
    return panel

def create_pdf(path,output,mode="exact",line_numbers=True,landscape_mode=False,font_size=9.5,hide_local_paths=False):
    raw=path.read_text(encoding="utf-8-sig",errors="replace")
    display_raw=raw.expandtabs(4)
    lines=display_raw.splitlines()
    block=find_output_block(lines) if mode=="handout" else None
    pagesize=landscape(A4) if landscape_mode else A4
    margin=14*mm
    pdf_title = descriptive_title(path, raw) if mode == "handout" else path.name
    if not raw.strip() and mode == "handout":
        pdf_title = f"{path.stem.replace('_', ' ').replace('-', ' ').title()} — Empty Source File"
    doc=CodeDoc(str(output),pagesize=pagesize,leftMargin=margin,rightMargin=margin,topMargin=13*mm,bottomMargin=16*mm,
                title=pdf_title,author="Code-to-PDF Converter",subject=f"Source code practical: {path.name}",
                footer_label=path.name,running_title=pdf_title)
    frame=Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id="main",leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="main",frames=frame,onPage=decorate)])
    st=styles(font_size); lexer=lexer_for(path); tok_lines=tokenized_lines(display_raw,lexer)
    tok_lines=emphasize_function_calls(tok_lines)
    while len(tok_lines)<len(lines): tok_lines.append([])
    story=header(path,mode,doc,st,raw)
    if block:
        comment_start,label_i,end_i,block_kind=block
        # Remove only the marked output comment from the handout presentation.
        # Keep any source code that follows it, and retain original line numbers.
        source_range=[i for i in range(len(lines)) if not (comment_start <= i <= end_i)]
        transcript=output_display_lines(lines,block)
    else:
        source_range=range(len(lines)); transcript=None
    rows=[]
    continuation_rows=set()
    # Estimate a safe character width for the chosen page, font and gutter.
    gutter_width = 9*mm if line_numbers else 0
    max_chars=max(24,int((doc.width-gutter_width-15*mm)/(font_size*0.602)))
    for idx in source_range:
        blank=not lines[idx].strip()
        compact=(mode=="handout" and blank)
        original_tokens=tok_lines[idx] if idx<len(tok_lines) else []
        chunks=[[]] if compact else split_tokens_for_width(original_tokens,max_chars)
        if not chunks: chunks=[[]]
        for chunk_index,chunk in enumerate(chunks):
            code=Paragraph("&#160;" if compact else markup_tokens(chunk),st["blankcode"] if compact else st["code"])
            if line_numbers:
                if compact or chunk_index > 0:
                    num=Paragraph("&#160;",st["blanknum"])
                else:
                    num=Paragraph(str(idx+1),st["num"])
                rows.append([num,code])
            else:
                rows.append([code])
            if chunk_index > 0:
                continuation_rows.add(len(rows)-1)
    if rows:
        if line_numbers:
            code_table=LongTable(rows,colWidths=[9*mm,None],hAlign="LEFT",repeatRows=0,splitByRow=1)
            code_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),PANEL),("BOX",(0,0),(-1,-1),.55,BORDER),
              ("LINEBEFORE",(1,0),(1,-1),.45,BORDER),("VALIGN",(0,0),(-1,-1),"TOP"),
              ("LEFTPADDING",(0,0),(0,-1),5),("RIGHTPADDING",(0,0),(0,-1),5),
              ("LEFTPADDING",(1,0),(1,-1),7),("RIGHTPADDING",(1,0),(1,-1),6),
              ("TOPPADDING",(0,0),(-1,-1),1.5),("BOTTOMPADDING",(0,0),(-1,-1),1.5)]))
            for ri in continuation_rows:
                code_table.setStyle(TableStyle([("LEFTPADDING",(1,ri),(1,ri),17)]))
        else:
            code_table=LongTable(rows,colWidths=[doc.width],hAlign="LEFT",splitByRow=1)
            code_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),PANEL),("BOX",(0,0),(-1,-1),.55,BORDER),
              ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
              ("TOPPADDING",(0,0),(-1,-1),1.5),("BOTTOMPADDING",(0,0),(-1,-1),1.5)]))
            for ri in continuation_rows:
                code_table.setStyle(TableStyle([("LEFTPADDING",(0,ri),(0,ri),18)]))
        story.append(code_table)
    if transcript is not None:
        commands,program_output=split_command_output(transcript)
        if commands:
            story.extend([Spacer(1,7),Paragraph("Build &amp; run",st["section"])])
            safe_commands=[]
            for line in commands:
                if hide_local_paths:
                    line=re.sub(r"[A-Za-z]:\\Users\\[^\\\s>]+",r"%USERPROFILE%",line,flags=re.I)
                safe_commands.append(line)
            story.append(terminal_panel(safe_commands,doc,st,font_size,accent=False))
        if program_output:
            story.extend([Spacer(1,6),Paragraph("Program output" if commands else "Sample output",st["section"])])
            safe_output=[]
            for line in program_output:
                if hide_local_paths:
                    line=re.sub(r"[A-Za-z]:\\Users\\[^\\\s>]+",r"%USERPROFILE%",line,flags=re.I)
                safe_output.append(line)
            story.append(terminal_panel(safe_output,doc,st,font_size,accent=True))
        if not commands and not program_output:
            story.extend([Spacer(1,7),Paragraph("Sample output",st["section"]),terminal_panel([],doc,st,font_size,accent=True)])
    output.parent.mkdir(parents=True,exist_ok=True)
    doc.build(story)

def main():
    p=argparse.ArgumentParser(description="Convert source code to readable, print-ready PDFs.")
    p.add_argument("files",nargs="+")
    p.add_argument("--output-dir",default="pdf_output")
    p.add_argument("--combine",action="store_true")
    p.add_argument("--mode",choices=["exact","handout"],default="exact")
    p.add_argument("--no-line-numbers",action="store_true")
    p.add_argument("--landscape",action="store_true")
    p.add_argument("--font-size",type=float,default=9.5)
    p.add_argument("--hide-local-paths",action="store_true",help="In handout mode only, replace local Windows user path prefixes in transcript lines.")
    args=p.parse_args()
    if args.font_size<7.5 or args.font_size>12: p.error("--font-size must be between 7.5 and 12 pt")
    paths=[Path(x).expanduser().resolve() for x in args.files]
    for path in paths:
        if not path.is_file(): print(f"ERROR: file not found: {path}",file=sys.stderr); return 2
    outdir=Path(args.output_dir).resolve(); outdir.mkdir(parents=True,exist_ok=True)
    if args.combine:
        try: from pypdf import PdfReader,PdfWriter
        except ImportError: print("ERROR: --combine requires pypdf. Install pypdf and retry.",file=sys.stderr); return 2
        import tempfile
        out=outdir/"combined_code.pdf"; writer=PdfWriter()
        with tempfile.TemporaryDirectory() as td:
            for i,path in enumerate(paths):
                tmp=Path(td)/f"{i}.pdf"
                create_pdf(path,tmp,args.mode,not args.no_line_numbers,args.landscape,args.font_size,args.hide_local_paths)
                for page in PdfReader(str(tmp)).pages: writer.add_page(page)
        with open(out,"wb") as f: writer.write(f)
        print(out)
    else:
        raw_stems=[re.sub(r"[^\w.\- ]+","_",path.stem).strip(" .") or "source_code" for path in paths]
        stem_counts={stem:raw_stems.count(stem) for stem in set(raw_stems)}
        used_names=set()
        for path,stem in zip(paths,raw_stems):
            name=stem
            if stem_counts[stem] > 1:
                parent=re.sub(r"[^\w.\- ]+","_",path.parent.name).strip(" .") or "folder"
                name=f"{stem}_{parent}"
            candidate=name
            counter=2
            while candidate.casefold() in used_names:
                candidate=f"{name}_{counter}"
                counter+=1
            used_names.add(candidate.casefold())
            out=outdir/(candidate+".pdf")
            create_pdf(path,out,args.mode,not args.no_line_numbers,args.landscape,args.font_size,args.hide_local_paths)
            print(out)
    if not HAVE_PYGMENTS: print("WARNING: Pygments unavailable; used plain text.",file=sys.stderr)
    return 0
if __name__=="__main__": raise SystemExit(main())
