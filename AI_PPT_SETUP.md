# AI PDF to PowerPoint setup

PDFMaster Pro now supports two PDF to PowerPoint modes:

1. **AI Presentation** (default): extracts PDF text/tables locally, uses Groq to create a presentation plan, and generates an editable `.pptx` with `python-pptx`.
2. **Preserve PDF Layout**: keeps the existing page-fidelity converter for scans or documents where exact page appearance matters more than slide restructuring.

## Coolify environment variables

Add these environment variables to the PDFMaster Pro application before deploying AI mode:

```text
GROQ_API_KEY=<your existing Groq API key>
GROQ_MODEL=openai/gpt-oss-120b
```

`GROQ_MODEL` is optional. If omitted, the application uses `openai/gpt-oss-120b` by default.

Groq retired `llama-3.3-70b-versatile` for free/developer-tier usage on August 16, 2026. PDFMaster Pro also normalizes that legacy model ID to `openai/gpt-oss-120b` at startup so an older Coolify value does not break the homepage AI assistant or AI PowerPoint mode.

The API key is read only by the Flask backend. It is never sent to browser JavaScript or stored in generated PowerPoint files.

## AI Presentation behavior

The backend:

- extracts text and useful tables with `pdfplumber`;
- asks Groq for strict JSON describing titles, slide divisions, bullet points, optional tables, source page references, and speaker notes;
- creates a widescreen editable PowerPoint with `python-pptx`;
- can use selected source pages as supporting visuals without making the whole deck a set of screenshots;
- preserves a non-AI layout mode as a fallback.

The user can choose Short, Standard, or Detailed length and Professional, Academic, or Simple presentation style.

## Important limitation

AI Presentation needs extractable text. For a scanned/image-only PDF, run OCR first or select Preserve PDF Layout.
