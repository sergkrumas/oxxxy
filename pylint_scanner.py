

import os 
import subprocess

# Засовывает все файлы с расширением .py и .pyw в pylint, файлы будут найдены даже в подпапках.

def scan():
    filepaths = []
    root = os.path.dirname(__file__)
    for cur_dir, dirs, files in os.walk(root):
        for filename in files:
            if filename.lower().endswith(('.py', '.pyw')):
                filepath = os.path.join(cur_dir, filename)
                filepaths.append(filepath)

    filepath = os.path.join(root, 'pylint_out.txt')
    if os.path.exists(filepath):
        os.remove(filepath)
    f = open(filepath, "w", encoding='utf8')
    count = len(filepaths)
    for n, filepath in enumerate(filepaths, start=1):
        status = f'[{n}/{count}]'
        print(f'scanning file {status} {filepath}...')
        subprocess.call(["pylint", filepath, "--disable=E0611,C0115,C0103,C0116"], stdout=f)

if __name__ == '__main__':
    scan()
