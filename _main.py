import os
import re
import json
import sys 
from pathlib import Path
from docx2python import docx2python

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QPushButton, QFileDialog, QLineEdit, QProgressBar, 
    QFrame, QTextEdit, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextCursor

from pathlib import Path 
from docx2python import DocxProcessor

sys.stdout.reconfigure(encoding='utf-8')

# =====================================================================
# BACKGROUND PROCESSING WORKER ENGINE 
# =====================================================================
class DocumentExtractorWorker(QThread):
    """
    Asynchronously parses the target .docx using the external engine rules,
    saves integrated imagery, and formats JSON payloads without blocking 
    the primary user interface thread.
    """
    progress_status = Signal(str)
    progress_percentage = Signal(int)
    extraction_complete = Signal(str, int)  # Output folder path, total questions found
    extraction_failed = Signal(str)

    def __init__(self, docx_path, text_answer_path):
        super().__init__()
        self.docx_path = os.path.normpath(docx_path)
        self.text_answer_path = os.path.normpath(text_answer_path)

    def map_answers(self, questions, answers_path=None):
        answers_path=self.answer_text2jon(self.text_answer_path)

        if answers_path is None:
            print("answers not found")
            return
        try:
            # first convert text answers to json
            # self.answer_text2jon(self.text_answer_path)
            
            print("....Mapping answer....")
            with open(answers_path, 'r', encoding='utf-8') as f:
                answers_data = json.load(f)
                for q in questions:
                    qno = q.get('qid')
                    if qno is not None:
                        q['answer'] = answers_data.get(str(qno))
                        # print(f"answer to {qno} is set {q['answer']}")
                return True
        except FileNotFoundError:
            self.progress_status.emit(f"[WARNING]: Answer key file not found: {answers_path}")
        except json.JSONDecodeError:
            self.progress_status.emit(f"[WARNING]: Invalid JSON structural format in: {answers_path}")
    
    def answer_text2jon(self, source=None):
        try:
            source_path = Path(source)
            result = {}
            with open(source_path, 'r') as file:
                data = file.read()

                # Split by whitespace
                tokens = data.split()

                # Convert into dictionary
                # result = {}
                for i in range(0, len(tokens), 2):
                    qno = tokens[i]
                    label = tokens[i+1]
                    result[int(qno)] = label

            # Save to JSON file
            answers_output_path = Path(self.docx_path).parent /"outputs" / "answers.json"
            with open(answers_output_path, "w") as f:
                json.dump(result, f, indent=2)

            print("✅ Conversion complete! Saved as answers.json")
            return answers_output_path

        except Exception as e:
            raise e

    def run(self):
        try:
            self.progress_percentage.emit(10)
            self.progress_status.emit("Initializing targeted input file structures...")


            questions = []
            source_path = Path(self.docx_path).resolve()
            folder = os.path.join(source_path.parent, "outputs")

            if not os.path.exists(folder):
                os.makedirs(folder)
                self.progress_status.emit(f"Folder '{folder}' created successfully.")
            else:
                self.progress_status.emit(f"Folder '{folder}' already exists.")

            self.progress_percentage.emit(25)
            self.progress_status.emit("Extracting binary images from archive layers...")

            with docx2python(self.docx_path) as docx_content:
                images_folder = os.path.join(folder, "images")
                if not os.path.exists(images_folder):
                    os.makedirs(images_folder)
                docx_content.save_images(images_folder)

            document = docx2python(self.docx_path)

            module_name = None
            course_name = None
            department = None
            course_code = None
            faculty = None
            qno = 0

            self.progress_percentage.emit(45)
            self.progress_status.emit("Processing structure conversion parsing paragraphs...")

            body_sections = document.body
            for s_idx, section in enumerate(body_sections):
                self.progress_percentage.emit(45 + int((s_idx / max(1, len(body_sections))) * 45))
                
                for page in section:
                    for paragraphs in page:
                        for line in paragraphs:
                            line = line.strip()
                            try:
                                if 'answer key' in line.lower():
                                    break

                                if not line or len(line.strip()) < 2:
                                    continue

                                if re.match(r'^\d+[.)]', line):
                                    pos = re.search(r'^\d+[.)]', line)
                                    end_pos = pos.end()
                                    question = {
                                        'qid': qno + 1, 
                                        'department': department, 
                                        'module': module_name, 
                                        'course': course_name, 
                                        'content': line.strip()[end_pos:], 
                                        'options': [], 
                                        'image': None, 
                                        'answer': None
                                    }
                                    questions.append(question)
                                    qno += 1

                                elif re.match(r'^(?:\([A-Za-z]\)|[A-Za-z][.)])\s*', line):
                                    found_image_path = None
                                    image_name = None
                                    if 'image' in line:
                                        image_token_pattern = re.compile(r'----media/([^-\s]+)----|\[\[\[\[([^\]\s]+)\]\]\]\]') 
                                        image_match = image_token_pattern.search(line)
                                        if image_match: 
                                            image_name = image_match.group(1) if image_match.group(1) else image_match.group(2)
                                            found_image_path = os.path.join("images/", image_name)
                                    
                                    pos = re.search(r'^[(A-Za-z][.)]|[A-Za-z][.)]', line)
                                    end_pos = 0
                                    if pos is not None:
                                        end_pos = pos.end()
                                    option_label = line[1] if line.startswith('(') else line[0]
                                    option_content = line[end_pos:].strip()

                                    option = {'label': option_label, 'content': option_content, 'image': found_image_path}
                                    if qno > 0:
                                        questions[qno - 1]['options'].append(option)

                                elif "IMAGE" in line.upper():
                                    if qno == 0:
                                        continue
                                    image_token_pattern = re.compile(r'----media/([^-\s]+)----|\[\[\[\[([^\]\s]+)\]\]\]\]') 
                                    image_match = image_token_pattern.search(line)
                                    if image_match: 
                                        image_name = image_match.group(1) if image_match.group(1) else image_match.group(2)
                                        found_image_path = os.path.join("images/", image_name)
                                        questions[qno - 1]['image'] = found_image_path

                                elif line.lower().startswith('answer'):
                                    if qno == 0:
                                        continue
                                    answer = line.strip().split(':')
                                    if len(answer) > 1:
                                        questions[qno - 1]['answer'] = answer[1].strip()

                                elif line.lower().startswith('course name'):
                                    course_name = line.split(':', 1)[1].strip()
                                elif line.lower().startswith('module name'):
                                    module_name = line.split(':', 1)[1].strip()
                                elif line.lower().startswith('department'):
                                    department = line.split(':', 1)[1].strip()
                                elif line.lower().startswith('course code'):
                                    if len(line.split(':', 1)) > 1:
                                        course_code = line.split(':', 1)[1].strip()
                                elif line.lower().startswith('faculty'):
                                    faculty = line
                                else:
                                    continue
                                    
                            except Exception as inside_e:
                                raise inside_e

            docx_dir = Path(self.docx_path).parent
            answers_path = os.path.join(docx_dir, 'answers.json')
            self.map_answers(questions, answers_path=answers_path)

            self.progress_percentage.emit(95)
            self.progress_status.emit("Dumping mapped data to structured json formatting layouts...")

            output_json_path = os.path.join(folder, 'questions.json')
            with open(output_json_path, 'w', encoding='utf-8') as file:
                json.dump(questions, file, ensure_ascii=False, indent=4)

            self.progress_percentage.emit(100)
            self.extraction_complete.emit(folder, qno)

        except Exception as e:
            self.extraction_failed.emit(str(e))


