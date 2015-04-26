#!/usr/bin/env python
#
# Mangling of various file formats that conveys binary
# information (Motorola S-Record, Intel HEX and binary files).

import sys
import binascii
import io
import string

__author__ = 'Erik Moqvist'


def crc_srec(hexstr):
    '''
    Calculate crc for given Motorola S-Record hexstring.
    '''
    crc = sum(bytearray(binascii.unhexlify(hexstr)))
    crc &= 0xff
    crc ^= 0xff
    return crc


def crc_ihex(hexstr):
    '''
    Calculate crc for given Intel HEX hexstring.
    '''
    crc = sum(bytearray(binascii.unhexlify(hexstr)))
    crc &= 0xff
    crc = (0x100 - crc)
    return crc


def pack_srec(type, address, size, data):
    '''
    Pack given variables into a Motorola S-Record string.
    '''
    if type in '0159':
        str = '%02X%04X' % (size + 2 + 1, address)
    elif type in '268':
        str = '%02X%06X' % (size + 3 + 1, address)
    elif type in '37':
        str = '%02X%08X' % (size + 4 + 1, address)
    else:
        raise ValueError('bad srec type %s' % type)
    if data:
        str += binascii.hexlify(data).decode('utf-8').upper()
    crc = crc_srec(str)
    return 'S%s%s%02X' % (type, str, crc)


