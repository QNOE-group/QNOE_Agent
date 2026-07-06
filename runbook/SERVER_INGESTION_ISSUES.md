# Server Ingestion — Per-Folder Issues & Status

*Last updated: 2026-06-18*

This document summarises the issues encountered ingesting `/ICFO/groups/NOE/` into Qdrant (`group-wide` collection), the fixes applied, and remaining work per folder.

---

## Summary Table

| Folder | Files (indexable) | Status | Modifications applied | Key Issues |
|--------|-------------------|--------|-----------------------|------------|
| Lab_Instruments | ~1,474 | 🟡 In progress | `DOCLING_DEVICE=cuda` (GPU Docling) | Some scanned PDFs, slow CIFS |
| Manuscripts | ~10,725 | ✅ Done (pypdf) | `DOCLING_DISABLE=1` (pypdf only); `EXCLUDE_EXTENSIONS` not applied | 315 suspected papers identified → 26 confirmed for Docling re-run (launched) |
| Meetings | ~631 | ✅ Done | None | — |
| Notebook | ~34,894 | 🟡 In progress (34%) | None (mostly .py/.ipynb — no Docling anyway); CIFS find workaround | CIFS rglob hang; `find` eventually got through |
| Notebooks | ~155 | ✅ Done | None | — |
| Papers & Books | ~288 | 🟡 In progress (8%) | `DOCLING_DEVICE=cuda` (GPU Docling for papers); path-based paper detection removed | Textbooks slow on GPU (~150s each); 65 confirmed papers will be Docling-verified by current run |
| Posters | ~443 | ✅ Done | None | Poster PDFs give 1 chunk (expected — image-heavy) |
| Presentation | ~7 | ✅ Done | None | — |
| Presentations | ~47 | ✅ Done | None | — |
| Projects | ~28,407 | 🟡 In progress (30%) | `DOCLING_DISABLE=1` (pypdf only); `EXCLUDE_EXTENSIONS=.txt` | CIFS find hang; 18k raw `.txt` excluded; 10,822 PDFs pypdf-only |
| Spectromag | ~42 | ✅ Done | None | Raw IV-curve `.txt` files indexed (noise) |
| Theses & reports | ~3,992 (excl. .txt) | ✅ Done (pypdf) | `DOCLING_DISABLE=1` (pypdf only); `EXCLUDE_EXTENSIONS=.txt` | 10,035 raw `.txt` excluded; 112 suspected papers identified → 19 confirmed for Docling re-run (launched) |

---

## Modification Legend

| Modification | Effect | Applied to |
|---|---|---|
| `DOCLING_DISABLE=1` | Skip Docling entirely — all PDFs processed by pypdf only. Fast (~1s/file) but loses layout awareness for multi-column papers. | Manuscripts, Projects, Theses & reports |
| `DOCLING_DEVICE=cuda` | Use GPU (CUDA) for Docling layout model instead of CPU. Speeds up paper PDF processing from ~300s → ~100s. | Lab_Instruments, Papers & Books |
| `EXCLUDE_EXTENSIONS=.txt` | Skip `.txt` files at discovery stage. Cuts noise from raw QCoDeS measurement exports (IV curves, time series). | Projects, Theses & reports |
| Path-based paper detection removed | `_is_likely_paper()` used to check if `"papers"` appeared in the file path. Fixed to content-only detection (Abstract + email/affiliation or short average line length). Was routing all 288 "Papers & Books" files through Docling incl. 800-page textbooks. | Papers & Books |
| `subprocess find` replacing `rglob` | Avoids Python stat()-per-file over CIFS (causes D-state hangs). `find` batches dir reads in kernel. Falls back to rglob on timeout. | All folders (global fix in `run_ingest.py`) |
| Confirmed-paper Docling re-run | For folders run with `DOCLING_DISABLE=1`, suspected papers were identified by heuristic, user reviewed them, confirmed files are now re-indexed with GPU Docling using `--file-list`. | Manuscripts (26 files), Theses & reports (19 files) |

