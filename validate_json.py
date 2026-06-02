import os
import sys
import json

# Terminal Colors for readable formatting
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def check_questions_json(file_path):
    if not os.path.exists(file_path):
        print(f"{Colors.FAIL}{Colors.BOLD}[ERROR]:{Colors.ENDC} Targeted file path does not exist: '{file_path}'")
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"{Colors.FAIL}{Colors.BOLD}[CRITICAL ERROR]:{Colors.ENDC} File is not a valid JSON string layout!\nDetails: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        print(f"{Colors.FAIL}{Colors.BOLD}[CRITICAL ERROR]:{Colors.ENDC} Root element is not a JSON list container []!")
        sys.exit(1)

    total_records = len(data)
    errors_count = 0
    warnings_count = 0

    print(f"{Colors.HEADER}=================================================={Colors.ENDC}")
    print(f"🔬 Starting Validation Audit Checklist on: {Colors.BOLD}{file_path}{Colors.ENDC}")
    print(f"Found total payload records: {total_records}")
    print(f"{Colors.HEADER}==================================================\n{Colors.ENDC}")

    for idx, item in enumerate(data):
        # Human readable track helper for logs
        q_identifier = item.get('qno') if isinstance(item, dict) and item.get('qno') is not None else f"Index {idx}"
        prefix_context = f"Question No. {q_identifier}:"

        if not isinstance(item, dict):
            print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {prefix_context} Structure block entry is not an object node!")
            errors_count += 1
            continue

        # --- 1. WARNING CHECKS (Metadata) ---
        missing_meta = []
        if not item.get('department') or str(item['department']).strip().lower() == "none":
            missing_meta.append("department")
        if not item.get('module') or str(item['module']).strip().lower() == "none":
            missing_meta.append("module")
        if not item.get('course') or str(item['course']).strip().lower() == "none":
            missing_meta.append("course")

        if missing_meta:
            meta_str = ", ".join(missing_meta)
            print(f"{Colors.WARNING}[WARNING]{Colors.ENDC} {prefix_context} Metadata fields are null/unset -> [{meta_str}]")
            warnings_count += 1

        # --- 2. ERROR CHECKS (Question Content & Answers) ---
        content = item.get('content')
        if content is None or (isinstance(content, str) and not content.strip()):
            print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {prefix_context} Question 'content' text body is completely empty/null!")
            errors_count += 1

        answer = item.get('answer')
        if answer is None or (isinstance(answer, str) and not answer.strip()) or str(answer).strip().lower() == "none":
            print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {prefix_context} Crucial field 'answer' key cannot be null or unset!")
            errors_count += 1

        # --- 3. ERROR CHECKS (Options Configuration) ---
        options = item.get('options')
        if not isinstance(options, list):
            print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {prefix_context} 'options' wrapper missing or formatted incorrectly (not a list)!")
            errors_count += 1
            continue

        if len(options) == 0:
            print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {prefix_context} Options collection list is empty! Requires A-D items.")
            errors_count += 1
            continue

        # Track labels found to check for expected standardized structures (A, B, C, D)
        found_labels = []
        for opt_idx, opt in enumerate(options):
            if not isinstance(opt, dict):
                print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {prefix_context} Option index {opt_idx} is corrupted (not an object block)!")
                errors_count += 1
                continue
            
            label = str(opt.get('label', '')).strip().upper()
            if label:
                found_labels.append(label)
                
            opt_content = opt.get('content')
            if opt_content is None or (isinstance(opt_content, str) and not opt_content.strip()):
                print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {prefix_context} Option Option ({label or opt_idx}) text value content is empty/null!")
                errors_count += 1

        # Verify options fulfill standard constraints (A-D labels checked sequentially)
        expected_labels = ["A", "B", "C", "D"]
        if found_labels != expected_labels:
            joined_found = ", ".join(found_labels) if found_labels else "None"
            print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {prefix_context} Broken choice scheme labels. Found: [{joined_found}]. Expected exactly: [A, B, C, D]")
            errors_count += 1

    # --- FINAL AUDIT REPORT ---
    print(f"\n{Colors.HEADER}=================================================={Colors.ENDC}")
    print(f"{Colors.BOLD}📋 FINAL SCHEMA AUDIT REPORT SUMMARY{Colors.ENDC}")
    print(f"{Colors.HEADER}=================================================={Colors.ENDC}")
    print(f"Total Exam Items Audited : {total_records}")
    
    if warnings_count > 0:
        print(f"Total Warnings Flagged    : {Colors.WARNING}{warnings_count}{Colors.ENDC}")
    else:
        print(f"Total Warnings Flagged    : {Colors.OKGREEN}0 (Clean metadata!){Colors.ENDC}")

    if errors_count > 0:
        print(f"Total Errors Found       : {Colors.FAIL}{Colors.BOLD}{errors_count}{Colors.ENDC}")
        print(f"\n{Colors.FAIL}{Colors.BOLD}❌ VALIDATION STATUS: FAILED.{Colors.ENDC} Please fix database files before parsing.")
        sys.exit(1)
    else:
        print(f"Total Errors Found       : {Colors.OKGREEN}{Colors.BOLD}0{Colors.ENDC}")
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}██████████████████████████████████████████████████{Colors.ENDC}")
        print(f"{Colors.OKGREEN}{Colors.BOLD}✔ VALIDATION STATUS: PASSED! JSON conforms to structural requirements.{Colors.ENDC}")
        sys.exit(0)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python validate_json.py <path_to_questions.json>")
        sys.exit(1)
    
    target_json = sys.argv[1]
    check_questions_json(target_json)