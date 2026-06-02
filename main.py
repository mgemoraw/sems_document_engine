import os
import re
import json
import sys 
from docx2python import docx2python

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QPushButton, QFileDialog, QLineEdit, QProgressBar, 
    QFrame, QTextEdit, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal

sys.stdout.reconfigure(encoding='utf-8')

# =====================================================================
# BACKGROUND PROCESSING WORKER ENGINE (FIXED PARSING EMPTY NESTED LISTS)
# =====================================================================
class DocumentExtractorWorker(QThread):
    """
    Asynchronously parses the target .docx data stream, saves integrated imagery,
    and formats JSON payloads without blocking the primary user interface thread.
    """
    progress_status = Signal(str)
    progress_percentage = Signal(int)
    extraction_complete = Signal(str, int)  # Output folder path, total questions found
    extraction_failed = Signal(str)

    def __init__(self, docx_path):
        super().__init__()
        self.docx_path = os.path.normpath(docx_path)

    def run(self):
        try:
            self.progress_percentage.emit(10)
            self.progress_status.emit("Initializing targeted input file structures...")

            # Enforce automatic outputs folder tree constraints
            base_directory = os.path.dirname(self.docx_path)
            output_folder = os.path.join(base_directory, "outputs")
            images_folder = os.path.join(output_folder, "images")
            
            os.makedirs(images_folder, exist_ok=True)
            
            self.progress_percentage.emit(25)
            self.progress_status.emit("Extracting binary images and math layers...")

            # Extract content cleanly using contextual blocks
            with docx2python(self.docx_path) as docx_content:
                docx_content.save_images(images_folder)
                html_body = docx_content.body

            self.progress_percentage.emit(45)
            self.progress_status.emit("Parsing paragraph runs and math nodes...")
            
            questions = []
            image_mappings = []
            module_name = None
            course_name = None
            department = None
            course_code = None
            qno = 0

            # Exact matching pattern to capture full filenames out of docx2python's '[[[[image1.png]]]]' tokens
            image_token_pattern = re.compile(r'----(image\d+\.[a-zA-Z0-9]+)----|\[\[\[\[(image\d+\.[a-zA-Z0-9]+)\]\]\]\]')

            # docx2python depth-4 tracking system normalization
            for s_idx, section in enumerate(html_body):
                self.progress_percentage.emit(45 + int((s_idx / max(1, len(html_body))) * 45))

                for page in section:
                    for paragraph in page:
                        for line_item in paragraph:
                            
                            # --- CRITICAL FIX HERE ---
                            # Instead of iterating over lists of objects, check if line_item is a list
                            # or join strings cleanly to ensure text formatting symbols are kept intact.
                            if isinstance(line_item, list):
                                line = " ".join([str(i).strip() for i in line_item if i]).strip()
                            else:
                                line = str(line_item).strip()
                            
                            if 'answer key' in line.lower():
                                break
                            if not line or len(line) < 2:
                                continue

                            # Look for image tokens in the current text block run
                            found_image = None
                            image_match = image_token_pattern.search(line)
                            if image_match:
                                # Capture group 1 or group 2 depending on token format used by docx2python version
                                found_image = image_match.group(1) or image_match.group(2)
                                line = image_token_pattern.sub(f" [Image: {found_image}] ", line).strip()

                            # --- 1. Question Line Detection ---
                            if re.match(r'^\d+[.)]', line):
                                pos = re.search(r'^\d+[.)]', line)
                                end_pos = pos.end()
                                question = {
                                    'qno': qno + 1, 
                                    'department': department, 
                                    'module': module_name, 
                                    'course': course_name, 
                                    'content': line[end_pos:].strip(), 
                                    'options': [], 
                                    'image': found_image,
                                    'answer': None
                                }
                                questions.append(question)
                                qno += 1

                            # --- 2. Option Entry Detection ---
                            elif re.match(r'^[A-Za-z][.)]', line):
                                if qno == 0:
                                    continue
                                pos = re.search(r'^[A-Za-z][.)]', line)
                                end_pos = pos.end()
                                option_label = line[0]
                                option_content = line[end_pos:].strip()

                                option = {
                                    'label': option_label, 
                                    'content': option_content, 
                                    'image': found_image  # Linked dynamically to the exact option paragraph
                                }

                                if found_image:
                                    image_mappings.append({
                                        "qno": qno,
                                        "option": option_label,
                                        "image": found_image
                                    })
                                questions[qno-1]['options'].append(option)

                            # --- 3. Standalone Image Placeholder ---
                            elif "[IMAGE" in line.upper() or found_image:
                                if qno == 0:
                                    continue

                                if found_image:
                                    image_mappings.append({
                                        "qno": qno,
                                        "image": found_image,
                                    })

                                if not questions[qno-1]['image']:
                                    questions[qno-1]['image'] = found_image

                            # --- 4. Answer Key Tracking ---
                            elif line.lower().startswith('answer'):
                                if qno == 0:
                                    continue
                                parts = line.split(':')
                                if len(parts) > 1:
                                    questions[qno-1]['answer'] = parts[1].strip()

                            # --- 5. Document Metadata Extraction ---
                            elif line.lower().startswith('course name'):
                                course_name = line.split(':', 1)[1].strip()
                            elif line.lower().startswith('module name'):
                                module_name = line.split(':', 1)[1].strip()
                            elif line.lower().startswith('department'):
                                department = line.split(':', 1)[1].strip()
                            elif line.lower().startswith('course code'):
                                if len(line.split(':', 1)) > 1:
                                    course_code = line.split(':', 1)[1].strip()

            self.progress_percentage.emit(95)
            self.progress_status.emit("Serializing JSON elements with math properties intact...")


            # Save structural output JSON map file
            image_index_path = os.path.join(output_folder, 'image_index.json')
            with open(image_index_path, 'w', encoding='utf-8') as img_file:
                json.dump(image_mappings, img_file, ensure_ascii=False, indent=4)

            json_out_path = os.path.join(output_folder, 'questions.json')
            with open(json_out_path, 'w', encoding='utf-8') as file:
                json.dump(questions, file, ensure_ascii=False, indent=4)

            self.progress_percentage.emit(100)
            self.extraction_complete.emit(output_folder, qno)

        except Exception as e:
            self.extraction_failed.emit(str(e))


