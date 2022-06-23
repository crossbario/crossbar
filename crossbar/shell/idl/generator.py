###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import argparse
import json
import pprint
import os

import docutils
import jinja2
from jinja2 import Environment, FileSystemLoader

from crossbar.shell.util import hl


def rst_filter(rst):
    html = docutils.core.publish_parts(source=rst, writer_name='html')['html_body']
    return jinja2.Markup(html)


def process(schema, template_paths=['templates', 'tests/idl']):
    # http://jinja.pocoo.org/docs/latest/api/#loaders
    loader = FileSystemLoader(template_paths, encoding='utf-8', followlinks=False)

    env = Environment(loader=loader, autoescape=True)
    env.filters['rst'] = rst_filter

    tmpl = env.get_template('service.py')

    print(tmpl)

    contents = tmpl.render(schema=schema)

    print(contents)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('infile', help='FlatBuffers JSON schema input file (.json)')
    parser.add_argument('-t', '--templates', help='Templates folder')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose processing output.')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output.')

    options = parser.parse_args()

    import txaio
    txaio.use_twisted()

    log = txaio.make_logger()
    txaio.start_logging(level='debug' if options.debug else 'info')

    infile_path = os.path.abspath(options.infile)
    with open(infile_path, 'rb') as f:
        buf = f.read()

    log.info('Loading FlatBuffers JSON schema ({} bytes) ...'.format(len(buf)))

    try:
        schema = json.loads(buf, encoding='utf8')
    except Exception as e:
        log.error(e)

    if options.verbose:
        log.info('Schema metadata:')
        schema_meta_str = pprint.pformat(schema['meta'])
        # log.info(schema_meta_str)
        # log.info('{}'.format(schema_meta_str))
        print(schema_meta_str)

        for o in schema['types'].values():
            if o['type'] == 'interface':
                log.info('interface: {}'.format(hl(o['name'], bold=True)))
                for s in o['slots'].values():
                    log.info('{:>12}: {}'.format(s['type'], hl(s['name'])))

    process(schema)
