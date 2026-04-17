Summary
JOB TITLE
Python Developer — PDF to Markdown batch pipeline (LLM-assisted document parsing)

PROJECT OVERVIEW
We are building an AI platform for Italian urban planning professionals. We need a batch pipeline built from scratch that converts PDF documents (Italian municipal regulations, ~100 pages each) into clean, structured Markdown files ready to be ingested by an LLM-based RAG system.
We provide PDF examples, expected Markdown output, and a full output specification document. 
See @atatchments/ for these files.

Your job is to build the pipeline from the ground up so it runs automatically on batches of documents without manual intervention.

WHAT YOU WILL BUILD
A Python script (or set of scripts) that:
	1.	Takes a folder of PDF files as input
	2.	Extracts and structures the text, preserving document hierarchy:
	•	Title (Titolo)
	•	Chapter (Capo)
	•	Article (Articolo)
	•	Paragraph (Comma)
	3.	Outputs one clean .md file per PDF with correct Markdown heading levels (# ## ### ####)
	4.	Each .md file must include a YAML front matter block (titolo, comune, tipo, anno) and follow the heading hierarchy # → ## → ### → #### without arbitrary skips
	5.	Runs in batch on 20–50 documents in parallel, unattended
	6.	Handles variation between documents — structure is detected using an LLM (Gemini API), not hardcoded rules
We provide:
	•	PDF examples and expected Markdown output
	•	Full output specification document with dos/don’ts and delivery checklist
	•	Two reference Markdown examples (real municipal instruments)

TECH STACK
	•	Python 3.10+
	•	Gemini API (we provide the key)
	•	PyMuPDF or Docling for PDF extraction
	•	No knowledge of Italian law or urban planning required

DELIVERABLE & ACCEPTANCE CRITERIA
	•	Script runs on a folder of PDFs and produces Markdown files with no manual step per document
	•	Correct heading hierarchy on at least 90% of documents in a test batch we provide
	•	Each output file includes valid YAML front matter
	•	Code is clean, commented, and easy to maintain
	•	Delivery within 2–3 weeks