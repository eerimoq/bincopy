"""Mangling of various file formats that conveys binary information
(Motorola S-Record, Intel HEX and binary files).

"""

from __future__ import print_function

import binascii
import io
import string

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

__author__ = 'Erik Moqvist'
__version__ = '5.2.0'

DEFAULT_WORD_SIZE = 8


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
        raise Error('Bad Motorola S-Record type %s.' % type_)

    if data:
        line += binascii.hexlify(data).decode('utf-8').upper()

    return 'S%s%s%02X' % (type_, line, crc_srec(line))


def unpack_srec(record):
    """Unpack given Motorola S-Record record into variables.

    """

    if record[0] != 'S':
        raise Error('bad srecord "%s"' % record)

    size = int(record[2:4], 16)
    type_ = record[1:2]

    if type_ in '0159':
        width = 4
    elif type_ in '268':
        width = 6
    elif type_ in '37':
        width = 8
    else:
        raise Error('Bad Motorola S-Record type %s.' % type_)

    address = int(record[4:4+width], 16)
    data = binascii.unhexlify(record[4 + width:4 + 2 * size - 2])
    real_crc = int(record[4 + 2 * size - 2:], 16)
    calc_crc = crc_srec(record[2:4 + 2 * size - 2])

    if real_crc != calc_crc:
        raise Error('Bad Motorola S-Record CRC for record '
                    '"{}" ({:02x} != {:02x})'.format(
                        record, real_crc, calc_crc))

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

    if record[0] != ':':
        raise Error('bad intel hex record "%s"' % record)

    size = int(record[1:3], 16)
    address = int(record[3:7], 16)
    type_ = int(record[7:9], 16)

    if size > 0:
        data = binascii.unhexlify(record[9:9 + 2 * size])
    else:
        data = ''

    real_crc = int(record[9 + 2 * size:], 16)
    calc_crc = crc_ihex(record[1:9 + 2 * size])

    if real_crc != calc_crc:
        print('warning: bad Intel HEX crc for record '
              '"{}" ({:02x} != {:02x})'.format(
                record, real_crc, calc_crc))

    return (type_, address, size, data)


class _Segment(object):
    """A segment is a chunk data with given begin and end address.

    """

    def __init__(self, minimum_address, maximum_address, data):
        self.minimum_address = minimum_address
        self.maximum_address = maximum_address
        self.data = data

    def add_data(self, minimum_address, maximum_address, data):
        """Add given data to this segment. The added data must be adjecent to
        the current segment data, otherwise an exception is thrown.

        """

        if minimum_address == self.maximum_address:
            self.maximum_address = maximum_address
            self.data += data
        elif maximum_address == self.minimum_address:
            self.minimum_address = minimum_address
            self.data = data + self.data
        else:
            raise Error('Data added to a segment must be adjacent '
                        'to the original segment data.')

    def remove_data(self, minimum_address, maximum_address):
        """Remove given data range from this segment. Returns the second
        segment if the removed data splits this segment in two.

        """

        if (minimum_address >= self.maximum_address) and (maximum_address <= self.minimum_address):
            raise Error('Cannot remove data that is not part of the segment.')

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

    def add(self, segment):
        """Add segments by ascending address.

        """

        if self.list:
            if segment.minimum_address == self.current_segment.maximum_address:
                # fast insertion for adjecent segments
                self.current_segment.add_data(segment.minimum_address,
                                              segment.maximum_address,
                                              segment.data)
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
                    s.add_data(segment.minimum_address, segment.maximum_address, segment.data)
                    segment = s

                self.current_segment = segment
                self.current_segment_index = i

            # merge adjacent
            if self.current_segment is not self.list[-1]:
                s = self.list[self.current_segment_index+1]

                if self.current_segment.maximum_address > s.minimum_address:
                    raise IndexError('cannot add overlapping segments')
                if self.current_segment.maximum_address == s.minimum_address:
                    self.current_segment.add_data(s.minimum_address, s.maximum_address, s.data)
                    del self.list[self.current_segment_index+1]
        else:
            self.list.append(segment)
            self.current_segment = segment
            self.current_segment_index = 0

    def remove(self, segment):
        if not self.list:
            return

        for i, s in enumerate(self.list):
            if segment.minimum_address <= s.maximum_address:
                break

        if segment.minimum_address >= s.maximum_address:
            # non-overlapping after
            pass
        elif segment.maximum_address <= s.minimum_address:
            # non-overlapping before
            pass
        else:
            # overlapping, remove overwritten parts segments
            split = s.remove_data(segment.minimum_address, segment.maximum_address)

            if s.minimum_address == s.maximum_address:
                del self.list[i]
            else:
                i += 1

            if split:
                self.list.insert(i, split)
                i += 1

            for s in self.list[i:]:
                if segment.maximum_address <= s.minimum_address:
                    break

                split = s.remove_data(segment.minimum_address, segment.maximum_address)

                if split:
                    raise

                if s.minimum_address == s.maximum_address:
                    del self.list[i]

    def iter(self, size=32):
        for segment in self.list:
            data = segment.data
            address = segment.minimum_address

            for offset in range(0, len(data), size):
                yield address + offset, data[offset:offset + size]

    def get_minimum_address(self):
        if not self.list:
            return None

        return self.list[0].minimum_address

    def get_maximum_address(self):
        if not self.list:
            return None

        return self.list[-1].maximum_address

    def __str__(self):
        return '\n'.join([s.__str__() for s in self.list])

    def get_size(self):
        if not self.list:
            return 0

        return self.get_maximum_address() - self.get_minimum_address()


