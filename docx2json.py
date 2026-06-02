from os import write
import os
from pathlib import Path
import re
import json
from docx2python import docx2python
import re
import json
import sys 

import sys

sys.stdout.reconfigure(encoding='utf-8')



class DocxProcessor:
    def __init__(self, docx_path):
        self.docx_path = docx_path
        self.questions = []

    def run(self):
        self.extract_questions()

    def create_working_directory(self, docx_path):
        pass

    def map_answers(self, questions, answers_path=None):
        if answers_path is None:
            return
        try:
            with open(answers_path, 'r', encoding='utf-8') as f:
                answers_data = json.load(f)
                # Create a mapping of question numbers to answers
                for q in questions:
                    qno = q.get('qno')
                    if qno is not None:
                        q['answer'] = answers_data.get(str(qno))  # Assuming answers_data is a dict with qno as keys
                        
                return True
        except FileNotFoundError:
            print(f"File not found: {answers_path}")
        except json.JSONDecodeError:
            print(f"Invalid JSON in file: {answers_path}")

    def extract_questions(self, docx_path):
        questions = []

        # set working folder
        # folder = input("Enter file folder: ")
        folder = os.path.join("./", "outputs")

        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"Folder '{folder}' created successfully.")
        else:
            print(f"Folder '{folder}' already exists.")

        # read docx document
        document = docx2python(docx_path)
        # print(dir(document))
        # save images to current directory
        with docx2python(docx_path) as docx_content:
            # os.makedirs(f'{folder}/images/')
            docx_content.save_images(f"./{folder}/images/")

        # get document body
        # print(document.body[2])
        module_name = None
        course_name = None
        department = None
        course_code = None
        university = None 
        faculty = None
        exam_year = None
        qno = 0
        # print(document.body[0][0][0])
        # print(document.body[1][0][0])
        # print(document.body[2][0][0])
        # print(dir(document))
        # print(document.)

        print("processing conversion....")
        for section in document.body:
            # print("----section---")
            for page in section:
                # print('-----page----')
                for paragraphs in page:
                    question = {}
                    options = []

                    # print("--------paragraph------")
                    # print(paragraphs)
                    for line in paragraphs:
                        # print(line)
                        line = line.strip()
                        try:
                            if 'answer key' in line.strip().lower():
                                break

                            if not line or len(line.strip()) < 2 :
                                continue

                            # check if the line is a numbered bullet
                            if re.match(r'^\d+[.)]', line):
                                # print("question:", line)
                                pos = re.search(r'^\d+[.)]', line)
                                end_pos = pos.end()
                                # print(pos)
                                question = {'qno': qno+1, 'department': department, 'module': module_name, 'course': course_name, 'content': line.strip()[end_pos:], 'options': [], 'image': None, 'answer': None}
                                # # options = []
                                questions.append(question)
                                qno += 1
                                # continue

                            # elif re.match(r'^\(?[A-Za-z]\)[ \t]*|^[A-Za-z][.)][ \t]*', line):
                            elif re.match(r'^(?:\([A-Za-z]\)|[A-Za-z][.)])\s*', line):
                                # if questions[qno-1].get('options') is None:
                                #     questions[qno-1]['options'] = []
                                found_image_path = None
                                image_name=None
                                if ('image' in line):
                                    # pos1 = line.find('/')
                                    # pos2 = line.find('.')
                                    # image_name = line[pos1+1:pos2+2]
                                    image_token_pattern = re.compile(r'----media/([^-\s]+)----|\[\[\[\[([^\]\s]+)\]\]\]\]') 
                                    image_match = image_token_pattern.search(line)
                                    if image_match: 
                                        image_name = image_match.group(1) if image_match.group(1) else image_match.group(2)
                                        found_image_path = os.path.join("images/", image_name)
                                
                                        # image_name = line[pos1+1:pos2+2]
                                        # questions[qno-1]['image'] = found_image_path
                                # print(f"Image placeholder: {line}")
                                # continue

                                pos = re.search(r'^[(A-Za-z][.)]|[A-Za-z][.)]', line)
                                end_pos = 0
                                
                                if pos is  not None:
                                    # continue    
                                    end_pos = pos.end()
                                option_label = line[1] if line.startswith('(') else line[0]
                                option_content = line[end_pos:].strip()

                                option = {'label': option_label, 'content': option_content, 'image': found_image_path}
                                questions[qno-1]['options'].append(option)
                                
                                # continue

                            elif "IMAGE" in line.upper():
                                # question['image'].append(line)
                                if qno == 0:
                                    continue
                                pos1 = line.find('/')
                                pos2 = line.find('.')
                                # Captures 'image39.png' out of either: ----media/image39.png----  OR  [[[[image39.png]]]]
                                image_token_pattern = re.compile(r'----media/([^-\s]+)----|\[\[\[\[([^\]\s]+)\]\]\]\]') 
                                image_match = image_token_pattern.search(line)
                                if image_match: 
                                    image_name = image_match.group(1) if image_match.group(1) else image_match.group(2)
                                    found_image_path = os.path.join("images/", image_name)
                            
                                    # image_name = line[pos1+1:pos2+2]
                                    questions[qno-1]['image'] = found_image_path
                                # print(f"Image placeholder: {line}")
                                # continue

                            elif line.lower().startswith('answer'):
                                pos = line.find(':')
                                # answer = line[pos+1]
                                answer = line.strip().split(':')
                                if (len(answer) > 1):
                                    questions[qno-1]['answer'] = answer[1]
                                    # print(line)
                            
                            # Extract metadata (e.g., course name, module name)
                            elif line.lower().startswith('course name'):
                                course_name = line.split(':', 1)[1].strip()
                                # questions[qno-1]['course'] = course_name
                                # print(f"Course Name: {course_name}")

                            elif line.lower().startswith('module name'):
                                module_name = line.split(':', 1)[1].strip()
                                # questions[qno-1]['module'] = module_name
                                # print(f"Module Name: {module_name}")
                            elif line.lower().startswith('department'):
                                department = line.split(':', 1)[1].strip()
                                # print(f"Department: {department}")
                                # questions[qno-1]['department'] = department

                            elif line.lower().startswith('course code'):
                                if (len(line.split(':', 1)) > 0):
                                    course_code = line.split(':', 1)[1].strip()

                                # print(f"Course Code: {course_code}")
                                # questions[qno-1]['course_code'] = course_code
                                
                            elif line.lower().startswith('university'):
                                pass
                                # university = line.split(':', 1)[1].strip()
                                # print(f"University: {university}")

                            elif line.lower().startswith('faculty'):
                                faculty = line
                                # faculty = line.split(':', 1)[1].strip()
                                # print(f"Faculty: {faculty}")
                            elif line.lower().startswith('exam year'):
                                pass
                                # exam_year = line.split(':', 1)[1].strip()
                                # print(f"Exam Year: {exam_year}")
                        
                            else:
                                continue
                                # print("TEXT, {}".format(qno), line)
                                
                        except Exception as e:
                            print(e)
                            raise e

        # befire saving, map answers if answer key file is provided
        docx_dir = Path(docx_path).parent
        answers_path = os.path.join(docx_dir, 'answers.json')
        self.map_answers(questions, answers_path=answers_path)

        # saving questions.json
        with open(os.path.join(folder, 'questions.json'), 'w') as file:
            print("Dumping data to json format...")
            json.dump(questions, file)


    def extract_bullets(self, docx_path):
        # Extract text from the .docx file
        doc_content = docx2python(docx_path)

        # print(doc_content.text.split())
        # for line in doc_content.body:
        #    if re.match(r"^\d+\)", line):
        #        print(line)
        # print(doc_content.body)
        
        for name, image in doc_content.images.items():
            with open(name, 'wb') as image_destination:
                image_destination.write(image)


        # Flatten text from the extracted structure
        text = "\n".join(["\n".join(paragraph) for section in doc_content.body for table in section for row in table for paragraph in row])

        
        # Define regex patterns for numbered and lettered bullets
        numbered_bullet_pattern = r"^\d+\)"   # Matches "1)", "2)", etc.
        lettered_bullet_pattern = r"^[A-Z]\)"  # Matches "A)", "B)", etc.

        numbered_bullets = []
        lettered_bullets = []

        # Iterate through each line and classify bullets
        for line in text.split("\n"):
            line = line.strip()  # Remove unnecessary spaces
            if re.match(numbered_bullet_pattern, line):
                numbered_bullets.append(line)
            elif re.match(lettered_bullet_pattern, line):
                lettered_bullets.append(line)

        return numbered_bullets, lettered_bullets


if __name__=='__main__':
    # docx_path = "sample.docx"

    if len(sys.argv) != 2:
        print("You have to enter name of docx file ")
        sys.exit(0)
    else:
        docx_path = f"./{sys.argv[1]}.docx"

        engine = DocxProcessor(docx_path)
        engine.extract_questions(docx_path)
        # call extract questions function
        # extract_questions(docx_path=docx_path)

        print("json file saved to {}.json".format(sys.argv[1]))

