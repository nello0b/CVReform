# CVReform MVP

## Goal

Convert an uploaded DOCX or PDF CV into an editable web document that preserves its visual style.

## Main Flow

1. Upload CV
2. Validate and store the document
3. Create a PDF visual reference for DOCX input when PDF support is enabled
4. Extract the document content and render its visual appearance
5. Generate matching HTML and CSS
6. Edit the CV in the browser
7. Export the edited CV to PDF

## MVP Features

- DOCX upload
- Independently configurable DOCX and PDF inputs
- Optional DOCX-to-PDF visual-reference conversion with LibreOffice
- Document validation and storage
- Style-preserving HTML and CSS generation
- Browser-based text editing
- PDF export
- Clear error messages

## Success Criteria

The MVP is complete when a user can upload a supported CV, edit its content in a visually faithful web version, and export the result to PDF.

## Not Included Yet

- Job-specific tailoring
- User accounts
- Saved history
- Multiple templates
- Advanced layout editing