---

## Per-Folder Detail

### Lab_Instruments
- **1,476 files** — instrument manuals, calibration reports, datasheets
- Running with `DOCLING_DEVICE=cuda` since restart
- Some PDFs are scanned (CalibrationReportDescription.pdf = 1 chunk) — no OCR pipeline
- **Status:** In progress

### Manuscripts
- **10,808 total files** of which indexable: ~10,725
- File breakdown: 5,172 `.txt`, 3,788 `.pdf`, 944 `.docx`, 412 `.py`, 378 `.pptx`
- **Issue 1:** `.txt` files are raw measurement/analysis data (not prose) — 1 chunk each, noise. Not excluded here (EXCLUDE_EXTENSIONS not applied); would benefit from exclusion on re-run.
- **Issue 2:** 3,788 PDFs through Docling on CPU = estimated 200+ hours
- **Fix applied:** `DOCLING_DISABLE=1` — all PDFs go through pypdf only
- **Paper re-run:** 315 PDFs identified as suspected papers by content heuristic. User reviewed 165; 26 confirmed. Docling re-run launched (`/tmp/docling_rerun_w2.log`).
- **Confirmed paper list:** `/tmp/confirmed_papers_manuscripts.txt` (26 files)

### Meetings
- ✅ Complete. No issues.

### Notebook
- **34,894 indexable files** — mostly raw QCoDeS measurement code and data
- **Issue:** `pathlib.rglob()` and short-timeout `find` both hung on CIFS with this many files
- **Fix:** `subprocess find` with 300s timeout; the folder eventually returned results on the current run
- **Status:** In progress (~35%). No Docling needed (mostly .py/.ipynb files).

### Notebooks
- ✅ Complete. Jupyter notebooks indexed cleanly.

### Papers & Books
- **288 files** — mix of research papers, textbook chapters, conference proceedings
- **Issue 1 (fixed):** Path-based paper detection triggered Docling for everything (folder name `"Papers & Books"` contains `"papers"`). 800-page textbooks took 100–150s each.
- **Fix:** Removed path-based detection. Content-only heuristic now.
- **Issue 2:** Even with fix, actual papers go through GPU Docling (~100s each). 288 files × ~100s = ~8h total.
- Running with `DOCLING_DEVICE=cuda`
- **Status:** In progress (~8%). The 65 confirmed papers from the review will be handled by this run (GPU Docling already active).

### Posters
- ✅ Complete.
- Many poster PDFs get 1 chunk — expected. Posters are graphical with minimal text.

### Presentation / Presentations
- ✅ Complete. No issues.

### Projects
- **~280,000+ total files** (entire project tree including raw data)
- **Indexable files:** ~28,407 (after extension filter)
- File breakdown: 18,365 `.txt` (raw data), 10,822 `.pdf`, 6,183 `.db` (QCoDeS), 5,366 `.py`, 4,673 `.pptx`
- **Issue 1:** CIFS `find` hung initially — same as Notebook. Current run got through.
- **Issue 2:** 18,365 `.txt` files are raw measurement data — excluded via `EXCLUDE_EXTENSIONS=.txt`
- **Issue 3:** 10,822 PDFs even with pypdf-only = ~3h; many are analysis output PDFs (plots, figures), not prose
- **Fix applied:** `DOCLING_DISABLE=1` + `EXCLUDE_EXTENSIONS=.txt`
- **Status:** In progress (~30%).

### Spectromag
- ✅ Complete (39/42 files).
- `.txt` files (e.g. `C150ohm iv103 c1 pin100001.txt`) are raw IV-curve data — 1 chunk each, noise.
- **Recommendation:** Exclude `.txt` from Spectromag on future re-runs.