# =====================================================================
# CORE VISUAL DASHBOARD DESIGN CANVAS
# =====================================================================
class DocumentConverterPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Academic Asset Processing Suite")
        self.resize(750, 550)
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Logo Banner
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_lay = QVBoxLayout(header_frame)
        header_lay.setContentsMargins(16, 16, 16, 16)
        
        title = QLabel("Docx Exam Parsing Engine")
        title.setStyleSheet("color: #0f172a; font-size: 22px; font-weight: 800;")
        desc = QLabel("Transform structured assessment forms into normalized, machine-readable datasets cleanly.")
        desc.setStyleSheet("color: #64748b; font-size: 13px;")
        
        header_lay.addWidget(title)
        header_lay.addWidget(desc)
        layout.addWidget(header_frame)

        # Fields (Input / Automated Output)
        form_frame = QFrame()
        form_frame.setObjectName("FormFrame")
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)

        self.input_display = QLineEdit()
        self.input_display.setPlaceholderText("Target file track map path...")
        self.input_display.setReadOnly(True)
        
        btn_browse = QPushButton("📁 Browse Docx")
        btn_browse.clicked.connect(self.select_source_document)
        btn_browse.setStyleSheet("""
            QPushButton { background-color: #2563eb; color: white; padding: 6px 14px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #1d4ed8; }
        """)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input_display, stretch=1)
        input_row.addWidget(btn_browse)

        self.output_display = QLineEdit()
        self.output_display.setPlaceholderText("Auto-generated directory target path profile location...")
        self.output_display.setReadOnly(True)
        self.output_display.setStyleSheet("background-color: #f8fafc; color: #64748b;")

        form_layout.addRow("Source Assessment File:", input_row)
        form_layout.addRow("Configured Output Path Target:", self.output_display)
        layout.addWidget(form_frame)

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

        # Stylesheet styling
        self.setStyleSheet("""
            QWidget { background-color: #f1f5f9; font-family: 'Segoe UI', Arial, sans-serif; }
            QFrame#HeaderFrame, QFrame#FormFrame {
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
            
            self.btn_execute.setEnabled(True)
            self.logger_canvas.append(f"[SYSTEM]: Registered input file stream: '{os.path.basename(file_path)}'")
            self.logger_canvas.append(f"[SYSTEM]: Output folder mapped to: '{target_out_path}{os.sep}'")

    def start_conversion_pipeline(self):
        docx_target = self.input_display.text()
        if not docx_target or not os.path.exists(docx_target):
            return

        self.btn_execute.setEnabled(False)
        self.progress_bar.setValue(0)
        self.logger_canvas.append("\n--- Starting Extraction Sequence ---")

        self.worker = DocumentExtractorWorker(docx_target)
        self.worker.progress_status.connect(lambda msg: self.logger_canvas.append(f"[PROCESS]: {msg}"))
        self.worker.progress_percentage.connect(self.progress_bar.setValue)
        self.worker.extraction_complete.connect(self.handle_pipeline_success)
        self.worker.extraction_failed.connect(self.handle_pipeline_error)
        self.worker.start()

    def handle_pipeline_success(self, target_path, count):
        self.logger_canvas.append(f"\n[SUCCESS]: Matrix transformations executed successfully!")
        self.logger_canvas.append(f"[SUCCESS]: Generated {count} normalized schema records inside:")
        self.logger_canvas.append(f"          📁 {target_path}{os.sep}questions.json")
        self.logger_canvas.append(f"          📁 {target_path}{os.sep}images{os.sep}")
        self.btn_execute.setEnabled(True)

    def handle_pipeline_error(self, message):
        self.logger_canvas.append(f"\n[CRITICAL ERROR]: Pipeline execution faulted: {message}")
        self.progress_bar.setValue(0)
        self.btn_execute.setEnabled(True)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DocumentConverterPage()
    window.show()
    sys.exit(app.exec())