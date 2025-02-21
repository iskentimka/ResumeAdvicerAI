# resumeExtract.py
#source venv/bin/activate
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
import json
import pdfplumber
import docx
import re
from pylatexenc.latex2text import LatexNodes2Text
from openai import OpenAI  # Ensure you have the proper OpenAI client installed
import subprocess
import zipfile

def save_docx_xml(docx_path, output_xml_path):
    """Extracts XML from a DOCX file and saves it to a .xml file."""
    with zipfile.ZipFile(docx_path, "r") as docx:
        xml_content = docx.read("word/document.xml").decode("utf-8")  # Extract XML

    # Save XML content to a file
    with open(output_xml_path, "w", encoding="utf-8") as xml_file:
        xml_file.write(xml_content)


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
        # Get the raw content from the message and strip any whitespace.
        raw_content = response.choices[0].message.content.strip()
        print("DEBUG: Raw response content:", raw_content)
        
        # If the raw content is empty, raise an error.
        if not raw_content:
            raise Exception("Received empty response from OpenAI API. Check your prompt, API key, or usage limits.")
        
        # Use the helper function to remove markdown fences (if any)
        json_str = extract_json_from_response(raw_content)
        print("DEBUG: Cleaned JSON content:", json_str)
        
        if not json_str:
            raise Exception("After cleaning, the response content is empty.")
        
        try:
            json_data = json.loads(json_str)
        except Exception as e:
            raise Exception(f"Error parsing JSON: {e}. Raw JSON string: {json_str}")
        
        with open("extracted_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, indent=4)
        return json_data

    def get_generated_new_text(self, extracted_data, job_description: str):
        """
        Uses OpenAI to generate a new description based on the extracted
        resume section and the job description. Expects a prompt template in 'generatePrompt.txt'.
        
        For each extracted part, if a "description" exists, it is used; otherwise the "text" field is used.
        
        Returns a dictionary mapping an index to an object with:
        - "section": the section name (e.g., "experience", "skills")
        - "extracted": the original extracted text for that section
        - "generated": the revised text returned by the API.
        """
        try:
            with open("generatePrompt.txt", "r", encoding="utf-8") as file:
                prompt_generate = file.read()
        except Exception as e:
            raise Exception(f"Could not read generatePrompt.txt: {str(e)}")
        
        result_map = {}
        for i, part in enumerate(extracted_data):
            # Use "description" if available; otherwise, fallback to "text".
            content = part.get("description") or part.get("text") or ""
            # Build the prompt.
            prompt = prompt_generate + f"</job_description>{job_description}</>\n</resume_part>{content}</>"
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            generated_text = response.choices[0].message.content.strip()
            result_map[i] = {
                "section": part["section"],
                "extracted": content,
                "generated": generated_text
            }
        
        with open("generated_data.json", "w", encoding="utf-8") as json_file:
            json.dump(result_map, json_file, indent=4)
        
        return result_map

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
    

    
    def extract_docx_runs_to_json(self, docx_path: str, output_json_path: str) -> None:
        """
        Extracts text from each run in a DOCX file and saves the result to a JSON file.
        
        Each run is represented as a dictionary in the following format:
        {
            "text": "example",
            "paragraph": 1,
            "run": 1
        }
        
        :param docx_path: Path to the DOCX file.
        :param output_json_path: Path where the JSON file should be saved.
        """
        document = docx.Document(docx_path)
        data = []
        
        for p_idx, paragraph in enumerate(document.paragraphs, start=1):
            for r_idx, run in enumerate(paragraph.runs, start=1):
                data.append({
                    "text": run.text,
                    "paragraph": p_idx,
                    "run": r_idx
                })
        
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)



if __name__ == "__main__":
    API_KEY = "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"
    formatter = ResumeFormatter(API_KEY)

    # Read the job description from file.
    with open("description.txt", "r", encoding="utf-8") as file:
        job_description = file.read()
    
    # ---------------- DOCX Example ----------------
    #save_docx_xml("resume_test.docx", "output.xml")
    formatter.extract_docx_runs_to_json("resume_test.docx", "resume_text_with_runs")
    
    

    
    
    # extracted_data = formatter.extract_editable_parts(text_from_doc)
    # print(f"Extracted by AI data: {extracted_data}\n")

    # json_generated_new_data = formatter.get_generated_new_text(extracted_data, job_description)
    # print(f"Generated by AI data: {json_generated_new_data}\n")

    



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