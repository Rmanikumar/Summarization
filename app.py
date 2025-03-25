from flask import Flask, request, jsonify, render_template
import os
import pdfplumber
import pytesseract
from PIL import Image
import re

app = Flask(__name__)

headings_and_content = []

def extract_text_from_pdf(pdf_path):
    headings_and_content = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                process_text(text, headings_and_content)
            else:
                page_image = page.to_image()
                ocr_text = pytesseract.image_to_string(page_image)
                process_text(ocr_text, headings_and_content)

    return headings_and_content

def process_text(text, headings_and_content):
    lines = text.split("\n")
    current_heading = None
    current_content = []

    for line in lines:
        line = line.strip()
        
        if line.isupper() or len(line.split()) <= 5:
            if current_heading:
                headings_and_content.append((current_heading, " ".join(current_content)))
            current_heading = line
            current_content = []
        else:
            current_content.append(line)

    if current_heading:
        headings_and_content.append((current_heading, " ".join(current_content)))

def clean_question(question):
    return re.sub(r'^(what is|what are|define|explain)\s+', '', question, flags=re.IGNORECASE).strip()

def find_answer_below_heading(question):
    cleaned_question = clean_question(question)

    for index, (heading, content) in enumerate(headings_and_content):
        if cleaned_question.lower() in heading.lower():
            answer_content = []
            answer_content.append(content)

            if index + 1 < len(headings_and_content):
                next_heading = headings_and_content[index + 1][0]
                next_content = headings_and_content[index + 1][1]
                answer_content.append(next_content)
            
            return " ".join(answer_content).strip()

    return "No matching heading found."

def get_first_pdf_from_folder(folder_path):
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.pdf'):
            return os.path.join(folder_path, filename)
    return None

@app.route('/')
def question():
    return render_template('question.html')

@app.route('/ask_question', methods=['POST'])
def ask_question():
    data = request.get_json()
    question = data.get('question', '')
    answer = find_answer_below_heading(question)
    return jsonify({'answer': answer})

if __name__ == "__main__":
    folder_path = "results/"  
    pdf_path = get_first_pdf_from_folder(folder_path)
    
    if pdf_path is None:
        print("No PDF files found in the specified folder.")
    else:
        headings_and_content.extend(extract_text_from_pdf(pdf_path))  
        print("Headings and content extracted successfully.")

    app.run(debug=True)
