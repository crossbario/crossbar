import os
import re

# separate the metadata and markdown parts of pages
def preproc(text):

    lines = text.splitlines()
    i = 0

    for line in lines:

        if line.strip() == '':
            part0 = '\n'.join(lines[0:i])
            part1 = '\n'.join(lines[i+1:])
            return part0, part1

        i += 1

    raise Exception('meta header not found')

pat = re.compile(r'^\[(.*)\]\(.*\)$')

import yaml

for root, dirs, files in os.walk('pages'):
    for name in files:
        fn = os.path.join(root, name)
        with open(fn) as fd:
            contents = fd.read()
            part0, part1 = preproc(contents)
            if not part0.startswith('['):
                print(fn)
            else:
                parts = part0.strip().split('>')
                parts = [p.strip() for p in parts]
                pp = []
                for s in parts:
                    m = pat.match(s)
                    if m:
                        s = m.groups()[0]
                    s = s.replace('-', ' ')
                    pp.append(s)
                meta = {
                    'title': pp[-1],
                    'toc': pp
                }
                print(yaml.dump(meta))

#            print(part0)
