from flask import Flask, request, render_template, send_file
import os
import PyPDF2
import spacy
from heapq import nlargest
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from textwrap import wrap
from werkzeug.utils import secure_filename
import re

app = Flask(__name__)

nlp = spacy.load('en_core_web_sm')

UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'pdf'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(RESULT_FOLDER):
    os.makedirs(RESULT_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + '\n'
    return text

def clean_text(text):
    return re.sub(r'[•►→✔✓■]', '', text)

def is_bold_line(line):
    return line.isupper() or line.endswith(':')

def summarize_text_by_headings(text):
    lines = clean_text(text).split('\n')
    summaries = {}
    current_heading = None
    current_text = []

    for line in lines:
        stripped_line = line.strip()

        if is_bold_line(stripped_line):
            if current_heading and current_text:
                summarized_text = summarize_text(' '.join(current_text))
                summaries[current_heading] = summarized_text
            
            current_heading = stripped_line
            current_text = []  
        elif current_heading:  
            current_text.append(stripped_line)

    if current_heading and current_text:
        summarized_text = summarize_text(' '.join(current_text))
        summaries[current_heading] = summarized_text

    return summaries

def summarize_text(text):
    doc = nlp(text)
    word_frequencies = {}
    stopwords = list(spacy.lang.en.stop_words.STOP_WORDS)

    for word in doc:
        if word.text.lower() not in stopwords and word.text.isalpha():
            word_frequencies[word.text] = word_frequencies.get(word.text, 0) + 1

    max_frequency = max(word_frequencies.values()) if word_frequencies else 1

    for word in word_frequencies:
        word_frequencies[word] = word_frequencies[word] / max_frequency

    sentence_tokens = [sent for sent in doc.sents]
    sentence_scores = {}
    for sent in sentence_tokens:
        for word in sent:
            if word.text.lower() in word_frequencies:
                sentence_scores[sent] = sentence_scores.get(sent, 0) + word_frequencies[word.text.lower()]

    select_length = max(1, int(len(sentence_tokens) * 0.3))
    summary_sentences = nlargest(select_length, sentence_scores, key=sentence_scores.get)
    
    final_summary = ' '.join([sent.text for sent in summary_sentences])
    return final_summary

def save_to_pdf(output_pdf_path, summarized_content):
    pdf = canvas.Canvas(output_pdf_path, pagesize=letter)
    pdf.setTitle("Summarized Document")

    width, height = letter
    margin = 1 * inch
    y_position = height - margin
    line_height = 14

    for heading, summary in summarized_content.items():
        if y_position < margin + 100:
            pdf.showPage()
            y_position = height - margin

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(margin, y_position, heading)
        y_position -= line_height * 1.5  

        pdf.setFont("Helvetica", 10)
        wrapped_summary = wrap(summary, width=80)

        y_position -= line_height  

        for line in wrapped_summary:
            if y_position < margin + 50:
                pdf.showPage()
                y_position = height - margin
            pdf.drawString(margin, y_position, line)
            y_position -= line_height

    pdf.save()

def clear_folders():
    for folder in [UPLOAD_FOLDER, RESULT_FOLDER]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            os.remove(file_path)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    clear_folders()  

    if 'file' not in request.files:
        return "No file part"
    file = request.files['file']
    if file.filename == '':
        return "No selected file"
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        output_pdf_path = os.path.join(app.config['RESULT_FOLDER'], f'summarized_{filename}')
        text = extract_text_from_pdf(file_path)
        summarized_content = summarize_text_by_headings(text)
        save_to_pdf(output_pdf_path, summarized_content)

        return {'output_pdf': f'summarized_{filename}'}

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['RESULT_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
