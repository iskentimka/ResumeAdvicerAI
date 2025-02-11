# resumeExtract.py

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
import json
import pdfplumber
import docx
import re
import fitz
from pylatexenc.latex2text import LatexNodes2Text
from openai import OpenAI  # Ensure you have the proper OpenAI client installed

# ------------------------------------------------------------------------------
# Single Class Combining All Functionality
# ------------------------------------------------------------------------------
class ResumeFormatter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.openai_client = OpenAI(api_key=api_key)

    # --- Extraction Methods ---
    def extract_from_pdf(self, pdf_path: str) -> str:
        """Extract text from a PDF file."""
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()

    def extract_text_with_positions(self, pdf_path: str):
        """
        Extracts text with position information from a PDF.
        Returns a list of tuples: (page_num, x0, y0, x1, y1, text)
        """
        text_positions = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                words = page.extract_words()
                for word in words:
                    x0, y0, x1, y1, text = word['x0'], word['top'], word['x1'], word['bottom'], word['text']
                    text_positions.append((page_num, x0, y0, x1, y1, text))
        return text_positions

    def extract_from_docx(self, docx_path: str) -> str:
        """Extract text from a DOCX file."""
        doc = docx.Document(docx_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return text.strip()

    def extract_from_latex(self, tex_path: str) -> str:
        """Extract and clean text from a LaTeX file."""
        with open(tex_path, "r", encoding="utf-8") as file:
            latex_content = file.read()
        text = LatexNodes2Text().latex_to_text(latex_content)
        text = re.sub(r'\\[a-zA-Z]+\{.*?\}', '', text)
        text = re.sub(r'%.*', '', text)
        text = re.sub(r'[\t\r]', '', text)
        return text.strip()

    def extract(self, file_path: str) -> str:
        """Determine file type and extract text accordingly."""
        if file_path.endswith(".pdf"):
            return self.extract_from_pdf(file_path)
        elif file_path.endswith(".docx"):
            return self.extract_from_docx(file_path)
        elif file_path.endswith(".tex"):
            return self.extract_from_latex(file_path)
        else:
            raise ValueError("Unsupported file format")

    # --- AI Methods ---
    def extract_editable_parts(self, text: str):
        """
        Uses OpenAI to extract editable parts from the text.
        Expects a prompt template in 'promptExtract.txt'.
        """
        try:
            with open("promptExtract.txt", "r", encoding="utf-8") as file:
                prompt = file.read()
        except Exception as e:
            raise Exception(f"Could not read promptExtract.txt: {str(e)}")
        prompt += f"</input_text_resume>{text}</>"

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message

    def generate_new_description(self, extracted_resume_text, job_description: str):
        """
        Uses OpenAI to generate a new description based on the extracted
        resume text and the job description. Expects a prompt template in 'generatePrompt.txt'.
        """
        try:
            with open("generatePrompt.txt", "r", encoding="utf-8") as file:
                prompt = file.read()
        except Exception as e:
            raise Exception(f"Could not read generatePrompt.txt: {str(e)}")
        prompt += f"</job_description>{job_description}</>\n</resume_parts>{extracted_resume_text}</>"

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message

    # --- PDF Modification (Parsing) ---
    def replace_text(self, pdf_path: str, modified_data, extracted_data, text_positions) -> str:
        """
        Dummy implementation that opens the PDF and saves a copy.
        Replace this with your own logic to replace text.
        """
        doc = fitz.open(pdf_path)
        # (Implement your custom text-replacement logic here using modified_data and text_positions)
        output_pdf = pdf_path.replace(".pdf", "_modified.pdf")
        doc.save(output_pdf)
        doc.close()
        return output_pdf

# ------------------------------------------------------------------------------
# FastAPI Setup & Endpoint
# ------------------------------------------------------------------------------
app = FastAPI()

# Enable CORS so that your React frontend (running on http://localhost:5173) can connect.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Replace with your actual OpenAI API key.
API_KEY = "YOUR_OPENAI_API_KEY"

# Create a single instance of ResumeFormatter.
formatter = ResumeFormatter(API_KEY)

@app.post("/api/format-cv")
async def format_cv(
    cv_file: UploadFile = File(None),
    latex_code: str = Form(None),
    job_desc_link: str = Form(None),
    job_description: str = Form(None)
):
    # Ensure that a CV input is provided.
    if not (latex_code or cv_file):
        raise HTTPException(status_code=400, detail="A CV file or LaTeX code must be provided.")

    with tempfile.TemporaryDirectory() as tmpdirname:
        # Save the incoming CV input to a temporary file.
        if latex_code:
            cv_path = os.path.join(tmpdirname, "cv_input.tex")
            with open(cv_path, "w", encoding="utf-8") as f:
                f.write(latex_code)
            # Optionally: compile the LaTeX code to PDF if needed.
        else:
            original_filename = cv_file.filename
            _, ext = os.path.splitext(original_filename)
            cv_path = os.path.join(tmpdirname, f"cv_input{ext}")
            with open(cv_path, "wb") as f:
                content = await cv_file.read()
                f.write(content)

        # Extract text from the CV file.
        try:
            extracted_text = formatter.extract(cv_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error extracting text: {str(e)}")

        # Use OpenAI to extract editable parts from the resume text.
        try:
            editable_parts_raw = formatter.extract_editable_parts(extracted_text)
            editable_parts = json.loads(editable_parts_raw)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error extracting editable parts: {str(e)}")

        # Use the provided job description; if only a link is provided, use that.
        if job_desc_link and not job_description:
            job_description = job_desc_link

        if not job_description:
            raise HTTPException(status_code=400, detail="Job description is required.")

        # Generate new description based on extracted resume parts and job description.
        try:
            generated_text_raw = formatter.generate_new_description(editable_parts, job_description)
            generated_text = json.loads(generated_text_raw)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating new description: {str(e)}")

        # For this example, we assume the input CV is a PDF.
        if not cv_path.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Currently, only PDF CV files are supported for formatting.")

        # Extract text positions from the PDF.
        text_positions = formatter.extract_text_with_positions(cv_path)

        # Replace text in the PDF with the generated text.
        try:
            formatted_pdf_path = formatter.replace_text(cv_path, generated_text, editable_parts, text_positions)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error formatting PDF: {str(e)}")

        # Return the modified PDF as a download.
        return FileResponse(
            formatted_pdf_path,
            filename="formatted_cv.pdf",
            media_type="application/pdf"
        )

# ------------------------------------------------------------------------------
# Run the FastAPI App if Executed Directly
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("resumeExtract:app", host="0.0.0.0", port=8000, reload=True)
