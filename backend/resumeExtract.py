# resumeExtract.py
import shutil
import os
import json
import re
import pdfplumber
import docx
import fitz
import subprocess
import zipfile
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pylatexenc.latex2text import LatexNodes2Text
from openai import OpenAI  # Make sure official openai python pkg is installed

def save_docx_xml(docx_path, output_xml_path):
    """Extracts XML from a DOCX file and saves it to a .xml file (for debugging)."""
    with zipfile.ZipFile(docx_path, "r") as docx_zip:
        xml_content = docx_zip.read("word/document.xml").decode("utf-8")
    with open(output_xml_path, "w", encoding="utf-8") as xml_file:
        xml_file.write(xml_content)

def extract_json_from_response(response_content: str) -> str:
    """
    Extracts JSON string from a response that might be wrapped in markdown code fences.
    For example:
        ```json
        { ... }
        ```
    it will return the inner JSON.
    """
    match = re.search(r"```json(.*?)```", response_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response_content.strip()

class ResumeFormatter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.openai_client = OpenAI(api_key=api_key)

    # ---------------- Extraction Methods ----------------
    def extract_from_pdf(self, pdf_path: str):
        """Extract text from a PDF (return entire text + positions)."""
        text = ""
        text_positions = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                words = page.extract_words()
                for w in words:
                    x0, y0, x1, y1, frag_text = (
                        w['x0'], w['top'], w['x1'], w['bottom'], w['text']
                    )
                    text_positions.append((page_num, x0, y0, x1, y1, frag_text))
        return (text.strip(), text_positions)

    def extract_from_docx(self, docx_path: str) -> str:
        """Extract text from a DOCX by joining paragraphs (naive)."""
        doc = docx.Document(docx_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return text

    def extract_from_latex(self, tex_path: str) -> str:
        """Extract and clean text from a .tex file."""
        with open(tex_path, "r", encoding="utf-8") as f:
            latex_content = f.read()
        text = LatexNodes2Text().latex_to_text(latex_content)
        # Remove commands
        text = re.sub(r'\\[a-zA-Z]+\{.*?\}', '', text)
        # Remove comments
        text = re.sub(r'%.*', '', text)
        # Remove tabs/returns
        text = re.sub(r'[\t\r]', '', text)
        return text.strip()

    def extract(self, file_path: str) -> str:
        """Generic method to pick correct extraction depending on file type."""
        if file_path.endswith(".pdf"):
            extracted, _ = self.extract_from_pdf(file_path)
            return extracted
        elif file_path.endswith(".docx"):
            return self.extract_from_docx(file_path)
        elif file_path.endswith(".tex"):
            return self.extract_from_latex(file_path)
        else:
            raise ValueError("Unsupported file format.")

    # ---------------- AI Methods ----------------
    def extract_editable_parts(self, text: str):
        """
        Calls OpenAI to parse the resume text and separate it into editable sections.
        The logic is defined in 'promptExtract.txt'.
        """
        # 1) Load your prompt
        try:
            with open("promptExtract.txt", "r", encoding="utf-8") as f:
                prompt = f.read()
        except Exception as e:
            raise Exception(f"Could not read promptExtract.txt: {str(e)}")

        # 2) Append the user text
        prompt += f"</input_text_resume>{text}</>"

        # 3) Call OpenAI
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        raw_content = response.choices[0].message.content.strip()
        if not raw_content:
            raise Exception("Empty response from OpenAI. Check prompt or API usage.")

        # 4) Extract JSON from possible markdown fences
        json_str = extract_json_from_response(raw_content)
        if not json_str:
            raise Exception("No JSON found in AI response.")
        
        # 5) Parse JSON
        try:
            json_data = json.loads(json_str)
        except Exception as e:
            raise Exception(f"Error parsing JSON: {e}\nRaw JSON: {json_str}")

        # 6) Write to extracted_data.json for debugging
        with open("extracted_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, indent=4)

        return json_data

    def get_generated_new_text(self, extracted_data, job_description: str):
        """
        Calls OpenAI with each extracted portion + your job_description,
        to produce a revised version. Writes out generated_data.json with
        "extracted" and "generated" keys.
        """
        try:
            with open("generatePrompt.txt", "r", encoding="utf-8") as f:
                prompt_generate = f.read()
        except Exception as e:
            raise Exception(f"Could not read generatePrompt.txt: {str(e)}")

        result_map = {}
        for i, part in enumerate(extracted_data):
            content = part.get("description") or part.get("text") or ""
            prompt = (
                prompt_generate
                + f"</job_description>{job_description}</>\n</resume_part>{content}</>"
            )

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            new_text = response.choices[0].message.content.strip()
            result_map[i] = {
                "section": part["section"],
                "extracted": content,
                "generated": new_text
            }

        # Save final text mapping as generated_data.json
        with open("generated_data.json", "w", encoding="utf-8") as json_file:
            json.dump(result_map, json_file, indent=4)

        return result_map

if __name__ == "__main__":
    API_KEY = "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"
    formatter = ResumeFormatter(API_KEY)

    # 1) read job description from file
    with open("description.txt", "r", encoding="utf-8") as f:
        job_desc = f.read()

    # 2) extract text from docx
    text_from_doc = formatter.extract("resume_test.docx")
    print("Extracted text from docx:\n", text_from_doc, "\n")

    # 3) optional debug: see raw XML
    save_docx_xml("resume_test.docx", "output.xml")

    # 4) call AI to figure out the "editable parts"
    extracted_data = formatter.extract_editable_parts(text_from_doc)

    # 5) call AI again to generate new text for each extracted part
    json_generated_data = formatter.get_generated_new_text(extracted_data, job_desc)

