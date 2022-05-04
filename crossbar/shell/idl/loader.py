###############################################################################
#
# Crossbar.io Shell
# Copyright (c) Crossbar.io Technologies GmbH. Licensed under EUPLv1.2.
#
###############################################################################

import os
import json
import argparse
import hashlib
import pprint

from typing import Dict, Any, Optional, BinaryIO  # noqa

from crossbar.shell.util import hl
from crossbar.shell.reflection import Schema

import txaio

txaio.use_twisted()


def extract_attributes(item, allowed_attributes=None):
    num_attrs = item.AttributesLength()
    attrs = [item.Attributes(i) for i in range(num_attrs)]
    attrs_dict = {
        x.Key().decode('utf8'): x.Value().decode('utf8') if x.Value().decode('utf8') not in ['0'] else None
        for x in attrs
    }
    if allowed_attributes:
        for attr in attrs_dict:
            if attr not in allowed_attributes:
                raise Exception('invalid XBR attribute  "{}" - must be one of {}'.format(attr, allowed_attributes))
    return attrs_dict


def extract_docs(item):
    num_docs = item.DocumentationLength()
    item_docs = [item.Documentation(i).decode('utf8').strip() for i in range(num_docs)]
    return item_docs


INTERFACE_ATTRS = ['type', 'uuid']

INTERFACE_MEMBER_ATTRS = ['type', 'stream']

INTERFACE_MEMBER_TYPES = ['procedure', 'topic']

INTERFACE_MEMBER_STREAM_VALUES = [None, 'in', 'out', 'inout']

EXTRACT_ATTRS_RAW = False

_BASETYPE_ID2NAME = {
    None: 'Unknown',
    0: 'none',
    1: 'utype',
    2: 'bool',
    3: 'int8',
    4: 'uint8',
    5: 'int16',
    6: 'uint16',
    7: 'int32',
    8: 'uint32',
    9: 'int64',
    10: 'uint64',
    11: 'float',
    12: 'double',
    13: 'string',
    14: 'vector',
    15: 'object',
    16: 'union',
}


