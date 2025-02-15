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
import subprocess

# ------------------------------------------------------------------------------
# Helper function to extract JSON string from API responses that may be wrapped in markdown code fences.
# ------------------------------------------------------------------------------
def extract_json_from_response(response_content: str) -> str:
    """
    Extracts JSON string from a response that might be wrapped in markdown code fences.
    For example, if the response is like:
        ```json
        { ... }
        ```
    it will return the inner JSON.
    """
    match = re.search(r"```json(.*?)```", response_content, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        json_str = response_content.strip()
    return json_str

# ------------------------------------------------------------------------------
# Single Class Combining All Functionality
# ------------------------------------------------------------------------------
class ResumeFormatter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.openai_client = OpenAI(api_key=api_key)

    # --- Extraction Methods ---
    def extract_from_pdf(self, pdf_path: str):
        """Extract text from a PDF file along with text positions."""
        text = ""
        text_positions = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                words = page.extract_words()
                for word in words:
                    x0, y0, x1, y1, frag_text = word['x0'], word['top'], word['x1'], word['bottom'], word['text']
                    text_positions.append((page_num, x0, y0, x1, y1, frag_text))
        return (text.strip(), text_positions)

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
                    x0, y0, x1, y1, frag_text = word['x0'], word['top'], word['x1'], word['bottom'], word['text']
                    text_positions.append((page_num, x0, y0, x1, y1, frag_text))
        return text_positions

    def extract_from_docx(self, docx_path: str) -> str:
        """Extract text from a DOCX file."""
        doc = docx.Document(docx_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return text

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
            extracted, _ = self.extract_from_pdf(file_path)
            return extracted
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
        Replaces parts of the PDF text with modified text.
        
        Parameters:
          pdf_path (str): Path to the input PDF.
          modified_data (dict): Mapping from field names to new text.
          extracted_data (dict): Mapping from field names to original text.
          text_positions (list): List of tuples (page_num, x0, y0, x1, y1, text) from the PDF.
        
        Returns:
          str: Path to the modified PDF.
        """
        doc = fitz.open(pdf_path)

        # Loop over each field that might have been edited.
        for field, new_text in modified_data.items():
            old_text = extracted_data.get(field)
            print(f"OLD TEXT for '{field}': {old_text}")
            if not old_text:
                continue
            if old_text == new_text:
                continue

            # Search for the old text in the text positions.
            for (page_num, x0, y0, x1, y1, frag_text) in text_positions:
                if old_text in frag_text:
                    page = doc[page_num]
                    rect = fitz.Rect(x0, y0, x1, y1)
                    # Erase the old text.
                    page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                    # Insert the new text.
                    page.insert_textbox(
                        rect,
                        new_text,
                        fontname="helv",
                        fontsize=12,
                        color=(0, 0, 0),
                        align=0
                    )
                    break

        output_pdf = pdf_path.replace(".pdf", "_modified.pdf")
        doc.save(output_pdf)
        doc.close()
        return output_pdf



       

    # --- LaTeX Modification ---
    def replace_text_latex(self, tex_path: str, modified_data, extracted_data) -> str:
        """
        Replaces parts of the LaTeX file text with modified text.
        
        Parameters:
          tex_path (str): Path to the input LaTeX file.
          modified_data (dict): Mapping from field names to new text.
          extracted_data (dict): Mapping from field names to original text.
        
        Returns:
          str: Path to the modified LaTeX file.
        """
        with open(tex_path, "r", encoding="utf-8") as file:
            content = file.read()
        for field, new_text in modified_data.items():
            old_text = extracted_data.get(field)
            if not old_text:
                continue
            if old_text == new_text:
                continue
            content = content.replace(old_text, new_text)
        output_tex = tex_path.replace(".tex", "_modified.tex")
        with open(output_tex, "w", encoding="utf-8") as file:
            file.write(content)
        return output_tex
    
    def map_extracted_to_generated(self,extracted_data, generated_data):
        """
        Maps texts from extracted AI data to the generated AI data using the index field.
        
        Parameters:
            extracted_data (list): List of dictionaries with extracted AI data.
            generated_data (list): List of dictionaries with generated AI data.
        
        Returns:
            dict: A dictionary where keys are index values and values are dictionaries with 'extracted' and 'generated' text.
        """
        mapping = {}

        # Convert generated_data into a dictionary for fast lookup by index
        generated_dict = {item["index"]: item["text"] for item in generated_data}

        # Iterate over extracted data and find corresponding generated text by index
        for item in extracted_data:
            index = item["index"]
            extracted_text = item["text"]
            generated_text = generated_dict.get(index, None)  # Get generated text, if exists
            
            mapping[index] = {
                "name": item["name"],  # Include name for reference
                "extracted": extracted_text,
                "generated": generated_text
            }

        return mapping
    
    def run_csharp_replacer(input_docx: str, json_mapping: str, output_docx: str) -> str:
        """
        Calls the C# DocxTextReplacer executable to replace text in a DOCX file.
        
        Parameters:
            input_docx (str): Path to the input DOCX file.
            json_mapping (str): Path to the JSON mapping file with old/new texts.
            output_docx (str): Path where the modified DOCX file will be saved.
        
        Returns:
            str: Path to the modified DOCX file.
        """
        command = ["./bin/Release/net8.0/osx-x64/publish/DocxTextReplacer", input_docx, json_mapping, output_docx]
        subprocess.run(command, check=True)
        return output_docx


# ------------------------------------------------------------------------------
# FastAPI Setup & Endpoint (Commented out for now)
# ------------------------------------------------------------------------------
# app = FastAPI()
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# API_KEY = "your-api-key-here"  # Replace with your actual API key.
# formatter = ResumeFormatter(API_KEY)
#
# @app.post("/api/format-cv")
# async def format_cv(
#     cv_file: UploadFile = File(None),
#     latex_code: str = Form(None),
#     job_desc_link: str = Form(None),
#     job_description: str = Form(None)
# ):
#     # ... (your endpoint implementation)
#     pass
#
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("resumeExtract:app", host="0.0.0.0", port=8000, reload=True)

# ------------------------------------------------------------------------------
# Main block for testing
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    API_KEY = "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"
    formatter = ResumeFormatter(API_KEY)

    # Read the job description from file.
    with open("description.txt", "r", encoding="utf-8") as file:
        job_description = file.read()
    
    # ---------------- DOCX Example ----------------
    text_from_doc = formatter.extract_from_docx("resume_test.docx")
    print(f"Extracted text from docx: {text_from_doc}\n")
    
    json_extracted_data = json.loads(extract_json_from_response(formatter.extract_editable_parts(text_from_doc).content))
    print(f"Extracted by AI data: {json_extracted_data}\n")

    json_generated_new_data = json.loads(extract_json_from_response(formatter.generate_new_description(json_extracted_data, job_description).content))
    print(f"Generated by AI data: {json_generated_new_data}\n")

    map_between_old_and_new_data = formatter.map_extracted_to_generated(json_extracted_data, json_generated_new_data)
    print(f"Map between data: {map_between_old_and_new_data}\n")
