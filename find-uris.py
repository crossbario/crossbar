import os
import re
import glob
from pprint import pprint


def find_uris(files):
    uris = set()
    pat1 = re.compile(r'.*(crossbarfabriccenter\.[a-z_.]*).*')
    pat2 = re.compile(r'.*(xbr\.network\.[a-z_.]*).*')
    pat3 = re.compile(r'.*(xbr\.marketmaker\.[a-z_.]*).*')
    for pat in [pat1, pat2, pat3]:
        for filename in files:
            with open(filename, 'rb') as fd:
                for line in fd.read().decode('utf-8').splitlines():
                    if 'crossbarfabriccenter' in line or 'xbr' in line:
                        m = pat.match(line)
                        if m:
                            uri = m.groups()[0]
                            if uri not in ['crossbarfabriccenter', 'xbr'] and not uri.endswith('.') and ".." not in uri and not uri.startswith('http'):
                                uris.add(uri)

    uris = sorted(list(uris))
    return uris


files = [fn for fn in glob.glob("**", recursive=True) if fn.endswith('.py') and fn != os.path.basename(__file__)]
uris_all = find_uris(files)
print('\nALL URIs used in Crossbar.io - {}:\n'.format(len(uris_all)))
pprint(uris_all)

if False:
    uris_cli = find_uris(['crossbar/shell/command.py', 'crossbar/shell/monitor.py'])
    print('\nURIs used in Crossbar.io CLI (client-side) - {}:\n'.format(len(uris_cli)))
    pprint(uris_cli)

    uris_non_cli = sorted(list(set(uris_all) - set(uris_cli)))
    print('\nURIs NOT used in Crossbar.io CLI (client-side) - {}:\n'.format(len(uris_non_cli)))
    pprint(uris_non_cli)
