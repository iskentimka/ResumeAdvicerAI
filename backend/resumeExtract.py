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
import re

def save_docx_xml(docx_path, output_xml_path):
    """Extracts XML from a DOCX file and saves it to a .xml file."""
    with zipfile.ZipFile(docx_path, "r") as docx:
        xml_content = docx.read("word/document.xml").decode("utf-8")  # Extract XML

    # Save XML content to a file
    with open(output_xml_path, "w", encoding="utf-8") as xml_file:
        xml_file.write(xml_content)


def process_text_file(input_file: str, output_file: str):
    """
    Reads a text file, checks each line, and replaces empty or whitespace-only lines with '$'.
    Saves the modified content to a new file.
    
    :param input_file: Path to the input .txt file.
    :param output_file: Path to the output .txt file where the modified content will be saved.
    """
    with open(input_file, "r", encoding="utf-8") as infile:
        lines = infile.readlines()

    # Modify lines: If a line is empty or contains only spaces/newlines, replace it with "$"
    modified_lines = [line if line.strip() else "$\n" for line in lines]

    # Save the modified content to a new file
    with open(output_file, "w", encoding="utf-8") as outfile:
        outfile.writelines(modified_lines)


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


def is_any_letters(string: str) -> bool:
    """Checks if the string contains at least one letter (A-Z, a-z), '!' or '.'"""
    return bool(re.search(r"[a-zA-Z!.]", string))


# ------------------------------------------------------------------------------
# Single Class Combining All Functionality
# ------------------------------------------------------------------------------
class ResumeFormatter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.openai_client = OpenAI(api_key=api_key)

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
        if file_path.endswith(".tex"):
            return self.extract_from_latex(file_path)
        else:
            raise ValueError("Unsupported file format")

    def get_generated_new_text(self, extracted_data_path, job_description: str):
        """
        Uses OpenAI to generate new text for the entire extracted JSON data based on the job description.
        The prompt instructs the model to update the JSON array such that for each JSON object:
        - The "text" field is modified according to the job description.
        - The "paragraph" and "run" fields remain unchanged.
        The model is explicitly instructed to return only the JSON array, without any additional commentary.
        
        Returns:
            A list of dictionaries, each with keys "text", "paragraph", and "run" (with updated text).
        """
        import json

        # Read the prompt template from file.
        try:
            with open("generatePrompt.txt", "r", encoding="utf-8") as file:
                prompt_generate = file.read()
        except Exception as e:
            raise Exception(f"Could not read generatePrompt.txt: {str(e)}")

        # Read the prompt template from file.
        modified_lines_data_path = "resume_lineless.txt"
        process_text_file(extracted_data_path,modified_lines_data_path)
        try:
            with open(modified_lines_data_path, "r", encoding="utf-8") as file:
                extracted_data_text = file.read()
        except Exception as e:
            raise Exception(f"Could not read generatePrompt.txt: {str(e)}")
        # Build a single prompt that includes the job description and the whole extracted JSON.
        # Note the final instruction "Return only the JSON array" to force a pure JSON output.
        prompt = (
            prompt_generate +
            "\n\nJob Description:\n" + job_description +
            "\n\nExtracted text file:\n" + extracted_data_text
        )
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        generated_response = response.choices[0].message.content.strip()    
        if not generated_response:
            raise Exception("The generated response is empty. Check the prompt and API call.")
        
        # For safety, if the response is wrapped in code fences, extract the inner content.
        if generated_response.startswith("```json") and generated_response.endswith("```"):
            generated_response = generated_response[len("```json"): -3].strip()

        try:
            generated_data = json.loads(generated_response)
        except Exception as e:
            raise Exception(f"Failed to parse generated JSON: {str(e)}\nResponse was: {generated_response}")
        
        with open("generated_data.json", "w", encoding="utf-8") as json_file:
            json.dump(generated_data, json_file, indent=4)
        
        return generated_data

    def gelegate_resume_text(self, extracted_data_text_path : str, extract_data_json_path : str,)-> None:
        # Read the text from resume file.
        try:
            with open(extracted_data_text_path, "r", encoding="utf-8") as file:
                text = file.read()
        except Exception as e:
            raise Exception(f"Could not read extracted_data_text_path file: {str(e)}")
        
        # Read the delegate prompt from file.
        try:
            with open("delegate_prompt.txt", "r", encoding="utf-8") as file:
                prompt_base = file.read()
        except Exception as e:
            raise Exception(f"Could not read prompt file: {str(e)}")
        
        # Read the JSON with strings from file.
        try:
            with open(extract_data_json_path, "r", encoding="utf-8") as file:
                json_content = file.read()
        except Exception as e:
            raise Exception(f"Could not read prompt file: {str(e)}")

        extract_data = json.loads(json_content)

        skills = []
        projects = []
        experiences = []
        others = []
        
        for str in extract_data:
            if str['text'] == " " or str['text'] == "" or str['text'] == '\n' or is_any_letters(str['text']) == False: continue
            prompt = ( prompt_base + 
                "\n\ Text of resume:\n" + text + "\n"
                "SKILLS: " + ", ".join(item for item in skills) + "\n" +
                "PROJECTS: " + ", ".join(item for item in projects) + "\n" +
                "EXPERIENCE: " + ", ".join(item for item in experiences) + "\n" +
                "OTHER: " + ", ".join(item for item in others) +
                "Given string: " + str['text'] + "\n" + 
                "Return only one word of SKILLS, PROJECTS, EXPERIENCE or OTHER\n"
            )
        
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            generated_response = response.choices[0].message.content.strip()

            if (generated_response == "SKILLS"): skills.append(str['text'])
            if (generated_response == "PROJECTS"): projects.append(str['text'])
            if (generated_response == "EXPERIENCE"): experiences.append(str['text'])
            if (generated_response == "OTHER"): others.append(str['text'])
        
        print(f"skills: {skills}")
        print(f"projects: {projects}")
        print(f"exps: {experiences}")
        print(f"others: {others}")


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
    

    
    def extract_text_to_json(self, docx_path: str, output_json_path: str, output_txt_path: str ) -> None:
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
        text = []
        
        for p_idx, paragraph in enumerate(document.paragraphs, start=1):
            for r_idx, run in enumerate(paragraph.runs, start=1):
                text.append(run.text)
                data.append({
                    "text": run.text,
                    "paragraph": p_idx,
                    "run": r_idx
                })
        
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # Save the extracted text into a TXT file
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(text)) 
        



if __name__ == "__main__":
    API_KEY = "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"
    formatter = ResumeFormatter(API_KEY)

    # Read the job description from file.
    with open("description.txt", "r", encoding="utf-8") as file:
        job_description = file.read()
    
    # ---------------- DOCX Example ----------------
    #save_docx_xml("resume_test.docx", "output.xml")
    json_output_path = "resume_text_with_runs.json"
    txt_output_path = "text_resume.txt"
    resume_path = "resume_test.docx"
    formatter.extract_text_to_json(resume_path, json_output_path, txt_output_path)
    formatter.get_generated_new_text(txt_output_path,job_description)
    
    
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