def unpack_srec(srec):
    '''
    Unpack given Motorola S-Record string into variables.
    '''
    if srec[0] != 'S':
        raise ValueError('bad srecord "%s"' % srec)
    size = int(srec[2:4], 16)
    type = srec[1:2]
    if type in '0159':
        width = 4
    elif type in '268':
        width = 6
    elif type in '37':
        width = 8
    else:
        raise ValueError('bad srec type "%s"' % type)
    address = int(srec[4:4+width], 16)
    data = bytearray(binascii.unhexlify(srec[4 + width:4 + 2 * size - 2]))
    crc = int(srec[4 + 2 * size - 2:], 16)
    crc2 = crc_srec(srec[2:4 + 2 * size - 2])
    if crc != crc2:
        fmt = ('warning: bad Motorola S-Record crc '
               'for record "%s" (%02x != %02x)')
        print(fmt % (srec, crc, crc2))
    return (type, address, size - 1 - width // 2, data)


def pack_ihex(type, address, size, data):
    '''
    Pack given variables into an Intel HEX record string.
    '''
    str = '%02X%04X%02X' % (size, address, type)
    if data:
        str += binascii.hexlify(data).decode('utf-8').upper()
    crc = crc_ihex(str)
    return ':%s%02X' % (str, crc)


def unpack_ihex(ihex):
    '''
    Unpack given Intel HEX record string into variables.
    '''
    if ihex[0] != ':':
        raise ValueError('bad intel hex record "%s"' % ihex)
    size = int(ihex[1:3], 16)
    address = int(ihex[3:7], 16)
    type = int(ihex[7:9], 16)
    if size > 0:
        data = binascii.unhexlify(ihex[9:9 + 2 * size])
    else:
        data = ''
    crc = int(ihex[9 + 2 * size:], 16)
    crc2 = crc_ihex(ihex[1:9 + 2 * size])
    if crc != crc2:
        fmt = 'warning: bad Intel HEX crc for record "%s" (%02x != %02x)'
        print(fmt % (ihex, crc, crc2))
    return (type, address, size, data)


class _Segment(object):

    def __init__(self, begin, end, data):
        self.begin = begin
        self.end = end
        self.data = data

    def add_data(self, begin, end, data):
        if begin == self.end:
            self.end = end
            self.data += data
        elif end == self.begin:
            self.begin = begin
            self.data = data + self.data
        else:
            fmt = 'segments must be adjacent (%d != %d and %d != %d)'
            raise ValueError(fmt % (begin, self.end, end, self.begin))

    def remove_data(self, begin, end):
        if (begin >= self.end) and (end <= self.begin):
            raise ValueError('segments must be overlapping')
        s1 = _Segment(0, 0, [])
        s2 = _Segment(0, 0, [])
        if begin > self.begin:
            s1.begin = self.begin
            s1.end = begin
            size = (begin - self.begin)
            for d in self.data:
                if size < len(d):
                    s1.data.append(d[0:size])
                    break
                s1.data.append(d)
                size -= len(d)
        if end < self.end:
            s2.begin = end
            s2.end = self.end
            skip = (end - self.begin)
            for i, d in enumerate(self.data):
                if skip < len(d):
                    s2.data.append(d[skip:])
                    break
                skip -= len(d)
            s2.data += self.data[i+1:]
        if len(s1.data) > 0:
            self.begin = s1.begin
            self.end = s1.end
            self.data = s1.data
            if len(s2.data) > 0:
                return s2
        elif len(s2.data) > 0:
            self.begin = s2.begin
            self.end = s2.end
            self.data = s2.data
            return None
        else:
            self.end = self.begin
            self.data = []
            return None

    def __str__(self):
        return '[%#x .. %#x]: %s' % (self.begin,
                                     self.end,
                                     ''.join([binascii.hexlify(d)
                                              for d in self.data]))


class _Segments(object):

    def __init__(self):
        self.current_segment = None
        self.current_segment_index = None
        self.list = []

    def add(self, segment):
        if self.list:
            if segment.begin == self.current_segment.end:
                # fast insertion for adjecent segments
                self.current_segment.add_data(segment.begin,
                                              segment.end,
                                              segment.data)
            else:
                # linear insert
                for i, s in enumerate(self.list):
                    if segment.begin <= s.end:
                        break
                if segment.begin > s.end:
                    # non-overlapping, non-adjacent after
                    self.list.append(segment)
                elif segment.end < s.begin:
                    # non-overlapping, non-adjacent before
                    self.list.insert(i, segment)
                else:
                    # adjacent or overlapping
                    s.add_data(segment.begin, segment.end, segment.data)
                    segment = s
                self.current_segment = segment
                self.current_segment_index = i

            # merge adjacent
            if self.current_segment is not self.list[-1]:
                s = self.list[self.current_segment_index+1]
                if self.current_segment.end > s.begin:
                    raise IndexError('cannot add overlapping segments')
                if self.current_segment.end == s.begin:
                    self.current_segment.add_data(s.begin, s.end, s.data)
                    del self.list[self.current_segment_index+1]
        else:
            self.list.append(segment)
            self.current_segment = segment
            self.current_segment_index = 0

    def remove(self, segment):
        if not self.list:
            return
        for i, s in enumerate(self.list):
            if segment.begin <= s.end:
                break
        if segment.begin >= s.end:
            # non-overlapping after
            pass
        elif segment.end <= s.begin:
            # non-overlapping before
            pass
        else:
            # overlapping, remove overwritten parts segments
            split = s.remove_data(segment.begin, segment.end)
            if s.begin == s.end:
                del self.list[i]
            else:
                i += 1
            if split:
                self.list.insert(i, split)
                i += 1
            for s in self.list[i:]:
                if segment.end <= s.begin:
                    break
                split = s.remove_data(segment.begin, segment.end)
                if split:
                    raise
                if s.begin == s.end:
                    del self.list[i]

    def iter(self, size=32):
        for s in self.list:
            data = b''
            address = s.begin
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
        return self.list[0].begin

    def get_maximum_address(self):
        if not self.list:
            return None
        return self.list[-1].end

    def __str__(self):
        return '\n'.join([s.__str__() for s in self.list])


class File(object):

    def __init__(self):
        self.header = None
        self.execution_start_address = None
        self.segments = _Segments()

    def add_srec(self, iostream):
        '''
        Add Motorola S-Records from given iostream.
        '''
        for record in iostream:
            type, address, size, data = unpack_srec(record)
            if type == '0':
                self.header = data
            elif type in '123':
                self.segments.add(_Segment(address, address + size, [data]))
            elif type in '789':
                self.execution_start_address = address

    def add_ihex(self, iostream):
        '''
        Add Intel HEX records from given iostream.
        '''
        extended_segment_address = 0
        extended_linear_address = 0
        for record in iostream:
            type, address, size, data = unpack_ihex(record)
            if type == 0:
                address = (address
                           + extended_segment_address
                           + extended_linear_address)
                self.segments.add(_Segment(address, address + size, [data]))
            elif type == 1:
                pass
            elif type == 2:
                extended_segment_address = int(binascii.hexlify(data), 16) * 16
            elif type == 3:
                pass
            elif type == 4:
                extended_linear_address = (int(binascii.hexlify(data), 16)
                                           * 65536)
            elif type == 5:
                print('warning: ignoring type 5')
            else:
                raise ValueError('bad ihex type %d' % type)

    def add_binary(self, iostream, address=0):
        '''
        Add binary data at `address` from `iostream`.
        '''
        data = bytearray(iostream.read())
        self.segments.add(_Segment(address, address + iostream.tell(), [data]))

    def as_srec(self, size=32, address_length=32):
        '''
        Return string of Motorola S-Records of all data.
        '''
        header = []
        if self.header:
            header.append(pack_srec('0', 0, len(self.header), self.header))
        type = str((address_length // 8) - 1)
        data = [pack_srec(type, address, len(data), data)
                for address, data in self.segments.iter(size)]
        footer = [pack_srec('5', len(data), 0, None)]
        if ((self.execution_start_address is not None)
            and (self.segments.get_minimum_address() == 0)):
            if type == '1':
                footer.append(pack_srec('9',
                                        self.execution_start_address,
                                        0,
                                        None))
            elif type == '2':
                footer.append(pack_srec('8',
                                        self.execution_start_address,
                                        0,
                                        None))
            elif type == '3':
                footer.append(pack_srec('7',
                                        self.execution_start_address,
                                        0,
                                        None))
        return '\n'.join(header + data + footer) + '\n'

    def as_ihex(self, size=32, address_length=32):
        '''
        Return string of Intel HEX records of all data.
        '''
        data_address = []
        extended_address = -1
        for address, data in self.segments.iter(size):
            if address_length == 32:
                if ((address >> 16) & 0xffff) > extended_address:
                    extended_address = ((address >> 16) & 0xffff)
                    packed = pack_ihex(4,
                                       0,
                                       2,
                                       binascii.unhexlify('%04X'
                                                          % extended_address))
                    data_address.append(packed)
            else:
                raise ValueError('unsupported address length %d'
                                 % address_length)
            data_address.append(pack_ihex(0, address, len(data), data))
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

    def as_binary(self, begin=None, padding=b'\xff'):
        '''
        Return a bytearray of all data.
        '''
        res = bytearray()
        end = self.get_minimum_address()
        if begin is not None:
            if begin > end:
                fmt = 'begin({}) cannot be greater than end({})'
                raise ValueError(fmt.format(begin, end))
            end = begin
        for address, data in self.segments.iter():
            res.extend(bytearray(padding * (address - end)))
            res.extend(data)
            end = address + len(data)
        return res

    def exclude(self, begin, end):
        '''
        Exclude range including `begin`, not including `end`.
        '''
        self.segments.remove(_Segment(begin, end, None))

    def set_execution_start_address(self, address):
        '''
        Set execution start address to `address`.
        '''
        self.execution_start_address = address

    def get_execution_start_address(self):
        '''
        Get execution start address.
        '''
        return self.execution_start_address

    def get_minimum_address(self):
        '''
        Get minimum address.
        '''
        return self.segments.get_minimum_address()

    def get_maximum_address(self):
        '''
        Get maximum address.
        '''
        return self.segments.get_maximum_address()

    def info(self, type, filename):
        '''
        Return string of human readable binary information.
        '''
        if type == 'srec':
            file_format = 'motorola s-record'
        elif type == 'ihex':
            file_format = 'intel hex'
        elif type == 'binary':
            file_format = 'binary'
        else:
            raise ValueError('bad file format type %s' % type)
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
        for begin, end, data in self.iter_segments():
            info += '        0x%08x - 0x%08x\n' % (begin, end)
        return info

    def iter_segments(self):
        '''Iterate over data segments.
        '''
        for segment in self.segments.list:
            yield segment.begin, segment.end, segment.data

    def __iadd__(self, other):
        self.add_srec(io.StringIO(other.as_srec()))
        return self

    def __str__(self):
        return self.segments.__str__()


def main(args, stdout=sys.stdout, stderr=sys.stderr):
    class FileArgs(object):

        def __init__(self):
            self.type = 'srec'
            self.offset = None
            self.output = False
            self.filename = None
            self.address_length = 32
            self.exclude = None

    def parse_file_args(fargs, args, i):
        while ((i < len(args)) and
               args[i].startswith('--') and
               not (args[i] == '--output') and
               not (args[i] == '--stdin')):
            if args[i] == '--ihex':
                fargs.type = 'ihex'
            elif args[i] == '--binary':
                fargs.type = 'binary'
            elif args[i] == '--offset':
                fargs.offset = int(args[i+1])
                i += 1
            elif args[i] == '--address-length':
                fargs.address_length = int(args[i+1])
                i += 1
            elif args[i] == '--exclude':
                begin = int(args[i+1], 0)
                end = int(args[i+2], 0)
                fargs.exclude = (begin, end)
                i += 2
            i += 1
        return i

    def help():
        stdout.write('USAGE\n')
        stdout.write('\n')
        stdout.write('    bincopy.py { cat, info, --help } ...\n')
        stdout.write('               ( { <file>, --stdin } [ --ihex | --binary ] [ --offset <n> ] ...\n')
        stdout.write('                 [ --exclude <begin> <end> ] )+ ...\n')
        stdout.write('               [ --output [ <file> ] [ --ihex | --binary ] [ --offset <n> ] ...\n')
        stdout.write('                 [ --exclude <begin> <end> ] [ --address-length <bits> ] ]\n')
        stdout.write('\n')
        stdout.write('DESCRIPTION\n')
        stdout.write('\n')
        stdout.write('    Mangling of various file formats that conveys binary information (Motorola S-Record,\n')
        stdout.write('    Intel HEX and binary files).\n')
        stdout.write('\n')
        stdout.write('EXAMPLES\n')
        stdout.write('\n')
        stdout.write('    help:\n')
        stdout.write('        $ bincopy.py --help\n')
        stdout.write('\n')
        stdout.write('    cat:\n')
        stdout.write('        $ bincopy.py cat foo.s19 bar.s19\n')
        stdout.write('        $ bincopy.py cat foo.s19 bar.hex --ihex fie.bin --binary --offset 512\n')
        stdout.write('        $ bincopy.py cat foo.s19 bar.hex --ihex --output fie.s19\n')
        stdout.write('        $ bincopy.py cat foo.s19 --exclude 0 100 bar.hex --ihex --output fie.hex --ihex\n')
        stdout.write('\n')
        stdout.write('    info:\n')
        stdout.write('        $ bincopy.py info foo.s19\n')
        stdout.write('\n')
        stdout.write('AUTHOR\n\n')
        stdout.write('    Erik Moqvist\n')

    def parse_args(args):
        i = 0
        file_args_list = []
        while i < len(args):
            file_args = FileArgs()
            if args[i] == '--output':
                file_args.output = True
                i += 1
                if (i < len(args)) and not args[i].startswith('--'):
                    file_args.filename = args[i]
                    i += 1
            elif args[i] == '--stdin':
                i += 1
            else:
                file_args.filename = args[i]
                i += 1
            i = parse_file_args(file_args, args, i)
            file_args_list.append(file_args)
        return file_args_list

    def cmd_cat(args):
        file_args_list = parse_args(args)
        file_all = File()
        outputted = False
        for file_args in file_args_list:
            f = File()
            if not file_args.output:
                if file_args.filename:
                    if file_args.type == 'srec':
                        with open(file_args.filename, 'r') as fin:
                            f.add_srec(fin)
                    elif file_args.type == 'ihex':
                        with open(file_args.filename, 'r') as fin:
                            f.add_ihex(fin)
                    elif file_args.type == 'binary':
                        with open(file_args.filename, 'rb') as fin:
                            f.add_binary(fin, (file_args.offset
                                               if file_args.offset else 0))
                else:
                    if file_args.type == 'srec':
                        f.add_srec(sys.stdin)
                    elif file_args.type == 'ihex':
                        f.add_ihex(sys.stdin)
                    elif file_args.type == 'binary':
                        f.add_binary(sys.stdin, (file_args.offset
                                                 if file_args.offset else 0))
                if file_args.exclude:
                    f.exclude(file_args.exclude[0], file_args.exclude[1])
                file_all += f
            else:
                outputted = True
                if file_args.exclude:
                    file_all.exclude(file_args.exclude[0],
                                     file_args.exclude[1])
                if file_args.filename:
                    if file_args.type == 'srec':
                        data = file_all.as_srec(address_length=file_args.address_length)
                        with open(file_args.filename, 'w') as fout:
                            fout.write(data)
                    elif file_args.type == 'ihex':
                        data = file_all.as_ihex()
                        with open(file_args.filename, 'w') as fout:
                            fout.write(data)
                    elif file_args.type == 'binary':
                        data = file_all.as_binary(file_args.offset
                                                  if file_args.offset else 0)
                        with open(file_args.filename, 'wb') as fout:
                            fout.write(data)
                else:
                    if file_args.type == 'srec':
                        stdout.write(file_all.as_srec(address_length=file_args.address_length))
                    elif file_args.type == 'ihex':
                        stdout.write(file_all.as_ihex())
                    elif file_args.type == 'binary':
                        stdout.write(file_all.as_binary(file_args.offset
                                                        if file_args.offset
                                                        else 0))
        if not outputted:
            stdout.write(file_all.as_srec())

    def cmd_info(args):
        file_args_list = parse_args(args)
        info_list = []
        for file_args in file_args_list:
            f = File()
            if file_args.output:
                raise ValueError('bad option --output')
            if file_args.filename:
                if file_args.type == 'srec':
                    with open(file_args.filename, 'r') as fin:
                        f.add_srec(fin)
                elif file_args.type == 'ihex':
                    with open(file_args.filename, 'r') as fin:
                        f.add_ihex(fin)
                elif file_args.type == 'binary':
                    with open(file_args.filename, 'rb') as fin:
                        f.add_binary(fin, (file_args.offset
                                           if file_args.offset else 0))
            else:
                if file_args.type == 'srec':
                    f.add_srec(sys.stdin)
                elif file_args.type == 'ihex':
                    f.add_ihex(sys.stdin)
                elif file_args.type == 'binary':
                    f.add_binary(sys.stdin, (file_args.offset
                                             if file_args.offset else 0))
            if file_args.exclude:
                f.exclude(file_args.exclude[0], file_args.exclude[1])
            info_list.append(f.info(file_args.type, file_args.filename))
        stdout.write('\n'.join(info_list))

    if (len(args) == 0) or (args[0] in ['--help', 'help']):
        help()
    elif args[0] == 'cat':
        cmd_cat(args[1:])
    elif args[0] == 'info':
        cmd_info(args[1:])
    else:
        stdout.write('error: bad argument %s\n' % args[0])
        sys.exit(1)


def entry():
    main(sys.argv[1:])


# See help() function for details or type 'python bincopy.py --help'
# on the command line
if __name__ == '__main__':
    entry()
