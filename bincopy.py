#!/usr/bin/env python
#
# Mangling of various file formats that conveys binary
# information (Motorola S-Record, Intel HEX and binary files).

import binascii
import io
import string

__author__ = 'Erik Moqvist'
__version__ = '2.1.3'

DEFAULT_WORD_SIZE = 8


class Error(Exception):
    """Bincopy base exception.

    """

    pass


def crc_srec(hexstr):
    """Calculate crc for given Motorola S-Record hexstring.

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
    """Pack given variables into a Motorola S-Record string.

    """

    if type_ in '0159':
        line = '%02X%04X' % (size + 2 + 1, address)
    elif type_ in '268':
        line = '%02X%06X' % (size + 3 + 1, address)
    elif type_ in '37':
        line = '%02X%08X' % (size + 4 + 1, address)
    else:
        raise Error('bad srec type %s' % type_)

    if data:
        line += binascii.hexlify(data).decode('utf-8').upper()

    return 'S%s%s%02X' % (type_, line, crc_srec(line))


def unpack_srec(srec):
    """Unpack given Motorola S-Record string into variables.

    """

    if srec[0] != 'S':
        raise Error('bad srecord "%s"' % srec)

    size = int(srec[2:4], 16)
    type_ = srec[1:2]

    if type_ in '0159':
        width = 4
    elif type_ in '268':
        width = 6
    elif type_ in '37':
        width = 8
    else:
        raise Error('bad srec type "%s"' % type_)

    address = int(srec[4:4+width], 16)
    data = binascii.unhexlify(srec[4 + width:4 + 2 * size - 2])
    real_crc = int(srec[4 + 2 * size - 2:], 16)
    calc_crc = crc_srec(srec[2:4 + 2 * size - 2])

    if real_crc != calc_crc:
        fmt = ('warning: bad Motorola S-Record crc '
               'for record "%s" (%02x != %02x)')
        print(fmt % (srec, real_crc, calc_crc))

    return (type_, address, size - 1 - width // 2, data)


def pack_ihex(type_, address, size, data):
    """Pack given variables into an Intel HEX record string.

    """

    line = '%02X%04X%02X' % (size, address, type_)

    if data:
        line += binascii.hexlify(data).decode('utf-8').upper()

    return ':%s%02X' % (line, crc_ihex(line))


def unpack_ihex(ihex):
    """Unpack given Intel HEX record string into variables.

    """

    if ihex[0] != ':':
        raise Error('bad intel hex record "%s"' % ihex)

    size = int(ihex[1:3], 16)
    address = int(ihex[3:7], 16)
    type_ = int(ihex[7:9], 16)

    if size > 0:
        data = binascii.unhexlify(ihex[9:9 + 2 * size])
    else:
        data = ''

    real_crc = int(ihex[9 + 2 * size:], 16)
    calc_crc = crc_ihex(ihex[1:9 + 2 * size])

    if real_crc != calc_crc:
        fmt = 'warning: bad Intel HEX crc for record "%s" (%02x != %02x)'
        print(fmt % (ihex, real_crc, calc_crc))

    return (type_, address, size, data)


class _Segment(object):

    def __init__(self, minimum, maximum, data):
        self.minimum = minimum
        self.maximum = maximum
        self.data = data

    def add_data(self, minimum, maximum, data):
        if minimum == self.maximum:
            self.maximum = maximum
            self.data += data
        elif maximum == self.minimum:
            self.minimum = minimum
            self.data = data + self.data
        else:
            fmt = 'segments must be adjacent (%d != %d and %d != %d)'
            raise Error(fmt % (minimum, self.maximum, maximum, self.minimum))

    def remove_data(self, minimum, maximum):
        if (minimum >= self.maximum) and (maximum <= self.minimum):
            raise Error('segments must be overlapping')

        s1 = _Segment(0, 0, [])
        s2 = _Segment(0, 0, [])

        if minimum > self.minimum:
            s1.minimum = self.minimum
            s1.maximum = minimum
            size = (minimum - self.minimum)

            for d in self.data:
                if size < len(d):
                    s1.data.append(d[0:size])
                    break

                s1.data.append(d)
                size -= len(d)

        if maximum < self.maximum:
            s2.minimum = maximum
            s2.maximum = self.maximum
            skip = (maximum - self.minimum)

            for i, d in enumerate(self.data):
                if skip < len(d):
                    s2.data.append(d[skip:])
                    break
                skip -= len(d)

            s2.data += self.data[i+1:]

        if len(s1.data) > 0:
            self.minimum = s1.minimum
            self.maximum = s1.maximum
            self.data = s1.data
            if len(s2.data) > 0:
                return s2
        elif len(s2.data) > 0:
            self.minimum = s2.minimum
            self.maximum = s2.maximum
            self.data = s2.data
            return None
        else:
            self.maximum = self.minimum
            self.data = []
            return None

    def __str__(self):
        return '[%#x .. %#x]: %s' % (self.minimum,
                                     self.maximum,
                                     ''.join([binascii.hexlify(d).decode('utf-8')
                                              for d in self.data]))


class _Segments(object):

    def __init__(self):
        self.current_segment = None
        self.current_segment_index = None
        self.list = []

    def add(self, segment):
        """Add segments by ascending address.

        """

        if self.list:
            if segment.minimum == self.current_segment.maximum:
                # fast insertion for adjecent segments
                self.current_segment.add_data(segment.minimum,
                                              segment.maximum,
                                              segment.data)
            else:
                # linear insert
                for i, s in enumerate(self.list):
                    if segment.minimum <= s.maximum:
                        break

                if segment.minimum > s.maximum:
                    # non-overlapping, non-adjacent after
                    self.list.append(segment)
                elif segment.maximum < s.minimum:
                    # non-overlapping, non-adjacent before
                    self.list.insert(i, segment)
                else:
                    # adjacent or overlapping
                    s.add_data(segment.minimum, segment.maximum, segment.data)
                    segment = s

                self.current_segment = segment
                self.current_segment_index = i

            # merge adjacent
            if self.current_segment is not self.list[-1]:
                s = self.list[self.current_segment_index+1]

                if self.current_segment.maximum > s.minimum:
                    raise IndexError('cannot add overlapping segments')
                if self.current_segment.maximum == s.minimum:
                    self.current_segment.add_data(s.minimum, s.maximum, s.data)
                    del self.list[self.current_segment_index+1]
        else:
            self.list.append(segment)
            self.current_segment = segment
            self.current_segment_index = 0

    def remove(self, segment):
        if not self.list:
            return

        for i, s in enumerate(self.list):
            if segment.minimum <= s.maximum:
                break

        if segment.minimum >= s.maximum:
            # non-overlapping after
            pass
        elif segment.maximum <= s.minimum:
            # non-overlapping before
            pass
        else:
            # overlapping, remove overwritten parts segments
            split = s.remove_data(segment.minimum, segment.maximum)

            if s.minimum == s.maximum:
                del self.list[i]
            else:
                i += 1

            if split:
                self.list.insert(i, split)
                i += 1

            for s in self.list[i:]:
                if segment.maximum <= s.minimum:
                    break

                split = s.remove_data(segment.minimum, segment.maximum)

                if split:
                    raise

                if s.minimum == s.maximum:
                    del self.list[i]

    def iter(self, size=32):
        for s in self.list:
            data = b''
            address = s.minimum

            for b in s.data:
                while len(b) > 0:
                    if len(data) + len(b) >= size:
                        left = size - len(data)
                        data += b[:left]
                        b = b[left:]
                        yield address, data
                        data = b''
                        address += size
                    else:
                        data += b
                        b = b''

            if len(data) > 0:
                yield address, data

    def get_minimum_address(self):
        if not self.list:
            return None

        return self.list[0].minimum

    def get_maximum_address(self):
        if not self.list:
            return None

        return self.list[-1].maximum

    def __str__(self):
        return '\n'.join([s.__str__() for s in self.list])


class File(object):

    def __init__(self, word_size=DEFAULT_WORD_SIZE):
        if (word_size % 8) != 0:
            raise Error('Word size must be a multiple of 8 bits.')
        self.word_size = word_size
        self.word_size_bytes = (word_size // 8)
        self.header = None
        self.execution_start_address = None
        self.segments = _Segments()

    def add_srec(self, iostream):
        """Add Motorola S-Records from given iostream.

        """

        for record in iostream:
            type_, address, size, data = unpack_srec(record)

            if type_ == '0':
                self.header = data
            elif type_ in '123':
                address *= self.word_size_bytes
                self.segments.add(_Segment(address, address + size, [data]))
            elif type_ in '789':
                self.execution_start_address = address

    def add_ihex(self, iostream):
        """Add Intel HEX records from given iostream.

        """

        extmaximumed_segment_address = 0
        extmaximumed_linear_address = 0

        for record in iostream:
            type_, address, size, data = unpack_ihex(record)

            if type_ == 0:
                address = (address
                           + extmaximumed_segment_address
                           + extmaximumed_linear_address)
                address *= self.word_size_bytes
                self.segments.add(_Segment(address, address + size, [data]))
            elif type_ == 1:
                pass
            elif type_ == 2:
                extmaximumed_segment_address = int(binascii.hexlify(data), 16) * 16
            elif type_ == 3:
                pass
            elif type_ == 4:
                extmaximumed_linear_address = (int(binascii.hexlify(data), 16)
                                           * 65536)
            elif type_ == 5:
                print('warning: ignoring type 5')
            else:
                raise Error('bad ihex type %d' % type_)

    def add_binary(self, iostream, address=0):
        """Add binary data at `address` from `iostream`.

        """

        data = iostream.read()
        self.segments.add(_Segment(address, address + iostream.tell(), [data]))

    def as_srec(self, size=32, address_length=32):
        """Return string of Motorola S-Records of all data.

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
        footer = [pack_srec('5', len(data), 0, None)]

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
        """Return string of Intel HEX records of all data.

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
                                       binascii.unhexlify('%04X'
                                                          % extended_linear_address))
                    data_address.append(packed)
            else:
                raise Error('unsupported address length %d'
                                 % address_length)

            data_address.append(pack_ihex(0, address_lower_16_bits, len(data), data))

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

    def as_binary(self, minimum=None, padding=b'\xff'):
        """Return a byte string of all data.

        :param minimum: Start address of the resulting binary data. Must
                      be less than or equal to the start address of
                      the binary data.
        :param padding: Value of the padding between not adjecent segments.
        :returns: A byte string of the binary data.

        """

        res = b''
        maximum_address = self.get_minimum_address()

        if minimum is not None:
            if minimum > self.get_minimum_address():
                raise Error(('The selected start address must be lower of equal to '
                             'the start address of the binary.'))

            maximum_address = minimum

        for address, data in self.segments.iter():
            address //= self.word_size_bytes
            res += padding * (address - maximum_address)
            res += data
            maximum_address = address + len(data)

        return res

    def exclude(self, minimum, maximum):
        """Exclude range including `minimum`, not including `maximum`.

        :param minimum: Minimum address to exclude (including).
        :param maximum: Maximum address to exclude (excluding).

        """

        minimum *= self.word_size_bytes
        maximum *= self.word_size_bytes
        self.segments.remove(_Segment(minimum, maximum, None))

    def set_execution_start_address(self, address):
        """Set execution start address to `address`.

        """

        self.execution_start_address = address

    def get_execution_start_address(self):
        """Get execution start address.

        """

        return self.execution_start_address

    def get_minimum_address(self):
        """Get minimum address.

        """

        return (self.segments.get_minimum_address() // self.word_size_bytes)

    def get_maximum_address(self):
        """Get maximum address.

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

        for minimum, maximum, _ in self.iter_segments():
            minimum //= self.word_size_bytes
            maximum //= self.word_size_bytes
            info += '        0x%08x - 0x%08x\n' % (minimum, maximum)

        return info

    def iter_segments(self):
        """Iterate over data segments.

        """

        for segment in self.segments.list:
            yield segment.minimum, segment.maximum, segment.data

    def __iadd__(self, other):
        self.add_srec(io.StringIO(other.as_srec()))

        return self

    def __str__(self):
        return self.segments.__str__()
