"""Index Blutter method labels/addresses, without exporting arbitrary strings."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def index_file(path):
    path=Path(path);text=path.read_text()
    package=re.search(r'url: (package:[^\n]+)',text)
    matches=[];label=None
    for line in text.splitlines():
        if re.match(r'^  \S.*\{$',line):label=line.strip()[:-1].strip()
        m=re.search(r'// \*\* addr: (0x[0-9a-f]+), size: (0x[0-9a-f]+)',line)
        if m and label:matches.append({'method':label,'address_hex':m[1],'size_hex':m[2]})
    return {'package':package[1] if package else None,
            'analysis_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'methods':matches}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('files',nargs='+',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    with a.output.open('x') as f:json.dump({'schema_version':1,'evidence':'Blutter annotated disassembly, not original Dart source','files':[index_file(path) for path in a.files]},f,indent=2);f.write('\n')


if __name__=='__main__':main()