class BinFile(object):

    def __init__(self, word_size=DEFAULT_WORD_SIZE):
        if (word_size % 8) != 0:
            raise Error('Word size must be a multiple of 8 bits.')
        self.word_size = word_size
        self.word_size_bytes = (word_size // 8)
        self.header = None
        self.execution_start_address = None
        self.segments = _Segments()

    def add_srec(self, records):
        """Add Motorola S-Records from given records string.

        """

        for record in StringIO(records):
            type_, address, size, data = unpack_srec(record)

            if type_ == '0':
                self.header = data
            elif type_ in '123':
                address *= self.word_size_bytes
                self.segments.add(_Segment(address, address + size,
                                           bytearray(data)))
            elif type_ in '789':
                self.execution_start_address = address

    def add_ihex(self, records):
        """Add Intel HEX records from given records string.

        """

        extmaximum_addressed_segment_address = 0
        extmaximum_addressed_linear_address = 0

        for record in StringIO(records):
            type_, address, size, data = unpack_ihex(record)

            if type_ == 0:
                address = (address
                           + extmaximum_addressed_segment_address
                           + extmaximum_addressed_linear_address)
                address *= self.word_size_bytes
                self.segments.add(_Segment(address, address + size,
                                           bytearray(data)))
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
                raise Error('Bad ihex type %d.' % type_)

    def add_binary(self, data, address=0):
        """Add given data at given address.

        """

        self.segments.add(_Segment(address, address + len(data),
                                   bytearray(data)))

    def add_srec_file(self, filename):
        """Open given Motorola S-Records file and add its records.

        """

        with open(filename, "r") as fin:
            self.add_srec(fin.read())

    def add_ihex_file(self, filename):
        """Open given Intel HEX file and add its records.

        """

        with open(filename, "r") as fin:
            self.add_ihex(fin.read())

    def add_binary_file(self, filename, address=0):
        """Open given binary file and add its contents.

        """

        with open(filename, "rb") as fin:
            self.add_binary(fin.read(), address)

    def as_srec(self, size=32, address_length=32):
        """Return a string of Motorola S-Records of all data.

        """

        header = []

        if self.header:
            header.append(pack_srec('0', 0, len(self.header), self.header))

        type_ = str((address_length // 8) - 1)
        data = [pack_srec(type_,
                          address // self.word_size_bytes,
                          len(data),
                          data)
                for address, data in self.segments.iter(size)]
        number_of_records = len(data)

        if number_of_records <= 0xffff:
            footer = [pack_srec('5', number_of_records, 0, None)]
        elif number_of_records <= 0xffffff:
            footer = [pack_srec('6', number_of_records, 0, None)]
        else:
            raise Error('too many records: {}'.format(number_of_records))

        if ((self.execution_start_address is not None)
            and (self.segments.get_minimum_address() == 0)):
            if type_ == '1':
                footer.append(pack_srec('9',
                                        self.execution_start_address,
                                        0,
                                        None))
            elif type_ == '2':
                footer.append(pack_srec('8',
                                        self.execution_start_address,
                                        0,
                                        None))
            elif type_ == '3':
                footer.append(pack_srec('7',
                                        self.execution_start_address,
                                        0,
                                        None))

        return '\n'.join(header + data + footer) + '\n'

    def as_ihex(self, size=32, address_length=32):
        """Return a string of Intel HEX records of all data.

        """

        data_address = []
        extended_linear_address = 0

        for address, data in self.segments.iter(size):
            address //= self.word_size_bytes
            address_upper_16_bits = (address >> 16)
            address_lower_16_bits = (address & 0xffff)

            if address_length == 32:
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
                raise Error('unsupported address length %d'
                                 % address_length)

            data_address.append(pack_ihex(0,
                                          address_lower_16_bits,
                                          len(data), data))

        footer = []

        if self.execution_start_address is not None:
            if address_length == 16:
                address = binascii.unhexlify('%08X'
                                             % self.execution_start_address)
                footer.append(pack_ihex(3, 0, 4, address))
            elif address_length == 32:
                address = binascii.unhexlify('%08X'
                                             % self.execution_start_address)
                footer.append(pack_ihex(5, 0, 4, address))

        footer.append(pack_ihex(1, 0, 0, None))

        return '\n'.join(data_address + footer) + '\n'

    def as_binary(self, minimum_address=None, padding=b'\xff'):
        """Return a byte string of all data.

        :param minimum_address: Start address of the resulting binary data. Must
                        be less than or equal to the start address of
                        the binary data.
        :param padding: Value of the padding between not adjecent segments.
        :returns: A byte string of the binary data.

         """

        if self.segments.get_size() == 0:
            return b''

        res = b''
        current_maximum_address = self.get_minimum_address()

        if minimum_address is not None:
            if minimum_address > self.get_minimum_address():
                raise Error(('The selected start address must be lower of equal to '
                             'the start address of the binary.'))

            current_maximum_address = minimum_address

        for address, data in self.segments.iter():
            address //= self.word_size_bytes
            res += padding * (address - current_maximum_address)
            res += data
            current_maximum_address = address + len(data)

        return res

    def as_array(self, minimum_address=None, padding=b'\xff', separator=', '):
        """Return a string of values separated by given separator. This
        function can be used to generate array initialization code for
        c and other languages.

        :param minimum_address: Start address of the resulting binary data. Must
                        be less than or equal to the start address of
                        the binary data.
        :param padding: Value of the padding between not adjecent segments.
        :param separator: Value separator.
        :returns: A string of separated values.

        """

        binary_data = self.as_binary(minimum_address, padding)
        words = []

        for offset in range(0, len(binary_data), self.word_size_bytes):
            word = 0

            for byte in binary_data[offset:offset + self.word_size_bytes]:
                word <<= 8;
                word += byte

            words.append('0x{:02x}'.format(word))

        return separator.join(words)

    def as_hexdump(self):
        """Return a hexdump of all data.

        :returns: A string of the hexdump.
        """

        def create_line(address, data):
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
                lines.append(create_line(line_address, line_data))
                if address > line_address + 32:
                    lines.append('...')
                line_address = address - (address % 16)
                line_data = []

            line_data += [None] * (address - (line_address + len(line_data)))
            line_left = 16 - len(line_data)

            if len(data) > line_left:
                line_data += [byte for byte in data[0:line_left]]
                lines.append(create_line(line_address, line_data))
                line_address = line_address + 16
                line_data = [byte for byte in data[line_left:]]
            elif len(data) == line_left:
                line_data += [byte for byte in data]
                lines.append(create_line(line_address, line_data))
                line_address = None
            else:
                line_data += [byte for byte in data]

        if line_address is not None:
            line_data += [None] * (16  - len(line_data))
            lines.append(create_line(line_address, line_data))

        return '\n'.join(lines) + '\n'

    def fill(self, value=b'\xff'):
        """Fill all empty space inbetween segments with given value.

        :param value: Value to fill with.
        """

        if self.segments.get_size() == 1:
            return

        previous_segment_maximum_address_address = None
        fill_segments = []

        for segment in self.segments.list:
            if previous_segment_maximum_address_address is not None:
                fill_size = segment.minimum_address - previous_segment_maximum_address_address
                fill_size_words = fill_size // self.word_size_bytes
                fill_segments.append(_Segment(previous_segment_maximum_address_address,
                                              previous_segment_maximum_address_address + fill_size,
                                              value * fill_size_words))

            previous_segment_maximum_address_address = segment.maximum_address

        for segment in fill_segments:
            self.segments.add(segment)

    def exclude(self, begin_address, end_address):
        """Exclude given range and keep the rest.

        :param begin_address: First word address to exclude (including).
        :param end_address: Last word address to exclude (excluding).

        """

        begin_address *= self.word_size_bytes
        end_address *= self.word_size_bytes
        self.segments.remove(_Segment(begin_address, end_address, bytearray()))

    def crop(self, begin_address, end_address):
        """Keep given range and discard the rest.

        :param begin_address: First word address to keep (including).
        :param end_address: Last word address to keep (excluding).

        """

        begin_address *= self.word_size_bytes
        end_address *= self.word_size_bytes
        maximum_address_address = self.segments.get_maximum_address()
        self.segments.remove(_Segment(0, begin_address, bytearray()))
        self.segments.remove(_Segment(end_address, maximum_address_address, bytearray()))

    def set_execution_start_address(self, address):
        """Set execution start address to `address`.

        """

        self.execution_start_address = address

    def get_execution_start_address(self):
        """Get execution start address.

        """

        return self.execution_start_address

    def get_minimum_address(self):
        """Get minimum_address address.

        """

        return (self.segments.get_minimum_address() // self.word_size_bytes)

    def get_maximum_address(self):
        """Get maximum_address address.

        """

        return (self.segments.get_maximum_address() // self.word_size_bytes)

    def info(self, type_, filename):
        """Return string of human readable binary information.

        """

        if type_ == 'srec':
            file_format = 'motorola s-record'
        elif type_ == 'ihex':
            file_format = 'intel hex'
        elif type_ == 'binary':
            file_format = 'binary'
        else:
            raise Error('bad file format type %s' % type)

        info = 'file:   %s\nformat: %s\n' % (filename, file_format)

        if self.header is not None:
            header = ''

            for b in self.header.decode('utf-8'):
                if b in string.printable:
                    header += b
                else:
                    header += '\\x%02x' % ord(b)

            info += 'header: "%s"\n' % header

        if self.execution_start_address is not None:
            info += ('execution start address: 0x%08x\n'
                     % self.execution_start_address)

        info += 'data:\n'

        for minimum_address, maximum_address, _ in self.iter_segments():
            minimum_address //= self.word_size_bytes
            maximum_address //= self.word_size_bytes
            info += '        0x%08x - 0x%08x\n' % (minimum_address, maximum_address)

        return info

    def iter_segments(self):
        """Iterate over data segments.

        """

        for segment in self.segments.list:
            yield segment.minimum_address, segment.maximum_address, segment.data

    def __iadd__(self, other):
        self.add_srec(io.StringIO(other.as_srec()))

        return self

    def __str__(self):
        return self.segments.__str__()
