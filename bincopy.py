"""Mangling of various file formats that conveys binary information
(Motorola S-Record, Intel HEX and binary files).

"""

from __future__ import print_function, division

import binascii
import string
import sys
import argparse

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


__author__ = 'Erik Moqvist'
__version__ = '7.6.0'


DEFAULT_WORD_SIZE_BITS = 8


class Error(Exception):
    """Bincopy base exception.

    """

    pass


def crc_srec(hexstr):
    """Calculate the CRC for given Motorola S-Record hexstring.

    """

    crc = sum(bytearray(binascii.unhexlify(hexstr)))
    crc &= 0xff
    crc ^= 0xff

    return crc


def crc_ihex(hexstr):
    """Calculate crc for given Intel HEX hexstring.

    """

    crc = sum(bytearray(binascii.unhexlify(hexstr)))
    crc &= 0xff
    crc = ((~crc + 1) & 0xff)

    return crc


def pack_srec(type_, address, size, data):
    """Create a Motorola S-Record record of given data.

    """

    if type_ in '0159':
        line = '%02X%04X' % (size + 2 + 1, address)
    elif type_ in '268':
        line = '%02X%06X' % (size + 3 + 1, address)
    elif type_ in '37':
        line = '%02X%08X' % (size + 4 + 1, address)
    else:
        raise Error("expected record type 0..3 or 5..9, but got '{}'".format(
            type_))

    if data:
        line += binascii.hexlify(data).decode('utf-8').upper()

    return 'S%s%s%02X' % (type_, line, crc_srec(line))


