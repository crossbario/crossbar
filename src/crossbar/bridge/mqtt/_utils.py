#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

from autobahn.websocket.utf8validator import Utf8Validator

_validator = Utf8Validator()


class ParseFailure(Exception):
    pass


class SerialisationFailure(Exception):
    pass


class ReadError(Exception):
    """
    Raised when reading past the end of the data in a :class:`ByteReader`.
    """


class ByteReader(object):
    """
    Read position over the bytes of one MQTT packet (replaces ``bitstring.BitStream``, #2321).
    """

    def __init__(self, data):
        self._data = bytes(data)
        self.pos = 0

    def __len__(self):
        return len(self._data)

    def read_bytes(self, count):
        end = self.pos + count
        if end > len(self._data):
            raise ReadError("Cannot read {} bytes, only {} available.".format(count, len(self._data) - self.pos))
        result = self._data[self.pos : end]
        self.pos = end
        return result

    def read_uint8(self):
        return self.read_bytes(1)[0]

    def read_uint16(self):
        return int.from_bytes(self.read_bytes(2), "big")


def read_prefixed_data(data):
    """
    Reads the next 16-bit-uint prefixed data block from `data`.
    """
    data_length = data.read_uint16()
    return data.read_bytes(data_length)


def read_string(data):
    """
    Reads the next MQTT pascal-style string from `data`.
    """
    byte_data = read_prefixed_data(data)
    _validator.reset()

    if _validator.validate(byte_data)[0]:
        decoded = byte_data.decode("utf8", "strict")
        if "\u0000" in decoded:
            raise ParseFailure("Invalid UTF-8 string (contains nulls)")
        return decoded
    else:
        raise ParseFailure("Invalid UTF-8 string (contains surrogates)")


def build_string(string):
    string = string.encode("utf8")
    return len(string).to_bytes(2, "big") + string


def build_header(packet_id, flags, payload_length):
    header = bytes([(packet_id << 4) | (flags[0] << 3) | (flags[1] << 2) | (flags[2] << 1) | flags[3]])

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

    return header + bytes(length_bytes)


def iterbytes(b):
    for i in range(len(b)):
        yield b[i : i + 1]