### Theses & reports
- **14,028 total files**, reduced to **~3,992 indexable** after excluding `.txt`
- File breakdown (after exclusion): 2,112 `.pdf`, 677 `.ipynb`, 647 `.db`, 455 `.pptx`, 87 `.py`, 70 `.docx`
- **Issue 1:** 10,035 `.txt` files are raw measurement data — excluded via `EXCLUDE_EXTENSIONS=.txt`
- **Issue 2:** 2,112 thesis PDFs through Docling = very slow even on GPU
- **Fix applied:** `DOCLING_DISABLE=1` + `EXCLUDE_EXTENSIONS=.txt`
- **Paper re-run:** 112 PDFs identified as suspected papers. User reviewed 56; 19 confirmed. Docling re-run launched (`/tmp/docling_rerun_w12.log`).
- **Confirmed paper list:** `/tmp/confirmed_papers_theses.txt` (19 files)

---

## Empty PDFs (scanned — no text layer)

- **8,056 PDFs** across all folders returned < 200 characters from pypdf and were **not indexed** (0 chunks).
- These are scanned documents, poster images, or figure-only PDFs.
- Logged to `/tmp/empty_pdfs.log` on DGX.
- OCR pipeline would be required to extract text. Currently not implemented (backlogged as B5).

---

## Global Issues Fixed

| Issue | Fix | Where |
|-------|-----|--------|
| `pathlib.rglob()` hangs on CIFS mounts with many files | Replaced with `subprocess find` + Python fallback | `run_ingest.py:_find_files()` |
| Windows Office lock files (`~$*.pptx`) picked up | Filter `path.name.startswith("~$")` | `run_ingest.py:_find_files()` |
| Path-based paper detection (`"papers"` in folder name) | Removed — content-only detection now | `splitter.py:_is_likely_paper()` |
| Scanned PDFs sent to Docling unnecessarily | Skip Docling if pypdf gets <200 chars | `splitter.py:_chunk_pdf()` |
| `DOCLING_DISABLE=1` env var | Bypass Docling entirely — pypdf only | `splitter.py:_chunk_pdf()` |
| `EXCLUDE_EXTENSIONS=.txt` env var | Skip raw data text files | `run_ingest.py:_find_files()` |
| `DOCLING_DEVICE=cuda` env var | Use GPU for Docling when vLLM is stopped | `splitter.py:_get_pdf_converter()` |
| `--file-list` flag in `run_ingest.py` | Re-index specific files with Docling after bulk pypdf-only run | `run_ingest.py:main()` |

---

## Pending Actions

- [ ] **Manuscripts re-run:** Monitor `/tmp/docling_rerun_w2.log` — 26 confirmed papers being re-indexed with GPU Docling
- [ ] **Theses re-run:** Monitor `/tmp/docling_rerun_w12.log` — 19 confirmed files being re-indexed with GPU Docling
- [ ] **Papers & Books re-run (W6):** 65 confirmed papers already covered by the running GPU Docling worker — no separate re-run needed
- [ ] **W6 confirmed list:** After W6 finishes, verify chunks counts look correct for the 65 confirmed papers
- [ ] **Notebook:** Currently ~35% — monitor `/tmp/ingest_w4.log`. Est. 2–3h remaining.
- [ ] **Projects:** Currently ~30% — monitor `/tmp/ingest_w10.log`. Est. 3–4h remaining.
- [ ] **Lab_Instruments:** Monitor until complete
- [ ] **OCR pipeline (B5):** 8,056 scanned PDFs got 0 chunks — need OCR to be useful. Backlogged.
- [ ] **Orphan sweep:** Files deleted from server still have stale chunks in Qdrant — add periodic cleanup
- [ ] **Re-enable vLLM** after ingestion completes: `sudo systemctl start vllm`
- [ ] **Manuscripts `.txt` files:** Consider adding `EXCLUDE_EXTENSIONS=.txt` on next Manuscripts re-run (5,172 raw data files currently indexed as noise)