# =====================================================================
# CORE VISUAL DASHBOARD DESIGN CANVAS (WITH VALIDATION INTERFACE)
# =====================================================================
class DocumentConverterPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Academic Asset Processing Suite")
        self.resize(800, 650)
        self.worker = None
        self.auto_target_json = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header Logo Banner
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_lay = QVBoxLayout(header_frame)
        header_lay.setContentsMargins(16, 16, 16, 16)
        
        title = QLabel("Docx Exam Parsing Engine")
        title.setStyleSheet("color: #0f172a; font-size: 22px; font-weight: 800;")
        desc = QLabel("Transform and validate structured assessment sheets into normalized, machine-readable datasets.")
        desc.setStyleSheet("color: #64748b; font-size: 13px;")
        
        header_lay.addWidget(title)
        header_lay.addWidget(desc)
        layout.addWidget(header_frame)

        # Extraction Fields Panel
        form_frame = QFrame()
        form_frame.setObjectName("FormFrame")
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)

        self.input_display = QLineEdit()
        self.input_display.setPlaceholderText("Target file track map path...")
        self.input_display.setReadOnly(True)

        self.input_answers = QLineEdit()
        self.input_answers.setPlaceholderText("Target file answers (.txt)...")
        self.input_answers.setReadOnly(True)

        
        btn_browse = QPushButton("📁 Browse Docx")
        btn_browse.clicked.connect(self.select_source_document)
        btn_browse.setStyleSheet("""
            QPushButton { background-color: #2563eb; color: white; padding: 6px 14px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #1d4ed8; }
        """)

        btn_browse2 = QPushButton("📁 Browse .txt")
        btn_browse2.clicked.connect(self.select_source_answers)
        btn_browse2.setStyleSheet("""
            QPushButton { background-color: #2563eb; color: white; padding: 6px 14px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #1d4ed8; }
        """)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input_display, stretch=1)
        input_row.addWidget(btn_browse)

        answer_input_row  = QHBoxLayout()
        answer_input_row.addWidget(self.input_answers, stretch=1)
        answer_input_row.addWidget(btn_browse2)

        self.output_display = QLineEdit()
        self.output_display.setPlaceholderText("Auto-generated directory target path profile location...")
        self.output_display.setReadOnly(True)
        self.output_display.setStyleSheet("background-color: #f8fafc; color: #64748b;")

        form_layout.addRow("Source Assessment File:", input_row)
        form_layout.addRow("Source Answer text File: ", answer_input_row)
        form_layout.addRow("Configured Output Path Target:", self.output_display)
        layout.addWidget(form_frame)

        # Added UI Component: Independent Validation File Panel
        val_frame = QFrame()
        val_frame.setObjectName("ValidationFrame")
        val_layout = QFormLayout(val_frame)
        val_layout.setContentsMargins(16, 16, 16, 16)
        val_layout.setSpacing(12)

        self.val_input_display = QLineEdit()

        self.val_input_display.setPlaceholderText("Select questions.json file to validate...")
        self.val_input_display.setReadOnly(True)

        btn_val_browse = QPushButton("📁 Select JSON")
        btn_val_browse.clicked.connect(self.select_validation_json)
        btn_val_browse.setStyleSheet("""
            QPushButton { background-color: #64748b; color: white; padding: 6px 14px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #475569; }
        """)

        val_row = QHBoxLayout()
        val_row.addWidget(self.val_input_display, stretch=1)
        val_row.addWidget(btn_val_browse)

        self.btn_validate = QPushButton("🔍 Validate Dataset Schema")
        self.btn_validate.setEnabled(False)
        self.btn_validate.clicked.connect(self.run_schema_validation)
        self.btn_validate.setStyleSheet("""
            QPushButton { background-color: #8b5cf6; color: white; padding: 6px 14px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #7c3aed; }
            QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
        """)
        val_row.addWidget(self.btn_validate)

        val_layout.addRow("Validation Checklist File:", val_row)
        layout.addWidget(val_frame)

        # Logger Canvas
        self.logger_canvas = QTextEdit()
        self.logger_canvas.setReadOnly(True)
        self.logger_canvas.setPlaceholderText("Console notification logs display module stream pipeline...")
        self.logger_canvas.setObjectName("ConsoleLogger")
        layout.addWidget(self.logger_canvas, stretch=1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress_bar)

        self.btn_execute = QPushButton("⚡ Execute Parsing Operations Pipeline")
        self.btn_execute.setEnabled(False)
        self.btn_execute.clicked.connect(self.start_conversion_pipeline)
        self.btn_execute.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; padding: 12px; font-size: 14px; font-weight: bold; border-radius: 6px; }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
        """)
        layout.addWidget(self.btn_execute)

        # Stylesheet styling updates
        self.setStyleSheet("""
            QWidget { background-color: #f1f5f9; font-family: 'Segoe UI', Arial, sans-serif; }
            QFrame#HeaderFrame, QFrame#FormFrame, QFrame#ValidationFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 6px;
                color: #334155;
                font-size: 13px;
                background-color: #ffffff;
            }
            QTextEdit#ConsoleLogger {
                background-color: #0f172a;
                color: #38bdf8;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 8px;
            }
            QProgressBar {
                border: 1px solid #cbd5e1;
                background-color: #e2e8f0;
                border-radius: 6px;
                height: 20px;
                color: #0f172a;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 5px;
            }
            QLabel { color: #334155; font-weight: 500; font-size: 13px; }
        """)

    def select_source_document(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Identify Target Examination File", "", "Word Documents (*.docx)")
        if file_path:
            self.input_display.setText(file_path)
            base_dir = os.path.dirname(file_path)
            target_out_path = os.path.join(base_dir, "outputs")
            self.output_display.setText(target_out_path)
            self.auto_target_json = os.path.join(target_out_path, "questions.json")
            
            self.btn_execute.setEnabled(True)
            self.log_html("<span style='color: #a7f3d0;'>[SYSTEM]: Registered input file stream: '" + os.path.basename(file_path) + "'</span>")
            self.log_html("<span style='color: #cbd5e1;'>[SYSTEM]: Output folder mapped to: '" + target_out_path + os.sep + "'</span>")

    def select_source_answers(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Identify Target Examination File answers", "", "Text file (*.txt)")

        if file_path:
            self.input_answers.setText(file_path)
            base_dir = os.path.dirname(file_path)
            target_out_path = os.path.join(base_dir, "outputs")
            self.output_display.setText(target_out_path)
            self.auto_target_json = os.path.join(target_out_path, "questions.json")
            
            self.btn_execute.setEnabled(True)
            self.log_html("<span style='color: #a7f3d0;'>[SYSTEM]: Registered input file stream: '" + os.path.basename(file_path) + "'</span>")
            self.log_html("<span style='color: #cbd5e1;'>[SYSTEM]: Output folder mapped to: '" + target_out_path + os.sep + "'</span>")

    def select_validation_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Identify Target Dataset Schema", "", "JSON Files (*.json)")
        if file_path:
            self.val_input_display.setText(file_path)
            self.btn_validate.setEnabled(True)
            self.log_html("<span style='color: #c084fc;'>[SYSTEM]: Validation target redirected to: '" + os.path.basename(file_path) + "'</span>")

    def log_html(self, html_text):
        self.logger_canvas.append(html_text)
        self.logger_canvas.moveCursor(QTextCursor.End)

    def start_conversion_pipeline(self):
        docx_target = self.input_display.text()
        text_ansewrs = self.input_answers.text()

        if not docx_target or not os.path.exists(docx_target):
            return

        self.btn_execute.setEnabled(False)
        self.btn_validate.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_html("<br><span style='color: #38bdf8; font-weight: bold;'>--- Starting Extraction Sequence ---</span>")

        self.worker = DocumentExtractorWorker(docx_target, text_ansewrs)
        self.worker.progress_status.connect(lambda msg: self.log_html(f"<span style='color: #94a3b8;'>[PROCESS]: {msg}</span>"))
        self.worker.progress_percentage.connect(self.progress_bar.setValue)
        self.worker.extraction_complete.connect(self.handle_pipeline_success)
        self.worker.extraction_failed.connect(self.handle_pipeline_error)
        self.worker.start()

    def handle_pipeline_success(self, target_path, count):
        self.log_html("<br><span style='color: #4ade80; font-weight: bold;'>[SUCCESS]: Matrix transformations executed successfully!</span>")
        self.log_html(f"<span style='color: #4ade80;'>[SUCCESS]: Generated {count} normalized schema records inside:</span>")
        self.log_html(f"           📁 {target_path}{os.sep}questions.json")
        self.btn_execute.setEnabled(True)
        
        # Automatically load generated target paths into the validation field layout
        if os.path.exists(self.auto_target_json):
            self.val_input_display.setText(self.auto_target_json)
            self.btn_validate.setEnabled(True)
            # Run background schema auto-audit checklist instantly
            self.run_schema_validation()

    def handle_pipeline_error(self, message):
        self.log_html(f"<br><span style='color: #f87171; font-weight: bold;'>[CRITICAL ERROR]: Pipeline execution faulted: {message}</span>")
        self.progress_bar.setValue(0)
        self.btn_execute.setEnabled(True)
        self.btn_validate.setEnabled(True)

    # UI Conversion of terminal schema audit functions
    def run_schema_validation(self):
        file_path = self.val_input_display.text()
        if not file_path or not os.path.exists(file_path):
            self.log_html(f"<span style='color: #f87171;'>[ERROR]: Targeted validation file path does not exist: '{file_path}'</span>")
            return

        self.log_html("<br><span style='color: #c084fc; font-weight: bold;'>==================================================</span>")
        self.log_html(f"<span style='color: #c084fc; font-weight: bold;'>🔬 Starting Validation Audit Checklist on: {os.path.basename(file_path)}</span>")
        self.log_html("<span style='color: #c084fc; font-weight: bold;'>==================================================</span>")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.log_html(f"<span style='color: #f87171; font-weight: bold;'>[CRITICAL ERROR]: File is not a valid JSON string layout! Details: {e}</span>")
            return

        if not isinstance(data, list):
            self.log_html("<span style='color: #f87171; font-weight: bold;'>[CRITICAL ERROR]: Root element is not a JSON list container []!</span>")
            return

        total_records = len(data)
        errors_count = 0
        warnings_count = 0
        self.log_html(f"<span style='color: #cbd5e1;'>Found total payload records: {total_records}</span><br>")

        for idx, item in enumerate(data):
            q_identifier = item.get('qid') if isinstance(item, dict) and item.get('qid') is not None else f"Index {idx}"
            prefix_context = f"Question No. {q_identifier}:"

            if not isinstance(item, dict):
                self.log_html(f"<span style='color: #f87171;'>[ERROR] {prefix_context} Structure block entry is not an object node!</span>")
                errors_count += 1
                continue

            # Warning Checks (Metadata fields tracking)
            missing_meta = []
            if not item.get('department') or str(item['department']).strip().lower() == "none":
                missing_meta.append("department")
            if not item.get('module') or str(item['module']).strip().lower() == "none":
                missing_meta.append("module")
            if not item.get('course') or str(item['course']).strip().lower() == "none":
                missing_meta.append("course")

            if missing_meta:
                meta_str = ", ".join(missing_meta)
                self.log_html(f"<span style='color: #fbbf24;'>[WARNING] {prefix_context} Metadata fields are null/unset -&gt; [{meta_str}]</span>")
                warnings_count += 1

            # Core Error Validation Layout Rules
            content = item.get('content')
            if content is None or (isinstance(content, str) and not content.strip()):
                self.log_html(f"<span style='color: #f87171;'>[ERROR] {prefix_context} Question 'content' text body is completely empty/null!</span>")
                errors_count += 1

            answer = item.get('answer')
            if answer is None or (isinstance(answer, str) and not answer.strip()) or str(answer).strip().lower() == "none":
                self.log_html(f"<span style='color: #f87171;'>[ERROR] {prefix_context} Crucial field 'answer' key cannot be null or unset!</span>")
                errors_count += 1

            options = item.get('options')
            if not isinstance(options, list):
                self.log_html(f"<span style='color: #f87171;'>[ERROR] {prefix_context} 'options' wrapper missing or formatted incorrectly (not a list)!</span>")
                errors_count += 1
                continue

            if len(options) == 0:
                self.log_html(f"<span style='color: #f87171;'>[ERROR] {prefix_context} Options collection list is empty! Requires A-D items.</span>")
                errors_count += 1
                continue

            found_labels = []
            for opt_idx, opt in enumerate(options):
                if not isinstance(opt, dict):
                    self.log_html(f"<span style='color: #f87171;'>[ERROR] {prefix_context} Option index {opt_idx} is corrupted (not an object block)!</span>")
                    errors_count += 1
                    continue
                
                label = str(opt.get('label', '')).strip().upper()
                if label:
                    found_labels.append(label)
                    
                opt_content = opt.get('content')
                if opt_content is None or (isinstance(opt_content, str) and not opt_content.strip()):
                    self.log_html(f"<span style='color: #f87171;'>[ERROR] {prefix_context} Option ({label or opt_idx}) text value content is empty/null!</span>")
                    errors_count += 1

            expected_labels = ["A", "B", "C", "D"]
            if found_labels != expected_labels:
                joined_found = ", ".join(found_labels) if found_labels else "None"
                self.log_html(f"<span style='color: #f87171;'>[ERROR] {prefix_context} Broken choice scheme labels. Found: [{joined_found}]. Expected exactly: [A, B, C, D]</span>")
                errors_count += 1

        # Summary Log Generation Block
        self.log_html("<br><span style='color: #c084fc; font-weight: bold;'>==================================================</span>")
        self.log_html("<span style='color: #ffffff; font-weight: bold;'>📋 FINAL SCHEMA AUDIT REPORT SUMMARY</span>")
        self.log_html("<span style='color: #c084fc; font-weight: bold;'>==================================================</span>")
        self.log_html(f"<span style='color: #cbd5e1;'>Total Exam Items Audited : {total_records}</span>")
        
        if warnings_count > 0:
            self.log_html(f"<span style='color: #fbbf24;'>Total Warnings Flagged    : {warnings_count}</span>")
        else:
            self.log_html("<span style='color: #34d399;'>Total Warnings Flagged    : 0 (Clean metadata!)</span>")

        if errors_count > 0:
            self.log_html(f"<span style='color: #f87171; font-weight: bold;'>Total Errors Found       : {errors_count}</span>")
            self.log_html("<span style='color: #f87171; font-weight: bold;'><br>❌ VALIDATION STATUS: FAILED. Please fix data constraints before proceeding.</span>")
        else:
            self.log_html("<span style='color: #34d399; font-weight: bold;'>Total Errors Found       : 0</span>")
            self.log_html("<span style='color: #34d399; font-weight: bold;'><br>✔ VALIDATION STATUS: PASSED! JSON conforms cleanly to structural requirements.</span>")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DocumentConverterPage()
    window.show()
    sys.exit(app.exec())