def read_reflection_schema(buf, log=None):
    """
    Read a binary FlatBuffers buffer that is typed according to the FlatBuffers
    reflection schema.

    The function returns extracted information in a plain, JSON serializable dict.
    """
    if not log:
        log = txaio.make_logger()

    _schema = Schema.GetRootAsSchema(buf, 0)

    _root = _schema.RootTable()
    if _root:
        root_name = _root.Name().decode('utf8').strip()
    else:
        root_name = None

    _file_ident = _schema.FileIdent().decode('utf8').strip()
    if _file_ident == '':
        _file_ident = None

    _file_ext = _schema.FileExt().decode('utf8').strip()
    if _file_ext == '':
        _file_ext = None

    m = hashlib.sha256()
    m.update(buf)

    schema_meta = {
        'bfbs_size': len(buf),
        'bfbs_sha256': m.hexdigest(),
        'file_ident': _file_ident,
        'file_ext': _file_ext,
        'root': root_name,
    }

    schema = None  # type: dict
    schema = {
        'meta': schema_meta,
        'tables': [],
        'enums': [],
        'services': [],
    }

    schema_by_uri = None  # type: dict
    schema_by_uri = {
        'meta': schema_meta,
        'types': {},
    }

    enums = []
    objects = []
    services = []

    fqn2type = dict()  # type: Dict[str, Any]

    enum_cnt = 0
    object_cnt = 0
    service_cnt = 0
    typerefs_cnt = 0
    typerefs_error_cnt = 0

    for i in range(_schema.EnumsLength()):
        item = _schema.Enums(i)
        name = item.Name().decode('utf8')
        if name in fqn2type:
            raise Exception('duplicate name "{}"'.format(name))
        enum_cnt += 1

    for i in range(_schema.ObjectsLength()):
        item = _schema.Objects(i)
        name = item.Name().decode('utf8')
        if name in fqn2type:
            raise Exception('duplicate name "{}"'.format(name))
        object_cnt += 1

    for i in range(_schema.ServicesLength()):
        item = _schema.Services(i)
        name = item.Name().decode('utf8')
        if name in fqn2type:
            raise Exception('duplicate name "{}"'.format(name))
        service_cnt += 1

    log.info('Processing schema with {} enums, {} objects and {} services ...'.format(
        enum_cnt, object_cnt, service_cnt))

    # enums
    #
    num_enums = _schema.EnumsLength()
    for i in range(num_enums):

        # extract enum base information
        #
        _enum = _schema.Enums(i)
        enum_name = _enum.Name().decode('utf8')
        log.debug('processing enum {} ("{}")'.format(i, enum_name))

        enum = {
            # '_index': i,
            'type': 'enum',
            'name': enum_name,
            'docs': extract_docs(_enum),
        }
        if EXTRACT_ATTRS_RAW:
            enum['attr'] = extract_attributes(_enum)

        # extract enum values
        #
        enum_values_dict = dict()  # type: Dict[str, Any]
        for j in range(_enum.ValuesLength()):
            _enum_value = _enum.Values(j)
            enum_value_name = _enum_value.Name().decode('utf8')
            enum_value = {
                'docs': extract_docs(_enum_value),
                # enum values cannot have attributes
            }
            if enum_value_name in enum_values_dict:
                raise Exception('duplicate enum value "{}"'.format(enum_value_name))
            enum_values_dict[enum_value_name] = enum_value
        enum['values'] = enum_values_dict

        if enum_name in schema_by_uri['types']:
            raise Exception('unexpected duplicate definition for qualified name "{}"'.format(enum_name))

        enums.append(enum)
        schema_by_uri['types'][enum_name] = enum

    # objects (tables/structs)
    #
    for i in range(_schema.ObjectsLength()):

        _obj = _schema.Objects(i)
        obj_name = _obj.Name().decode('utf8')
        object_type = 'struct' if _obj.IsStruct() else 'table'

        obj = {
            # '_index': i,
            'type': object_type,
            'name': obj_name,
            'docs': extract_docs(_obj),
        }
        if EXTRACT_ATTRS_RAW:
            obj['attr'] = extract_attributes(_obj)

        # extract fields
        num_fields = _obj.FieldsLength()
        fields = []
        fields_by_name = {}
        for j in range(num_fields):

            _field = _obj.Fields(j)
            field_name = _field.Name().decode('utf8')
            log.debug('processing field {} ("{}")'.format(i, field_name))

            _field_type = _field.Type()

            _field_index = int(_field_type.Index())
            _field_base_type = _BASETYPE_ID2NAME.get(_field_type.BaseType(), None)

            _field_element = _BASETYPE_ID2NAME.get(_field_type.Element(), None)
            if _field_element == 'none':
                _field_element = None

            # FIXME
            # if _field_element == 'object':
            #     el = _schema.Objects(_field_type.Element())
            #     if isinstance(el, reflection.Type) and hasattr(el, 'IsStruct'):
            #         _field_element = 'struct' if el.Element().IsStruct(
            #         ) else 'table'

            field = {
                # '_index': j,
                'name': field_name,
                'id': int(_field.Id()),
                'offset': int(_field.Offset()),
                'base_type': _field_base_type,
            }

            if _field_element:
                # vector
                field['element_type'] = _field_element

            if _field_index != -1:

                # field['field_index'] = _field_index

                if _field_base_type in ['object', 'struct'] or _field_element in ['object', 'struct']:

                    # obj/struct

                    if _field_index < _schema.ObjectsLength():
                        l_obj = _schema.Objects(_field_index)
                        l_obj_ref = _obj.Name().decode('utf8')
                        field['ref_category'] = 'struct' if l_obj.IsStruct() else 'table'
                        field['ref_type'] = l_obj_ref
                        typerefs_cnt += 1
                    else:
                        log.info('WARNING - referenced table/struct for index {} ("{}.{}") not found'.format(
                            _field_index, obj_name, field_name))
                        field['ref_category'] = 'object'
                        field['ref_type'] = None
                        typerefs_error_cnt += 1

                elif _field_base_type in [
                        'utype', 'bool', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64',
                        'float', 'double', 'string'
                ]:
                    # enum
                    field['ref_category'] = 'enum'

                    if _field_index < _schema.EnumsLength():
                        _enum_ref = _schema.Enums(_field_index).Name().decode('utf8')
                        field['ref_type'] = _enum_ref
                        typerefs_cnt += 1
                    else:
                        log.info('WARNING - referenced enum not found')
                        field['ref_type'] = None
                        typerefs_error_cnt += 1

                else:
                    raise Exception('unhandled field type: {} {} {} {}'.format(field_name, _field_base_type,
                                                                               _field_element, _field_index))

            field_docs = extract_docs(_field)
            if field_docs:
                field['docs'] = field_docs

            if EXTRACT_ATTRS_RAW:
                _field_attrs = extract_attributes(_field)
                if _field_attrs:
                    field['attr'] = _field_attrs

            fields.append(field)
            fields_by_name[field_name] = field

        obj['fields'] = fields_by_name

        if obj['name'] in schema_by_uri['types']:
            raise Exception('unexpected duplicate definition for qualified name "{}"'.format(field['name']))

        # always append the object here, so we can dereference indexes
        # correctly
        objects.append(obj)

        # skip our "void marker"
        if False and obj_name in ['Void']:
            pass
        else:
            schema_by_uri['types'][obj['name']] = obj

    # iterate over services
    #
    num_services = _schema.ServicesLength()
    for i in range(num_services):
        _service = _schema.Services(i)

        service_name = _service.Name().decode('utf8')

        service_attrs_dict = extract_attributes(_service, INTERFACE_ATTRS)

        service_type = service_attrs_dict.get('type', None)
        if service_type != 'interface':
            raise Exception('invalid value "{}" for attribute "type" in XBR interface'.format(service_type))

        service = {
            # '_index': i,
            'type': service_type,
            'name': service_name,
            'docs': extract_docs(_service),
        }

        if EXTRACT_ATTRS_RAW:
            service['attrs'] = service_attrs_dict
        else:
            service['uuid'] = service_attrs_dict.get('uuid', None)

        num_calls = _service.CallsLength()
        calls = []
        calls_by_name = {}
        for j in range(num_calls):
            _call = _service.Calls(j)

            _call_name = _call.Name().decode('utf8')

            call_attrs_dict = extract_attributes(_call)

            call_type = call_attrs_dict.get('type', None)
            if call_type not in INTERFACE_MEMBER_TYPES:
                raise Exception('invalid XBR interface member type "{}" - must be one of {}'.format(
                    call_type, INTERFACE_MEMBER_TYPES))

            call_stream = call_attrs_dict.get('stream', None)
            if call_stream in ['none', 'None', 'null', 'Null']:
                call_stream = None

            if call_stream not in INTERFACE_MEMBER_STREAM_VALUES:
                raise Exception('invalid XBR interface member stream modifier "{}" - must be one of {}'.format(
                    call_stream, INTERFACE_MEMBER_STREAM_VALUES))

            def _decode_type(x):
                res = x.Name().decode('utf8')
                if res in ['Void', 'wamp.Void']:
                    res = None
                return res

            call = {
                'type': call_type,
                'name': _call_name,
                'in': _decode_type(_call.Request()),
                'out': _decode_type(_call.Response()),
                'stream': call_stream,
                # 'id': int(_call.Id()),
                # 'offset': int(_call.Offset()),
            }
            # call['attrs'] = call_attrs_dict
            call['docs'] = extract_docs(_call)

            calls.append(call)
            calls_by_name[_call_name] = call

        # service['calls'] = sorted(calls, key=lambda field: field['id'])
        service['slots'] = calls_by_name

        services.append(service)

        if service_name in schema_by_uri['types']:
            raise Exception('unexpected duplicate definition for qualified name "{}"'.format(service_name))
        else:
            schema_by_uri['types'][service_name] = service

    if typerefs_error_cnt:
        raise Exception('{} unresolved type references encountered in schema'.format(typerefs_error_cnt))

    schema['enums'] = sorted(enums, key=lambda enum: enum['name'])
    schema['tables'] = sorted(objects, key=lambda obj: obj['name'])
    schema['services'] = sorted(services, key=lambda service: service['name'])

    return schema_by_uri


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('infile', help='FlatBuffers binary schema input file (.bfbs)')
    parser.add_argument('-o', '--outfile', help='FlatBuffers JSON schema output (.json)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose processing output.')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output.')

    options = parser.parse_args()

    log = txaio.make_logger()
    txaio.start_logging(level='debug' if options.debug else 'info')

    infile_path = os.path.abspath(options.infile)
    with open(infile_path, 'rb') as f:
        buf = f.read()

    log.info('Loading FlatBuffers binary schema ({} bytes) ...'.format(len(buf)))

    try:
        schema = read_reflection_schema(buf, log=log)
    except Exception as e:
        log.error(e)

    if True:
        schema['meta']['file_name'] = os.path.basename(options.infile)
        schema['meta']['file_path'] = infile_path

    with open(options.outfile, 'wb') as fo:  # type: BinaryIO
        outdata = json.dumps(schema, ensure_ascii=False, sort_keys=False, indent=4,
                             separators=(', ', ': ')).encode('utf8')
        fo.write(outdata)

    cnt_bytes = len(outdata)
    cnt_defs = len(schema['types'].keys())
    log.info('FlatBuffers JSON schema data written ({} bytes, {} defs).'.format(cnt_bytes, cnt_defs))

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
