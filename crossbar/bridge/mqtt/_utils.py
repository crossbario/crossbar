#####################################################################################
#
#  Copyright (c) Crossbar.io Technologies GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from bitstring import pack

from autobahn.websocket.utf8validator import Utf8Validator

_validator = Utf8Validator()


class ParseFailure(Exception):
    pass


class SerialisationFailure(Exception):
    pass


def read_prefixed_data(data):
    """
    Reads the next 16-bit-uint prefixed data block from `data`.
    """
    data_length = data.read('uint:16')
    return data.read(data_length * 8).bytes


def read_string(data):
    """
    Reads the next MQTT pascal-style string from `data`.
    """
    byte_data = read_prefixed_data(data)
    _validator.reset()

    if _validator.validate(byte_data)[0]:
        decoded = byte_data.decode('utf8', 'strict')
        if "\u0000" in decoded:
            raise ParseFailure("Invalid UTF-8 string (contains nulls)")
        return decoded
    else:
        raise ParseFailure("Invalid UTF-8 string (contains surrogates)")


def build_string(string):

    string = string.encode('utf8')
    return pack('uint:16', len(string)).bytes + string


def build_header(packet_id, flags, payload_length):

    header = pack('uint:4, bool, bool, bool, bool', packet_id, *flags)

    if payload_length > 0:
        length_bytes = []

        while payload_length > 0:
            encoded_byte = payload_length % 128
            payload_length = payload_length // 128
            if payload_length > 0:
                encoded_byte = encoded_byte | 128
            length_bytes.append(encoded_byte)
    else:
        length_bytes = [0]

    return header.bytes + pack(','.join(['uint:8'] * len(length_bytes)), *length_bytes).bytes


def iterbytes(b):
    for i in range(len(b)):
        yield b[i:i + 1]
