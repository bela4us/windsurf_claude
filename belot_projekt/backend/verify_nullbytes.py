import os

def check_null_bytes(file_path):
    with open(file_path, 'rb') as f:
        content = f.read()
        null_bytes = content.count(b'\x00')
        if null_bytes > 0:
            print(f"PRONAĐENO {null_bytes} null byte-ova u {file_path}")
            return True
    return False

def scan_directory(directory):
    problem_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') and ('urls' in file or 'urls' in root):
                file_path = os.path.join(root, file)
                if check_null_bytes(file_path):
                    problem_files.append(file_path)
    return problem_files

# Promijenite ovu putanju prema vašem projektu
problem_files = scan_directory('belot_projekt/backend')
print(f"Pronađeno {len(problem_files)} problematičnih datoteka")