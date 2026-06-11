import os
import html
import re
import streamlit as st
from retriever import LocalBilingualRetriever

# =============================================================================
# 1. UI Page Setup
# =============================================================================
st.set_page_config(
    page_title="Local Hybrid Search",
    page_icon="🔍",
    layout="wide"
)

# Custom premium styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap');
    
    /* Global Fonts */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3, .app-title {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Premium Header */
    .app-title-container {
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(135deg, #4285F4 0%, #34A853 50%, #FBBC05 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Result Card Styles */
    .result-card {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    }
    .result-card:hover {
        transform: translateY(-2px);
        border-color: rgba(66, 133, 244, 0.4);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    }
    .result-header {
        font-size: 0.85rem;
        color: #888888;
        margin-bottom: 0.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .result-badge {
        background-color: rgba(66, 133, 244, 0.15);
        color: #4285F4;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .result-snippet {
        font-size: 0.95rem;
        color: #dddddd;
        line-height: 1.6;
        margin-bottom: 1rem;
    }
    
    /* Document Viewer Styles */
    .viewer-container {
        background-color: rgba(0, 0, 0, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.5rem;
        height: 600px;
        overflow-y: auto;
    }
    .viewer-content {
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.9rem;
        line-height: 1.6;
        color: #cccccc;
        white-space: pre-wrap;
    }
    .viewer-placeholder {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 400px;
        color: #666666;
        text-align: center;
        border: 2px dashed rgba(255, 255, 255, 0.05);
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# 2. Text Highlighting Helper
# =============================================================================
def highlight_query_terms(text: str, query: str) -> str:
    """Highlights terms from the search query inside the text using HTML <mark> tags."""
    if not query:
        return html.escape(text)
        
    # Extract terms (words with 3 or more characters)
    raw_words = query.split()
    words = []
    for w in raw_words:
        cleaned = w.strip("?,.!-()\"'[]:;{}/*&^%$#@!+=")
        if len(cleaned) >= 3:
            words.append(cleaned)
            
    escaped_text = html.escape(text)
    if not words:
        return escaped_text
        
    # Build a regex matching any of the query terms on word boundaries
    try:
        pattern = re.compile(r'\b(' + '|'.join(map(re.escape, words)) + r')\b', re.IGNORECASE)
        # Wrap matching words in styled mark tags
        highlighted = pattern.sub(
            r'<mark style="background-color: rgba(252, 229, 136, 0.95); color: #111111; border-radius: 3px; padding: 1px 3px; font-weight: 500;">\1</mark>',
            escaped_text
        )
        return highlighted
    except Exception:
        return escaped_text


# =============================================================================
# 3. Initialization & State Management
# =============================================================================
FOLDER_PATH = "./source_docs"

@st.cache_resource
def get_retriever():
    """Initializes and returns the LocalBilingualRetriever (cached)."""
    return LocalBilingualRetriever()

retriever = get_retriever()

# Initialize session state keys
if "selected_document" not in st.session_state:
    st.session_state.selected_document = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "results" not in st.session_state:
    st.session_state.results = []
if "has_searched" not in st.session_state:
    st.session_state.has_searched = False


# =============================================================================
# 4. Ingestion / Rebuilding Logic
# =============================================================================
def rebuild_database():
    """Clears ChromaDB and reads/embeds all documents in source_docs."""
    retriever.clear_database()
    
    if not os.path.exists(FOLDER_PATH):
        os.makedirs(FOLDER_PATH)
        return False, f"Created folder '{FOLDER_PATH}'. Please put documents there."
        
    files = [f for f in os.listdir(FOLDER_PATH) if f.endswith(".txt")]
    if not files:
        # Auto-create sample documents if folder is completely empty
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

    # Index each document
    progress_bar = st.sidebar.progress(0.0)
    for idx, fname in enumerate(files):
        fpath = os.path.join(FOLDER_PATH, fname)
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        retriever.chunk_and_add_document(text, fname)
        progress_bar.progress((idx + 1) / len(files))
        
    progress_bar.empty()
    return True, f"Successfully indexed {len(files)} document(s)!"


# =============================================================================
# 5. Sidebar Layout & Database Utilities
# =============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/nolan/128/binoculars.png", width=80)
    st.markdown("<h2 style='margin-top:0;'>Edmond Admin</h2>", unsafe_allow_html=True)
    st.markdown("Local Hybrid Search (English & Swedish)")
    st.divider()
    
    # Database Status Details
    is_empty = retriever.is_empty()
    total_chunks = 0 if is_empty else retriever.collection.count()
    unique_sources = {meta.get("source_document") for meta in retriever.indexed_metadatas if meta and "source_document" in meta}
    
    st.markdown("**📁 Database Statistics**")
    st.write(f"- Collection Count: `{total_chunks} chunks`")
    st.write(f"- Indexed Files: `{len(unique_sources)} files`")
    st.write(f"- Model: `E5-Small (Multilingual)`")
    st.write(f"- Mode: `Dense Vector + BM25 Hybrid`")
    
    st.divider()
    
    # Ingestion Controls
    st.markdown("**🛠️ Data Management**")
    if st.button("🔄 Rebuild Database Index", use_container_width=True):
        with st.spinner("Clearing and re-indexing source documents..."):
            success, msg = rebuild_database()
            if success:
                st.success(msg)
                # Re-sync local lists
                retriever._rebuild_keyword_index()
                st.rerun()
            else:
                st.warning(msg)
                
    st.caption("Clears database memory and reads all `.txt` documents from `./source_docs` folder.")


# =============================================================================
# 6. Main Application Layout
# =============================================================================

# Title
st.markdown("<div class='app-title-container'><h1 style='font-size: 3rem; margin-bottom: 0;'>Edmond</h1><p style='color:#aaaaaa; font-size:1.1rem; margin-top:0.5rem;'>Bilingual Semantic & Keyword Search Engine</p></div>", unsafe_allow_html=True)

# Search Bar Form
with st.form(key="search_form", clear_on_submit=False):
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        query_input = st.text_input(
            label="Search input",
            value=st.session_state.search_query,
            placeholder="Type search terms or semantic questions (e.g. 'stridsutrustning' or 'trip wire')...",
            label_visibility="collapsed"
        )
    with col_btn:
        submit_btn = st.form_submit_button(label="Search", use_container_width=True)

# Trigger Search
if submit_btn and query_input.strip():
    st.session_state.search_query = query_input
    with st.spinner("Executing hybrid vector & semantic retrieval..."):
        st.session_state.results = retriever.retrieve(query_input, limit=5)
        st.session_state.has_searched = True
        # Clear selected document when doing a new search
        st.session_state.selected_document = None


# =============================================================================
# 7. Split Layout: Results vs Document Viewer
# =============================================================================
if st.session_state.has_searched:
    
    # Create the two columns for Master-Detail view
    col_results, col_viewer = st.columns([3, 2])
    
    # --- Column 1: Search Results List ---
    with col_results:
        st.markdown(f"### 🔍 Search Results (`{len(st.session_state.results)} hits`)")
        st.markdown(f"Query: *\"{st.session_state.search_query}\"*")
        st.write("---")
        
        if st.session_state.results:
            for idx, hit in enumerate(st.session_state.results):
                source_name = hit["source"]
                confidence = hit["confidence"]
                snippet = hit["text"]
                
                # Check if this hit is currently selected
                is_selected = (st.session_state.selected_document == source_name)
                border_color = "rgba(66, 133, 244, 0.6)" if is_selected else "rgba(255, 255, 255, 0.08)"
                bg_color = "rgba(66, 133, 244, 0.05)" if is_selected else "rgba(255, 255, 255, 0.03)"
                
                st.markdown(f"""
                <div class="result-card" style="border-color: {border_color}; background-color: {bg_color};">
                    <div class="result-header">
                        <span>📄 <b>{source_name}</b></span>
                        <span class="result-badge">Match: {confidence}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Render snippet and a preview button
                st.markdown(f"<div style='margin-top: -12px; margin-bottom: 12px; font-size: 0.95rem; color:#ccc;'><i>{snippet}</i></div>", unsafe_allow_html=True)
                
                if st.button(f"🔍 Open Document Preview: {source_name}", key=f"preview_btn_{idx}", use_container_width=True):
                    st.session_state.selected_document = source_name
                    st.rerun()
        else:
            st.info("No matching results found. Try broadening your query or rebuild the index in the sidebar.")
            
    # --- Column 2: Document Viewer Detail Pane ---
    with col_viewer:
        st.markdown("### 📄 Document Viewer")
        
        if st.session_state.selected_document:
            doc_name = st.session_state.selected_document
            doc_path = os.path.join(FOLDER_PATH, doc_name)
            
            st.markdown(f"Showing beginning of: **{doc_name}**")
            
            if os.path.exists(doc_path):
                try:
                    with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                        # Read the beginning of the file (first 2500 characters)
                        full_content = f.read(2500)
                        
                    # Calculate if it was truncated
                    file_size = os.path.getsize(doc_path)
                    is_truncated = file_size > len(full_content)
                    
                    # Highlight query words in the content and render as html
                    highlighted_content = highlight_query_terms(full_content, st.session_state.search_query)
                    
                    # Display content inside scrollable styled card
                    st.markdown(f"""
                    <div class="viewer-container">
                        <div class="viewer-content">{highlighted_content}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if is_truncated:
                        st.caption(f"⚠️ Displaying first 2,500 characters of {file_size} bytes. Original source file resides in `./source_docs/{doc_name}`.")
                    else:
                        st.caption(f"✅ Displaying full file ({file_size} bytes).")
                except Exception as e:
                    st.error(f"Failed to read file: {e}")
            else:
                st.error(f"File '{doc_name}' not found at path '{doc_path}'.")
        else:
            # Welcome/Empty Detail State
            st.markdown("""
            <div class="viewer-placeholder">
                <img src="https://img.icons8.com/pastel-glyph/64/document.png" style="opacity: 0.2; margin-bottom: 1rem;"/>
                <p>Click "Open Document Preview" on any result to inspect the document structure and content here.</p>
            </div>
            """, unsafe_allow_html=True)
else:
    # Initial state (if user hasn't typed anything yet)
    # Check if database is empty to warn the user
    if retriever.is_empty():
        st.warning(
            "⚠️ The database is currently empty. "
            "Please click **'Rebuild Database Index'** in the sidebar to scan and index the documents."
        )
    else:
        st.info("💡 Type a query and click 'Search' to view results.")
