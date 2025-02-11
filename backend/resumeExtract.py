from openai import OpenAI
import pdfplumber
import docx
import re
import fitz
import json
from pylatexenc.latex2text import LatexNodes2Text


class Extractor:
    """Handles text extraction from different file types."""

    @staticmethod
    def extract_from_pdf(pdf_path):
        """Extracts text from a PDF file."""
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    
    
    @staticmethod
    def extract_text_with_positions(pdf_path):
        with pdfplumber.open(pdf_path) as pdf:
            text_positions = []

            for page_num, page in enumerate(pdf.pages):
                words = page.extract_words()
                
                for word in words:
                    x0, y0, x1, y1, text = word['x0'], word['top'], word['x1'], word['bottom'], word['text']
                    text_positions.append((page_num, x0, y0, x1, y1, text))

        return text_positions


    @staticmethod
    def extract_from_docx(docx_path):
        """Extracts text from a DOCX file."""
        doc = docx.Document(docx_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return text.strip()

    @staticmethod
    def extract_from_latex(tex_path):
        """Extracts and cleans text from a LaTeX file."""
        with open(tex_path, "r", encoding="utf-8") as file:
            latex_content = file.read()

        text = LatexNodes2Text().latex_to_text(latex_content)

        text = re.sub(r'\\[a-zA-Z]+\{.*?\}', '', text)
        text = re.sub(r'%.*', '', text)
        text = re.sub(r'[\t\r]', '', text)

        return text.strip()

    @staticmethod
    def extract(file_path):
        """Determines file type and extracts text accordingly."""
        if file_path.endswith(".pdf"):
            return Extractor.extract_from_pdf(file_path)
        elif file_path.endswith(".docx"):
            return Extractor.extract_from_docx(file_path)
        elif file_path.endswith(".tex"):
            return Extractor.extract_from_latex(file_path)
        else:
            raise ValueError("Unsupported file format")


class ExtractorAI:
    """Handles text parsing and extraction of editable parts using OpenAI API."""

    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def extract_editable_parts(self, text):
        """Uses OpenAI to extract editable parts from the text."""
        with open("promptExtract.txt", "r", encoding="utf-8") as file:
            prompt = file.read()

        prompt += f"</input_text_resume>{text}</>"

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message


class Generator:
    """Handles the generation of new descriptions based on extracted text and job descriptions."""

    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def generate_new_description(self, extracted_resume_text, job_description):
        """Generates a new description based on the extracted resume text and job description."""
        with open("generatePrompt.txt", "r", encoding="utf-8") as file:
            prompt = file.read()

        prompt += f"</job_description>{job_description}</>\n</resume_parts>{extracted_resume_text}</>"

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message

class Parser:
        
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)


    def replace_text(self, modified_data, extracted_data, text_positions):
        """
        Replaces extracted text with modified text at exact location.
        :param modified_data: Dictionary {original_text: modified_text}
        """

        for item in extracted_data:
            words = item["text"].split()

            for word in words:
                




            if original_text in text_positions:
                page_num, positions = text_positions[original_text]
                page = self.doc[page_num]

                for (x0, y0) in positions:
                    page.insert_text((x0, y0), "", fontsize=12, color=(1, 1, 1))

                x0, y0, _, _ = positions[0]
                page.insert_text((x0, y0), new_text, fontsize=12, color=(0, 0, 0))

        output_pdf = self.pdf_path.replace(".pdf", "_modified.pdf")
        self.doc.save(output_pdf)
        self.doc.close()

        return output_pdf


if __name__ == "__main__":
    API_KEY = ""

    extractor = Extractor()
    extractorAI = ExtractorAI(api_key=API_KEY)
    generator = Generator(api_key=API_KEY)

    file_path = "resume_test.pdf"

    parser = Parser(file_path)

    extracted_resume_text = extractor.extract(file_path)
    text_positions = extractor.extract_text_with_positions(file_path)
    print(f"Extracted text from resume: {extracted_resume_text}")

    editable_parts = json.loads(extractorAI.extract_editable_parts(extracted_resume_text))
    print(f"Editable parts: {editable_parts}")

    with open("description.txt", "r", encoding="utf-8") as file:
        job_description = file.read()

    generated_text = json.loads(generator.generate_new_description(editable_parts, job_description))
    print(f"Generated text from resume: {generated_text}")

    parser.replace_text(generated_text, editable_parts,text_positions)