def unpack_srec(record):
    """Unpack given Motorola S-Record record into variables.

    """

    if len(record) < 6:
        raise Error("record '{}' too short".format(record))

    if record[0] != 'S':
        raise Error("record '{}' not starting with an 'S'".format(
            record))

    size = int(record[2:4], 16)
    type_ = record[1:2]

    if type_ in '0159':
        width = 4
    elif type_ in '268':
        width = 6
    elif type_ in '37':
        width = 8
    else:
        raise Error("expected record type 0..3 or 5..9, but got '{}'".format(
            type_))

    address = int(record[4:4+width], 16)
    data = binascii.unhexlify(record[4 + width:4 + 2 * size - 2])
    actual_crc = int(record[4 + 2 * size - 2:], 16)
    expected_crc = crc_srec(record[2:4 + 2 * size - 2])

    if actual_crc != expected_crc:
        raise Error("expected crc {:#02x} in record {}, but got {:#02x}".format(
            expected_crc,
            record,
            actual_crc))

    return (type_, address, size - 1 - width // 2, data)


def pack_ihex(type_, address, size, data):
    """Create a Intel HEX record of given data.

    """

    line = '%02X%04X%02X' % (size, address, type_)

    if data:
        line += binascii.hexlify(data).decode('utf-8').upper()

    return ':%s%02X' % (line, crc_ihex(line))


def unpack_ihex(record):
    """Unpack given Intel HEX record into variables.

    """

    if len(record) < 11:
        raise Error("record '{}' too short".format(record))

    if record[0] != ':':
        raise Error("record '{}' not starting with a ':'".format(record))

    size = int(record[1:3], 16)
    address = int(record[3:7], 16)
    type_ = int(record[7:9], 16)

    if size > 0:
        data = binascii.unhexlify(record[9:9 + 2 * size])
    else:
        data = ''

    actual_crc = int(record[9 + 2 * size:], 16)
    expected_crc = crc_ihex(record[1:9 + 2 * size])

    if actual_crc != expected_crc:
        raise Error("expected crc {:#02x} in record {}, but got {:#02x}".format(
            expected_crc,
            record,
            actual_crc))

    return (type_, address, size, data)


def is_srec(records):
    try:
        unpack_srec(records.splitlines()[0])
    except Error:
        return False
    else:
        return True


def is_ihex(records):
    try:
        unpack_ihex(records.splitlines()[0])
    except Error:
        return False
    else:
        return True


class _Segment(object):
    """A segment is a chunk data with given minimum and maximum address.

    """

    def __init__(self, minimum_address, maximum_address, data):
        self.minimum_address = minimum_address
        self.maximum_address = maximum_address
        self.data = data

    def add_data(self, minimum_address, maximum_address, data, overwrite):
        """Add given data to this segment. The added data must be adjacent to
        the current segment data, otherwise an exception is thrown.

        """

        if minimum_address == self.maximum_address:
            self.maximum_address = maximum_address
            self.data += data
        elif maximum_address == self.minimum_address:
            self.minimum_address = minimum_address
            self.data = data + self.data
        elif (overwrite
              and minimum_address < self.maximum_address
              and maximum_address > self.minimum_address):
            self_data_offset = minimum_address - self.minimum_address

            # prepend data
            if self_data_offset < 0:
                self_data_offset *= -1
                self.data = data[:self_data_offset] + self.data
                del data[:self_data_offset]
                self.minimum_address = minimum_address

            # overwrite overlapping part
            self_data_left = len(self.data) - self_data_offset

            if len(data) <= self_data_left:
                self.data[self_data_offset:self_data_offset + len(data)] = data
                data = bytearray()
            else:
                self.data[self_data_offset:] = data[:self_data_left]
                data = data[self_data_left:]

            # append data
            if len(data) > 0:
                self.data += data
                self.maximum_address = maximum_address
        else:
            raise Error('data added to a segment must be adjacent to or '
                        'overlapping with the original segment data')

    def remove_data(self, minimum_address, maximum_address):
        """Remove given data range from this segment. Returns the second
        segment if the removed data splits this segment in two.

        """

        if ((minimum_address >= self.maximum_address)
            and (maximum_address <= self.minimum_address)):
            raise Error('cannot remove data that is not part of the segment')

        if minimum_address < self.minimum_address:
            minimum_address = self.minimum_address

        if maximum_address > self.maximum_address:
            maximum_address = self.maximum_address

        remove_size = maximum_address - minimum_address
        part1_size = minimum_address - self.minimum_address
        part1_data = self.data[0:part1_size]
        part2_data = self.data[part1_size + remove_size:]

        if len(part1_data) and len(part2_data):
            # Update this segment and return the second segment.
            self.maximum_address = self.minimum_address + part1_size
            self.data = part1_data

            return _Segment(maximum_address,
                            maximum_address + len(part2_data),
                            part2_data)
        else:
            # Update this segment.
            if len(part1_data) > 0:
                self.maximum_address = minimum_address
                self.data = part1_data
            elif len(part2_data) > 0:
                self.minimum_address = maximum_address
                self.data = part2_data
            else:
                self.maximum_address = self.minimum_address
                self.data = bytearray()

    def __str__(self):
        return '[%#x .. %#x]: %s' % (self.minimum_address,
                                     self.maximum_address,
                                     binascii.hexlify(self.data))


class _Segments(object):
    """A list of segments.

    """

    def __init__(self):
        self.current_segment = None
        self.current_segment_index = None
        self.list = []

    def add(self, segment, overwrite=False):
        """Add segments by ascending address.

        """

        if self.list:
            if segment.minimum_address == self.current_segment.maximum_address:
                # fast insertion for adjacent segments
                self.current_segment.add_data(segment.minimum_address,
                                              segment.maximum_address,
                                              segment.data,
                                              overwrite)
            else:
                # linear insert
                for i, s in enumerate(self.list):
                    if segment.minimum_address <= s.maximum_address:
                        break

                if segment.minimum_address > s.maximum_address:
                    # non-overlapping, non-adjacent after
                    self.list.append(segment)
                elif segment.maximum_address < s.minimum_address:
                    # non-overlapping, non-adjacent before
                    self.list.insert(i, segment)
                else:
                    # adjacent or overlapping
                    s.add_data(segment.minimum_address,
                               segment.maximum_address,
                               segment.data,
                               overwrite)
                    segment = s

                self.current_segment = segment
                self.current_segment_index = i

            # remove overwritten and merge adjacent segments
            while self.current_segment is not self.list[-1]:
                s = self.list[self.current_segment_index + 1]

                if self.current_segment.maximum_address >= s.maximum_address:
                    # the whole segment is overwritten
                    del self.list[self.current_segment_index + 1]
                elif self.current_segment.maximum_address >= s.minimum_address:
                    # adjacent or beginning of the segment overwritten
                    self.current_segment.add_data(
                        self.current_segment.maximum_address,
                        s.maximum_address,
                        s.data[self.current_segment.maximum_address - s.minimum_address:],
                        overwrite=False)
                    del self.list[self.current_segment_index+1]
                    break
                else:
                    # segments are not overlapping, nor adjacent
                    break
        else:
            self.list.append(segment)
            self.current_segment = segment
            self.current_segment_index = 0

    def remove(self, minimum_address, maximum_address):
        new_list = []

        for segment in self.list:
            if (segment.maximum_address <= minimum_address
                or maximum_address < segment.minimum_address):
                # no overlap
                new_list.append(segment)
            else:
                # overlapping, remove overwritten parts segments
                split = segment.remove_data(minimum_address, maximum_address)

                if segment.minimum_address < segment.maximum_address:
                    new_list.append(segment)

                if split:
                    new_list.append(split)

        self.list = new_list

    def iter(self, size=32):
        """Iterate over all segments and return chunks of the data.

        """

        for segment in self.list:
            data = segment.data
            address = segment.minimum_address

            for offset in range(0, len(data), size):
                yield address + offset, data[offset:offset + size]

    def get_minimum_address(self):
        """Get the minimum address of the data.

        """

        if not self.list:
            raise Error('cannot get minimum address from an empty file')

        return self.list[0].minimum_address

    def get_maximum_address(self):
        """Get the maximum address of the data.

        """

        if not self.list:
            raise Error('cannot get maximum address from an empty file')

        return self.list[-1].maximum_address

    def get_size(self):
        """Get the size of the binary, including holes in the data.

        """

        if not self.list:
            return 0

        return self.get_maximum_address() - self.get_minimum_address()

    def __str__(self):
        return '\n'.join([s.__str__() for s in self.list])


class BinFile(object):

    def __init__(self, word_size_bits=DEFAULT_WORD_SIZE_BITS):
        if (word_size_bits % 8) != 0:
            raise Error('word size must be a multiple of 8 bits')
        self.word_size_bits = word_size_bits
        self.word_size_bytes = (word_size_bits // 8)
        self.header = None
        self.execution_start_address = None
        self.segments = _Segments()

    def __setitem__(self, key, data):
        """Write data to given absolute address or address range.

        """

        if isinstance(key, slice):
            if key.start is None:
                address = self.get_minimum_address()
            else:
                address = key.start
        else:
            address = key

        self.add_binary(data, address, overwrite=True)

    def __getitem__(self, key):
        """Read data from given absolute address or address range.

        """

        if isinstance(key, slice):
            if key.start is not None:
                key = slice(key.start - self.get_minimum_address(),
                            key.stop,
                            key.step)

            if key.stop is not None:
                key = slice(key.start,
                            key.stop - self.get_minimum_address(),
                            key.step)

            return self.as_binary()[key]
        else:
            relative_address = key - self.get_minimum_address()

            return self.as_binary()[relative_address:relative_address + 1]

    def add(self, data, overwrite=False):
        """Add given data by guessing its format. The format must be Motorola
        S-Records or Intel HEX. Set `overwrite` to True to allow
        already added data to be overwritten.

        """

        if is_srec(data):
            self.add_srec(data, overwrite)
        elif is_ihex(data):
            self.add_ihex(data, overwrite)
        else:
            raise Error('unsupported file format')

    def add_srec(self, records, overwrite=False):
        """Add given Motorola S-Records. Set `overwrite` to True to allow
        already added data to be overwritten.

        """

        for record in StringIO(records):
            type_, address, size, data = unpack_srec(record.strip())

            if type_ == '0':
                self.header = data
            elif type_ in '123':
                address *= self.word_size_bytes
                self.segments.add(_Segment(address, address + size,
                                           bytearray(data)),
                                  overwrite)
            elif type_ in '789':
                self.execution_start_address = address

    def add_ihex(self, records, overwrite=False):
        """Add given Intel HEX records. Set `overwrite` to True to allow
        already added data to be overwritten.

        """

        extmaximum_addressed_segment_address = 0
        extmaximum_addressed_linear_address = 0

        for record in StringIO(records):
            type_, address, size, data = unpack_ihex(record.strip())

            if type_ == 0:
                address = (address
                           + extmaximum_addressed_segment_address
                           + extmaximum_addressed_linear_address)
                address *= self.word_size_bytes
                self.segments.add(_Segment(address, address + size,
                                           bytearray(data)),
                                  overwrite)
            elif type_ == 1:
                pass
            elif type_ == 2:
                extmaximum_addressed_segment_address = int(
                    binascii.hexlify(data), 16) * 16
            elif type_ == 3:
                pass
            elif type_ == 4:
                extmaximum_addressed_linear_address = (int(
                    binascii.hexlify(data), 16) * 65536)
            elif type_ == 5:
                self.execution_start_address = int(binascii.hexlify(data), 16)
            else:
                raise Error("expected type 1..5 in record {}, but got '{}'".format(
                    record,
                    type_))

    def add_binary(self, data, address=0, overwrite=False):
        """Add given data at given address. Set `overwrite` to True to allow
        already added data to be overwritten.

        """

        self.segments.add(_Segment(address, address + len(data),
                                   bytearray(data)),
                          overwrite)

    def add_file(self, filename, overwrite=False):
        """Open given file and add its data by guessing its format. The format
        must be Motorola S-Records or Intel HEX. Set `overwrite` to
        True to allow already added data to be overwritten.

        """

        with open(filename, 'r') as fin:
            self.add(fin.read(), overwrite)

    def add_srec_file(self, filename, overwrite=False):
        """Open given Motorola S-Records file and add its records. Set
        `overwrite` to True to allow already added data to be
        overwritten.

        """

        with open(filename, "r") as fin:
            self.add_srec(fin.read(), overwrite)

    def add_ihex_file(self, filename, overwrite=False):
        """Open given Intel HEX file and add its records. Set `overwrite` to
        True to allow already added data to be overwritten.

        """

        with open(filename, "r") as fin:
            self.add_ihex(fin.read(), overwrite)

    def add_binary_file(self, filename, address=0, overwrite=False):
        """Open given binary file and add its contents. Set `overwrite` to
        True to allow already added data to be overwritten.

        """

        with open(filename, "rb") as fin:
            self.add_binary(fin.read(), address, overwrite)

    def as_srec(self, number_of_data_bytes=32, address_length_bits=32):
        """Format the binary file as Motorola S-Records records and return
        them as a string.

        :param number_of_data_bytes: Number of data bytes in each record.
        :param address_length_bits: Number of address bits in each record.
        :returns: A string of Motorola S-Records records separated by a newline.

        """

        header = []

        if self.header:
            header.append(pack_srec('0', 0, len(self.header), self.header))

        type_ = str((address_length_bits // 8) - 1)

        if type_ not in ['1', '2', '3']:
            raise Error("expected type 1..3, bit got {}".format(type_))

        data = [pack_srec(type_,
                          address // self.word_size_bytes,
                          len(data),
                          data)
                for address, data in self.segments.iter(number_of_data_bytes)]
        number_of_records = len(data)

        if number_of_records <= 0xffff:
            footer = [pack_srec('5', number_of_records, 0, None)]
        elif number_of_records <= 0xffffff:
            footer = [pack_srec('6', number_of_records, 0, None)]
        else:
            raise Error('too many records {}'.format(number_of_records))

        # Add the execution start address.
        if self.execution_start_address is not None:
            if type_ == '1':
                record = pack_srec('9', self.execution_start_address, 0, None)
            elif type_ == '2':
                record = pack_srec('8', self.execution_start_address, 0, None)
            else:
                record = pack_srec('7', self.execution_start_address, 0, None)

            footer.append(record)

        return '\n'.join(header + data + footer) + '\n'

    def as_ihex(self, number_of_data_bytes=32, address_length_bits=32):
        """Format the binary file as Intel HEX records and return them as a
        string.

        :param number_of_data_bytes: Number of data bytes in each record.
        :param address_length_bits: Number of address bits in each record.
        :returns: A string of Intel HEX records separated by a newline.

        """

        data_address = []
        extended_linear_address = 0

        for address, data in self.segments.iter(number_of_data_bytes):
            address //= self.word_size_bytes
            address_upper_16_bits = (address >> 16)
            address_lower_16_bits = (address & 0xffff)

            if address_length_bits == 32:
                # All segments are sorted by address. Update the
                # extended linear address when required.
                if address_upper_16_bits > extended_linear_address:
                    extended_linear_address = address_upper_16_bits
                    packed = pack_ihex(4,
                                       0,
                                       2,
                                       binascii.unhexlify(
                                           '%04X'
                                           % extended_linear_address))
                    data_address.append(packed)
            else:
                raise Error('expected address length 32, but got {}'.format(
                    address_length_bits))

            data_address.append(pack_ihex(0,
                                          address_lower_16_bits,
                                          len(data), data))

        footer = []

        if self.execution_start_address is not None:
            if address_length_bits == 16:
                address = binascii.unhexlify(
                    '%08X' % self.execution_start_address)
                footer.append(pack_ihex(3, 0, 4, address))
            elif address_length_bits == 32:
                address = binascii.unhexlify(
                    '%08X' % self.execution_start_address)
                footer.append(pack_ihex(5, 0, 4, address))

        footer.append(pack_ihex(1, 0, 0, None))

        return '\n'.join(data_address + footer) + '\n'

    def as_binary(self, minimum_address=None, padding=None):
        """Return a byte string of all data.

        :param minimum_address: Start address of the resulting binary data. Must
                        be less than or equal to the start address of
                        the binary data.
        :param padding: Word value of the padding between non-adjacent segments.
                        Give as a bytes object of length 1 when the word size is 8 bits, length 2 when
                        the word size is 16 bits, and so on.
        :returns: A byte string of the binary data.

        """

        if self.segments.get_size() == 0:
            return b''

        res = b''
        current_maximum_address = self.get_minimum_address()

        if padding is None:
            padding = b'\xff' * self.word_size_bytes

        if minimum_address is not None:
            if minimum_address > self.get_minimum_address():
                raise Error('the selected start address must be lower or '
                            'equal to the start address of the binary')

            current_maximum_address = minimum_address

        for address, data in self.segments.iter():
            address //= self.word_size_bytes
            res += padding * (address - current_maximum_address)
            res += data
            current_maximum_address = address + (len(data) // self.word_size_bytes)

        return res

    def as_array(self, minimum_address=None, padding=None, separator=', '):
        """Format the binary file as a string values separated by given
        separator. This function can be used to generate array
        initialization code for c and other languages.

        :param minimum_address: Start address of the resulting binary data. Must
                        be less than or equal to the start address of
                        the binary data.
        :param padding: Value of the padding between not adjacent segments.
        :param separator: Value separator.
        :returns: A string of the separated values.

        """

        binary_data = self.as_binary(minimum_address, padding)
        words = []

        for offset in range(0, len(binary_data), self.word_size_bytes):
            word = 0

            for byte in binary_data[offset:offset + self.word_size_bytes]:
                word <<= 8
                word += byte

            words.append('0x{:02x}'.format(word))

        return separator.join(words)

    def as_hexdump(self):
        """Format the binary file as a hexdump. This function can be used to
        generate array.

        :returns: A hexdump string.

        """

        def format_line(address, data):
            """`data` is a list of integers and None for unused elements.

            """

            hexdata = []

            for byte in data:
                if byte is not None:
                    elem = '{:02x}'.format(byte)
                else:
                    elem = '  '

                hexdata.append(elem)

            first_half = ' '.join(hexdata[0:8])
            second_half = ' '.join(hexdata[8:16])

            ascii = ''

            for byte in data:
                non_dot_characters = set(string.printable)
                non_dot_characters -= set(string.whitespace)
                non_dot_characters |= set(' ')

                if byte is None:
                    ascii += ' '
                elif chr(byte) in non_dot_characters:
                    ascii += chr(byte)
                else:
                    ascii += '.'

            return '{:08x}  {:23s}  {:23s}  |{:16s}|'.format(
                address, first_half, second_half, ascii)

        lines = []
        line_address = None
        line_data = []

        for address, data in self.segments.iter(16):
            if line_address is None:
                # A new line.
                line_address = address - (address % 16)
                line_data = []
            elif address > line_address + 16:
                line_data += [None] * (16 - len(line_data))
                lines.append(format_line(line_address, line_data))
                if address > line_address + 32:
                    lines.append('...')
                line_address = address - (address % 16)
                line_data = []

            line_data += [None] * (address - (line_address + len(line_data)))
            line_left = 16 - len(line_data)

            if len(data) > line_left:
                line_data += [byte for byte in data[0:line_left]]
                lines.append(format_line(line_address, line_data))
                line_address = line_address + 16
                line_data = [byte for byte in data[line_left:]]
            elif len(data) == line_left:
                line_data += [byte for byte in data]
                lines.append(format_line(line_address, line_data))
                line_address = None
            else:
                line_data += [byte for byte in data]

        if line_address is not None:
            line_data += [None] * (16  - len(line_data))
            lines.append(format_line(line_address, line_data))

        return '\n'.join(lines) + '\n'

    def fill(self, value=b'\xff'):
        """Fill all empty space inbetween segments with given value.

        :param value: Value to fill with.

        """

        previous_segment_maximum_address = None
        fill_segments = []

        for minimum_address, maximum_address, _ in self.iter_segments():
            if previous_segment_maximum_address is not None:
                fill_size = minimum_address - previous_segment_maximum_address
                fill_size_words = fill_size // self.word_size_bytes
                fill_segments.append(_Segment(
                    previous_segment_maximum_address,
                    previous_segment_maximum_address + fill_size,
                    value * fill_size_words))

            previous_segment_maximum_address = maximum_address

        for segment in fill_segments:
            self.segments.add(segment)

    def exclude(self, minimum_address, maximum_address):
        """Exclude given range and keep the rest.

        :param minimum_address: First word address to exclude (including).
        :param maximum_address: Last word address to exclude (excluding).

        """

        if maximum_address < minimum_address:
            raise Error('bad address range')

        minimum_address *= self.word_size_bytes
        maximum_address *= self.word_size_bytes
        self.segments.remove(minimum_address, maximum_address)

    def crop(self, minimum_address, maximum_address):
        """Keep given range and discard the rest.

        :param minimum_address: First word address to keep (including).
        :param maximum_address: Last word address to keep (excluding).

        """

        minimum_address *= self.word_size_bytes
        maximum_address *= self.word_size_bytes
        maximum_address_address = self.segments.get_maximum_address()
        self.segments.remove(0, minimum_address)
        self.segments.remove(maximum_address, maximum_address_address)

    def set_execution_start_address(self, address):
        """Set the execution start address to `address`.

        :param address: Execution start address.

        """

        self.execution_start_address = address

    def get_execution_start_address(self):
        """Get the execution start address.

        :returns: The execution start address.

        """

        return self.execution_start_address

    def get_minimum_address(self):
        """Get the minimum address of the data.

        :returns: The minimum address of the data.

        """

        return (self.segments.get_minimum_address() // self.word_size_bytes)

    def get_maximum_address(self):
        """Get the maximum address of the data.

        :returns: The maximum address of the data.

        """

        return (self.segments.get_maximum_address() // self.word_size_bytes)

    def info(self):
        """Return a string of human readable information about the binary
        file.

        """

        info = ''

        if self.header is not None:
            header = ''

            for b in self.header.decode('utf-8'):
                if b in string.printable:
                    header += b
                else:
                    header += '\\x%02x' % ord(b)

            info += 'Header:                  "%s"\n' % header

        if self.execution_start_address is not None:
            info += ('Execution start address: 0x%08x\n'
                     % self.execution_start_address)

        info += 'Data address ranges:\n'

        for minimum_address, maximum_address, _ in self.iter_segments():
            minimum_address //= self.word_size_bytes
            maximum_address //= self.word_size_bytes
            info += '                         0x%08x - 0x%08x\n' % (
                minimum_address,
                maximum_address)

        return info

    def iter_segments(self):
        """Iterate over all data segments, returning them one at a time.

        """

        for segment in self.segments.list:
            yield segment.minimum_address, segment.maximum_address, segment.data

    def __iadd__(self, other):
        self.add_srec(other.as_srec())

        return self

    def __str__(self):
        return self.segments.__str__()


def _do_info(args):
    for binfile in args.binfile:
        f = BinFile()
        f.add_file(binfile)
        print(f.info())


def _main():
    parser = argparse.ArgumentParser(
        description='Various binary file format utilities.')

    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('--version',
                        action='version',
                        version=__version__,
                        help='Print version information and exit.')

    # Workaround to make the subparser required in Python 3.
    subparsers = parser.add_subparsers(title='subcommands',
                                       dest='subcommand')
    subparsers.required = True

    # The 'info' subparser.
    info_parser = subparsers.add_parser(
        'info',
        description='Print general information about given file(s).')
    info_parser.add_argument('binfile',
                             nargs='+',
                             help='One or more binary format files.')
    info_parser.set_defaults(func=_do_info)

    args = parser.parse_args()

    if args.debug:
        args.func(args)
    else:
        try:
            args.func(args)
        except BaseException as e:
            sys.exit(str(e))
