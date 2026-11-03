"""arXiv LaTeX source (the e-print archive) to Markdown; `tabular` cells keep their exact text."""
from __future__ import annotations

import gzip
import io
import re
import tarfile

from evidence.sources import markdown_table

MAX_BYTES = 60 * 1024 * 1024
HEADINGS = {"section": "##", "subsection": "###", "subsubsection": "####", "paragraph": "####"}
TABULAR = re.compile(r"\\begin\{(tabular\*?|tabularx)\}(.*?)\\end\{\1\}", re.S)
RULES = re.compile(r"\\(hline|toprule|midrule|bottomrule|cline\{[^}]*\})")
WRAPPERS = r"\\(?:textbf|textit|emph|textrm|texttt|textsc|underline|mathbf|mathrm|text)\s*\{([^{}]*)\}"


def read_files(blob: bytes) -> dict[str, str]:
    """The .tex files of an e-print download: a gzipped tar, a gzipped single file or a plain file.
    ValueError when nothing in it looks like LaTeX."""
    if len(blob) > MAX_BYTES:
        raise ValueError("source archive too large")
    files: dict[str, str] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tar:
            for m in tar.getmembers():
                if m.isfile() and m.name.endswith(".tex") and m.size <= MAX_BYTES:
                    f = tar.extractfile(m)
                    if f is not None:
                        files[m.name.removeprefix("./")] = f.read().decode("utf-8", "replace")
    except tarfile.TarError:
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(blob)) as gz:
                raw = gz.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("source too large once decompressed")
        except OSError:
            raw = blob
        text = raw.decode("utf-8", "replace")
        if "\\begin{document}" in text:
            files["main.tex"] = text
    if not files:
        raise ValueError("no LaTeX source in the download")
    return files


def _main(files: dict[str, str]) -> str:
    mains = [n for n, t in files.items() if "\\begin{document}" in t]
    if not mains:
        raise ValueError("no main .tex file (no \\begin{document})")
    return max(mains, key=lambda n: len(files[n]))


def _inline(text: str) -> str:
    """Text with LaTeX wrappers removed: \\textbf{x} -> x, \\% -> %, $^{*}$ -> *, \\cite{..} dropped."""
    text = re.sub(r"\\(cite[a-z]*|label|ref|eqref|autoref)\{[^}]*\}", "", text)
    text = re.sub(r"\$\^\{?([^}$]*)\}?\$", r"\1", text)
    for _ in range(4):
        text = re.sub(WRAPPERS, r"\1", text)
    text = text.replace("$", "").replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("\\#", "#")
    text = re.sub(r"\\(?:,|;|!|quad|qquad)", " ", text).replace("~", " ")
    return " ".join(text.replace("{", "").replace("}", "").split())


def _cell(cell: str) -> tuple[str, int]:
    """(text, how many columns the cell spans)."""
    cell = cell.strip()
    span = 1
    m = re.match(r"\\multicolumn\{(\d+)\}\{[^}]*\}\{(.*)\}\s*$", cell, re.S)
    if m:
        span, cell = int(m.group(1)), m.group(2)
    cell = re.sub(r"^\\multirow\{[^}]*\}\{[^}]*\}\{(.*)\}\s*$", r"\1", cell, flags=re.S)
    return _inline(cell), span


def tabular_rows(body: str) -> list[list[str]]:
    """The rows of a tabular body (after `\\begin{tabular}`): the column spec is skipped, rules dropped."""
    body = body.strip()
    if body.startswith("{"):   # the column spec, one balanced group
        depth = 0
        for i, ch in enumerate(body):
            depth += (ch == "{") - (ch == "}")
            if depth == 0:
                body = body[i + 1:]
                break
    body = RULES.sub("", body)
    rows: list[list[str]] = []
    for raw in re.split(r"(?<!\\)\\\\(?:\[[^\]]*\])?", body):
        if not raw.strip():
            continue
        row: list[str] = []
        for cell in re.split(r"(?<!\\)&", raw):
            text, span = _cell(cell)
            row.extend([text, *[""] * (span - 1)])
        rows.append(row)
    return rows


def _expand(text: str, files: dict[str, str], depth: int = 0) -> str:
    def sub(m: re.Match) -> str:
        name = m.group(2).strip()
        for cand in (name, name + ".tex"):
            for key, body in files.items():
                if key == cand or key.endswith("/" + cand):
                    return _expand(body, files, depth + 1) if depth < 8 else ""
        return ""

    return re.sub(r"\\(input|include)\{([^}]*)\}", sub, text)


def latex_markdown(blob: bytes) -> str:
    """Markdown of an arXiv e-print download. ValueError when it holds no usable LaTeX."""
    files = read_files(blob)
    text = _expand(files[_main(files)], files)
    text = re.sub(r"(?<!\\)%.*", "", text)
    title = re.search(r"\\title\{([^{}]*)\}", text)
    body = text.split("\\begin{document}", 1)[1].split("\\end{document}", 1)[0]
    tables: list[str] = []

    def stash(m: re.Match) -> str:
        tables.append(markdown_table(tabular_rows(m.group(2))))
        return f"\n\nTABLE{len(tables) - 1}ENDTABLE\n\n"

    body = TABULAR.sub(stash, body)
    body = re.sub(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", lambda m: f"\n\nCAPTION {_inline(m.group(1))}\n\n", body)
    body = re.sub(r"\\(section|subsection|subsubsection|paragraph)\*?\{([^{}]*)\}",
                  lambda m: f"\n\nHEAD{HEADINGS[m.group(1)]} {_inline(m.group(2))}\n\n", body)
    body = re.sub(r"\\(begin|end)\{(table\*?|figure\*?|center|abstract|document)\}(\[[^\]]*\])?", "\n\n", body)
    body = re.sub(r"\\(centering|small|footnotesize|maketitle)\b|\\title\{[^{}]*\}", "", body)
    out = [f"# {_inline(title.group(1))}"] if title else []
    for para in re.split(r"\n\s*\n", body):
        if not para.strip():
            continue
        p = para.strip()
        if m := re.fullmatch(r"TABLE(\d+)ENDTABLE", p):
            out.append(tables[int(m.group(1))])
        elif p.startswith("CAPTION "):
            out.append(f"**{p[8:]}**")
        elif p.startswith("HEAD"):
            out.append(p[4:])
        elif p := _inline(p):
            out.append(p)
    result = "\n\n".join(out).strip() + "\n"
    if len(result.strip()) < 50:
        raise ValueError("the LaTeX converted to almost no text")
    return result
