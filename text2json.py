import csv
import json
import re
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path 
import os 
import sys 


sys.stdout.reconfigure(encoding='utf-8')

class Option(BaseModel):
    label: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None


class QuestionSchema(BaseModel):
    id: Optional[int] = None
    content: Optional[str] = None
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    module_id: Optional[int] = None
    options: Optional[List[Option]] = []
    image: Optional[str] = None
    answer: Optional[str] = None
    year: Optional[int] = None


class TextToJson:
    def __init__(self, text_file_path:None, department: None, exam_year=None):
        self._text_file_path = Path(text_file_path).resolve()
        self.department = department
        self.text_content = None

        if exam_year is None:
            self.exam_year = datetime.now().year
    
    def start_processing(self):
        questions = self.read()
        self.write_to_json(questions, "questions.json")
        print("Questions written to ")
        return True

    def save(self):
        json.dumps("questions.json")

    def read(self):
        if self._text_file_path is None:
            raise Exception("Input Files Error!")
        if self.department is None:
            raise Exception("Department Required")
        
        questions = []
        with open(self._text_file_path, 'r', encoding="utf-8", errors='ignore') as file:
            # self.text_content = file.readlines()
            lines = file.readlines()
            # print(self.text_content)

            question = {
                'qid': None,
                'department_id': None,
                'department_name': self.department,
                'course_code': None,
                'module_id': None,
                'year': self.exam_year,
                'image': None,
                'content': None,
                'options': [],
                'answer': None,
            }
            options =[]
            counter = 0
            for line in  lines:
                line = line.strip()
                # if re.match(r'^\d+[.)]', line):
                if re.match(r'^(?!\d+[.)])(?![A-Da-d][.)])(?!\([A-Da-d]\))(?!ANSWER\b).+', line):
                    line.strip()
                    re.IGNORECASE

                    # print("question:", line)
                    pos = re.search(r'^\d+[.)]', line)
                    if pos is not  None:   
                        end_pos = pos.end()
                        q_num_str = pos.group()
                        actual_q_num = int(q_num_str.rstrip('.)'))
                        content = line.strip()[end_pos:]
                    else:
                        # print(pos)
                        content = line.strip()
                        actual_q_num = None

                    question = {'qid': counter+1, "qno": actual_q_num, 'department': self.department, 'module': None, 'course': None, 'content': content, 'options': [], 'image': None, 'answer': None}
                    
                    questions.append(question)
                    counter += 1
                
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
                    
                    # for subline in line.split('\n'):
                    #     if not subline:
                    #         continue
                    pos = re.search(r'^[(A-Za-z][.)]|[A-Za-z][.)]', line)
                    end_pos = 0
                    
                    if pos is  not None:
                        # continue    
                        end_pos = pos.end()
                    option_label = line[1] if line.startswith('(') else line[0]
                    option_content = line[end_pos:].strip()

                    option = {'label': option_label, 'content': option_content, 'image': found_image_path}
                    questions[counter-1]['options'].append(option)
                
        
                elif line.startswith("ANSWER"):
                    pos = line.find(":")
                    answer = line[pos+1:].strip()[0]
                    questions[counter-1]['answer'] = answer
                    
                    


                    # reset questions
                    options = []
                    question = {
                        'qid': None,
                        'department_id': None,
                        'department_name': self.department,
                        'course_code': None,
                        'module_id': None,
                        'year': self.exam_year,
                        'image': None,
                        'content': None,
                        'options': [],
                        'answer': None,
                    }
                    # continue

            # save files
            return questions 
            # self.write_to_json(questions, "questions.json")

    def process_line(question, line, ):

        try:
               
            # check if the line is a numbered bullet
            if re.match(r'^\d+[.)]', line):
                # print("question:", line)
                pos = re.search(r'^\d+[.)]', line)
                end_pos = pos.end()
                q_num_str = pos.group()
                actual_q_num = int(q_num_str.rstrip('.)'))
                # print(pos)
                # question = {'qid': qno+1, "qno": actual_q_num, 'department': department, 'module': module_name, 'course': course_name, 'content': line.strip()[end_pos:], 'options': [], 'image': None, 'answer': None}
                # # options = []
                return question
            
            # continue
        except Exception as e:
            raise e 
    

    def write_to_json(self, file:list, save_to:str):
        source_path = Path(self._text_file_path).parent
        dest_path = source_path / self.department if self.department else "JSON"
        dest_path.mkdir(parents=True, exist_ok=True)
        with open(os.path.join(dest_path, save_to), "w") as json_file:
            json.dump(file, json_file, indent=4) 

        print(f"File saved to {save_to}")


    def convert(self):
        # read file
        self.read()

        if self.text_content is None:
            raise Exception("Reading file failed. File is not Valid")
        
        # for line in self.text_content.readlines():
        #     print(line)
        
        # open storage list for questions
        questions = []
        
        questions_split = self.text_content.strip().split("\n\n")

        print(self.text_content)
        for idx, question_block in enumerate(questions_split):
            lines = question_block.strip().split("\n")
            question_text = lines[0]
            options = []
            for option_line in lines[1:-1]:  # Skip the last line with the answer
                print(option_line)
                option_label, option_content = option_line.split(".", 1)
                options.append({
                    "label": option_label.strip(),
                    "content": option_content.strip(),
                    "image": None
                })
            answer_line = lines[-1]
            correct_option = answer_line.split(":")[1].strip()

            # Find the correct answer option
            correct_answer = next(option for option in options if option["label"] == correct_option)

            questions.append({
                "qid": idx + 1,
                "content": question_text,
                "image": None,
                "options": options
            })

        # Convert to JSON
        json_output = json.dumps(questions, indent=4)
        print(json_output)


if __name__ == "__main__":
    import sys 


    if len(sys.argv) < 2:
        print("... File path required")
        print(sys.argv)
        exit(0)
    
    file_path=sys.argv[1]
    t2j = TextToJson(
        department="Information Technology",
        text_file_path= file_path
    )
    t2j.read()
    # t2j.convert()