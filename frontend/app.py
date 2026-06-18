import os
import re
import html
import mimetypes
import sys
from pypdf import PdfReader
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from backend.retriever import LocalBilingualRetriever

mimetypes.add_type('text/javascript', '.mjs')
mimetypes.add_type('application/wasm', '.wasm')

app = Flask(__name__)
app.secret_key = 'dev'

FOLDER_PATH = os.path.join(PROJECT_ROOT, "source_docs")

retriever = LocalBilingualRetriever()


def highlight_query_terms(text: str, query: str) -> str:
    """Wraps query terms (3+ chars) found in text with <mark> tags. Returns escaped, safe HTML."""
    escaped_text = html.escape(text)
    words = [w.strip("?,.!-()\"'[]:;{}/*&^%$#@!+=") for w in query.split()]
    words = [w for w in words if len(w) >= 3]
    if not words:
        return escaped_text

    pattern = re.compile(r'\b(' + '|'.join(map(re.escape, words)) + r')\b', re.IGNORECASE)
    return pattern.sub(r'<mark>\1</mark>', escaped_text)


def clean_query_terms(query: str) -> list[str]:
    """Query words (3+ chars, punctuation stripped) used to drive preview scroll-to/highlight.
    Searching for these directly (rather than a phrase reconstructed from chunk text) avoids
    mismatches from PDF-extraction artifacts like hyphenated line-wraps or bullet characters."""
    terms = [w.strip("?,.!-()\"'[]:;{}/*&^%$#@!+=") for w in query.split()]
    return [t for t in terms if len(t) >= 3]


def extract_pdf_pages(path: str) -> list[str]:
    reader = PdfReader(path)
    return [page.extract_text() or "" for page in reader.pages]


def preview_kind_for(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return "pdf"
    return "text"


def rebuild_index():
    """Clears the collection and re-indexes every .txt/.pdf file in source_docs/."""
    retriever.clear_database()

    if not os.path.exists(FOLDER_PATH):
        os.makedirs(FOLDER_PATH)
        return False, f"Created folder '{FOLDER_PATH}'. Please put documents there."

    files = [f for f in os.listdir(FOLDER_PATH) if f.lower().endswith((".txt", ".pdf"))]
    if not files:
        sample_docs = {
            "demo_booby_traps.txt": (
                "BOOBY TRAP SAFETY PROCEDURES (JUNGLE OPS)\n\n"
                "1. Always scan for straight lines in nature. Trip wires are unnatural.\n"
                "2. When encountering a suspected explosive device: mark it, report it, and avoid it.\n"
                "3. Never pick up attractive items like radios, magazines, or food tins in active areas."
            ),
            "demo_haren_sv.txt": (
                "STRIDSPLAN: OPERATION HAREN\n\n"
                "1. Samöva skytteplutonerna i stridsmoment i kompanis ram.\n"
                "2. SIB (Strid i bebyggelse) kräver dubbla hörselskydd (kåpor och öronproppar).\n"
                "3. Skadade soldater ilastas skyndsamt i sjukvårdsfordon efter kamraträddning."
            )
        }
        for fname, content in sample_docs.items():
            with open(os.path.join(FOLDER_PATH, fname), "w", encoding="utf-8") as f:
                f.write(content)
        files = list(sample_docs.keys())

    indexed = 0
    skipped = 0
    for fname in files:
        fpath = os.path.join(FOLDER_PATH, fname)
        try:
            if preview_kind_for(fname) == "pdf":
                pages = extract_pdf_pages(fpath)
                added_any = False
                for page_number, page_text in enumerate(pages, start=1):
                    if page_text.strip():
                        retriever.chunk_and_add_document(page_text, fname, extra_metadata={"page": page_number})
                        added_any = True
                if added_any:
                    indexed += 1
                else:
                    skipped += 1
            else:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

                if not text.strip():
                    skipped += 1
                    continue

                retriever.chunk_and_add_document(text, fname)
                indexed += 1
        except Exception:
            skipped += 1

    message = f"Successfully indexed {indexed} document(s)!"
    if skipped:
        message += f" Skipped {skipped} file(s) that couldn't be read."
    return True, message


@app.route('/')
def index():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        hits = retriever.retrieve(q, limit=5)
        for hit in hits:
            results.append({
                "filename": hit["source"],
                "excerpt": highlight_query_terms(hit["text"], q),
                "confidence": hit["confidence"],
                "page": hit["metadata"].get("page"),
            })

    preview_filename = request.args.get('preview', '').strip()
    is_safe_filename = preview_filename and os.path.basename(preview_filename) == preview_filename
    if not is_safe_filename or not os.path.isfile(os.path.join(FOLDER_PATH, preview_filename)):
        preview_filename = None

    preview_kind = preview_kind_for(preview_filename) if preview_filename else None
    preview_query_terms = clean_query_terms(q) if preview_filename else []
    raw_page = request.args.get('page', '').strip()
    preview_page = raw_page if preview_filename and raw_page.isdigit() else None

    return render_template(
        'index.html',
        q=q,
        results=results,
        preview_filename=preview_filename,
        preview_kind=preview_kind,
        preview_query_terms=preview_query_terms,
        preview_page=preview_page,
    )


@app.route('/rebuild', methods=['POST'])
def rebuild():
    _, message = rebuild_index()
    flash(message)
    return redirect(url_for('index'))


@app.route('/file/<path:filename>')
def serve_file(filename):
    as_attachment = request.args.get('download') == '1'
    return send_from_directory(FOLDER_PATH, filename, as_attachment=as_attachment)


if __name__ == '__main__':
    app.run(debug=True)
