from __future__ import print_function

import sys
import unittest
import shutil
import bincopy
from collections import namedtuple

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

try:
    from BytesIO import BytesIO
except ImportError:
    from io import BytesIO

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch


class BinCopyTest(unittest.TestCase):

    maxDiff = None

    def assert_files_equal(self, actual, expected):
        with open(actual, 'rb') as fin:
            actual = fin.read()

        # open(expected, 'wb').write(actual)

        with open(expected, 'rb') as fin:
            expected = fin.read()

        self.assertEqual(actual, expected)

    def test_srec(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        with open('tests/files/in.s19', 'r') as fin:
            self.assertEqual(binfile.as_srec(28, 16), fin.read())

        binfile = bincopy.BinFile()

        with open('tests/files/empty_main.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        # Add and overwrite the data.
        binfile = bincopy.BinFile()
        binfile.add_srec_file('tests/files/empty_main_rearranged.s19')
        binfile.add_srec_file('tests/files/empty_main_rearranged.s19',
                              overwrite=True)

        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        with self.assertRaises(bincopy.Error) as cm:
            binfile.add_srec_file('tests/files/bad_crc.s19')

        self.assertEqual(
            str(cm.exception),
            "expected crc '25' in record "
            "S2144002640000000002000000060000001800000022, but got '22'")

    def test_bad_srec(self):
        # Pack.
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.pack_srec('q', 0, 0, '')

        self.assertEqual(str(cm.exception),
                         "expected record type 0..3 or 5..9, but got 'q'")

        # Unpack too short record.
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_srec('')

        self.assertEqual(str(cm.exception), "record '' too short")

        # Unpack bad first character.
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_srec('T0000011')

        self.assertEqual(str(cm.exception),
                         "record 'T0000011' not starting with an 'S'")

        # Unpack bad type.
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_srec('S.0200FF')

        self.assertEqual(str(cm.exception),
                         "expected record type 0..3 or 5..9, but got '.'")

        # Unpack bad crc.
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_srec('S1020011')

        self.assertEqual(str(cm.exception),
                         "expected crc 'FD' in record S1020011, but got '11'")

    def test_ti_txt(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.s19.txt', 'r') as fin:
            binfile.add_ti_txt(fin.read())

        with open('tests/files/in.s19.txt', 'r') as fin:
            self.assertEqual(binfile.as_ti_txt(), fin.read())

        binfile = bincopy.BinFile()

        with open('tests/files/empty_main.s19.txt', 'r') as fin:
            binfile.add_ti_txt(fin.read())

        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        # Add and overwrite the data.
        binfile = bincopy.BinFile()
        binfile.add_ti_txt_file('tests/files/empty_main_rearranged.s19.txt')
        binfile.add_ti_txt_file('tests/files/empty_main_rearranged.s19.txt',
                              overwrite=True)

        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        empty = bincopy.BinFile()
        binfile = bincopy.BinFile('tests/files/empty.txt')
        self.assertEqual(binfile.as_ti_txt(), empty.as_ti_txt())

    def test_bad_ti_txt(self):
        datas = [
            ('bad_ti_txt_address_value.txt', 'bad section address'),
            ('bad_ti_txt_bad_q.txt',         'bad file terminator'),
            ('bad_ti_txt_data_value.txt',    'bad data'),
            ('bad_ti_txt_record_short.txt',  'missing section address'),
            ('bad_ti_txt_record_long.txt',   'bad line length'),
            ('bad_ti_txt_no_offset.txt',     'missing section address'),
            ('bad_ti_txt_no_q.txt',          'missing file terminator'),
            ('bad_ti_txt_blank_line.txt',    'bad line length')
        ]

        for filename, message in datas:
            binfile = bincopy.BinFile()

            with self.assertRaises(bincopy.Error) as cm:
                binfile.add_ti_txt_file('tests/files/' + filename)

            self.assertEqual(str(cm.exception), message)

    def test_compare_ti_txt(self):
        filenames = [
            'in.s19',
            'empty_main.s19',
            'convert.s19',
            'out.s19',
            'non_sorted_segments.s19',
            'non_sorted_segments_merged_and_sorted.s19',

            'in.hex',
            'empty_main.hex',
            'convert.hex',
            'out.hex'
        ]

        for file_1 in filenames:
            file_2 = file_1 + '.txt'

            try:
                bin1 = bincopy.BinFile('tests/files/' + file_1)
                bin2 = bincopy.BinFile('tests/files/' + file_2)

                self.assertEqual(bin1.as_ti_txt(), bin2.as_ti_txt())
            except bincopy.Error as exc:
                print("Error comparing {} to {}: {}".format(file_1, file_2, str(exc)))
                raise exc

    def test_bad_ihex(self):
        # Unpack.
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_ihex('')

        self.assertEqual(str(cm.exception), "record '' too short")

        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_ihex('.0011110022')

        self.assertEqual(str(cm.exception),
                         "record '.0011110022' not starting with a ':'")

        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_ihex(':0011110022')

        self.assertEqual(str(cm.exception),
                         "expected crc 'DE' in record :0011110022, but got '22'")

    def test_ihex(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.hex', 'r') as fin:
            binfile.add_ihex(fin.read())

        with open('tests/files/in.hex', 'r') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

        # Add and overwrite the data.
        binfile = bincopy.BinFile()
        binfile.add_ihex_file('tests/files/in.hex')
        binfile.add_ihex_file('tests/files/in.hex', overwrite=True)

        with open('tests/files/in.hex') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

    def test_i8hex(self):
        """I8HEX files use only record types 00 and 01 (16 bit addresses).

        """

        binfile = bincopy.BinFile()

        binfile.add_ihex(':0100000001FE\n'
                         ':0101000002FC\n'
                         ':01FFFF0003FE\n'
                         ':0400000300000000F9\n' # Will not be part of
                                                 # I8HEX output.
                         ':00000001FF\n')

        self.assertEqual(list(binfile.segments),
                         [
                             (0, b'\x01'),
                             (0x100, b'\x02'),
                             (0xffff, b'\x03')
                         ])

        self.assertEqual(binfile.as_ihex(address_length_bits=16),
                         ':0100000001FE\n'
                         ':0101000002FC\n'
                         ':01FFFF0003FE\n'
                         ':00000001FF\n')

    def test_i8hex_address_above_64k(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(b'\x00', 65536)

        with self.assertRaises(bincopy.Error) as cm:
            binfile.as_ihex(address_length_bits=16)

        self.assertEqual(
            str(cm.exception),
            'cannot address more than 64 kB in I8HEX files (16 bits '
            'addresses)')

    def test_i16hex(self):
        """I16HEX files use only record types 00 through 03 (20 bit
        addresses).

        """

        binfile = bincopy.BinFile()

        binfile.add_ihex(':0100000001FE\n'
                         ':01F00000020D\n'
                         ':01FFFF0003FE\n'
                         ':02000002C0003C\n'
                         ':0110000005EA\n'
                         ':02000002FFFFFE\n'
                         ':0100000006F9\n'
                         ':01FFFF0007FA\n'
                         ':020000021000EC\n'
                         ':0100000004FB\n'
                         ':0400000500000000F7\n' # Converted to 03 in
                                                 # I16HEX output.
                         ':00000001FF\n')

        self.assertEqual(
            list(binfile.segments),
            [
                (0, b'\x01'),
                (0xf000, b'\x02'),
                (0xffff, b'\x03\x04'), # 3 at 0xffff and 4 at 16 *
                                       # 0x1000 = 0x10000.
                (16 * 0xc000 + 0x1000, b'\x05'),
                (16 * 0xffff, b'\x06'),
                (17 * 0xffff, b'\x07')
            ])

        self.assertEqual(binfile.as_ihex(address_length_bits=24),
                         ':0100000001FE\n'
                         ':01F00000020D\n'
                         ':02FFFF000304F9\n'
                         ':02000002C0003C\n'
                         ':0110000005EA\n'
                         ':02000002F0000C\n'
                         ':01FFF000060A\n'
                         ':02000002FFFFFE\n'
                         ':01FFFF0007FA\n'
                         ':0400000300000000F9\n'
                         ':00000001FF\n')

    def test_i16hex_address_above_1meg(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(b'\x00', 17 * 65535 + 1)

        with self.assertRaises(bincopy.Error) as cm:
            binfile.as_ihex(address_length_bits=24)

        self.assertEqual(
            str(cm.exception),
            'cannot address more than 1 MB in I16HEX files (20 bits '
            'addresses)')

    def test_i32hex(self):
        """I32HEX files use only record types 00, 01, 04, and 05 (32 bit
         addresses).

        """

        binfile = bincopy.BinFile()

        binfile.add_ihex(':0100000001FE\n'
                         ':01FFFF0002FF\n'
                         ':02000004FFFFFC\n'
                         ':0100000004FB\n'
                         ':01FFFF0005FC\n'
                         ':020000040001F9\n'
                         ':0100000003FC\n'
                         ':0400000500000000F7\n'
                         ':00000001FF\n')

        self.assertEqual(binfile.as_ihex(),
                         ':0100000001FE\n'
                         ':02FFFF000203FB\n'
                         ':02000004FFFFFC\n'
                         ':0100000004FB\n'
                         ':01FFFF0005FC\n'
                         ':0400000500000000F7\n'
                         ':00000001FF\n')
        self.assertEqual(binfile.minimum_address, 0)
        self.assertEqual(binfile.maximum_address, 0x100000000)
        self.assertEqual(binfile.execution_start_address, 0)
        self.assertEqual(binfile[0], 1)
        self.assertEqual(binfile[0xffff], 2)
        self.assertEqual(binfile[0x10000], 3)
        self.assertEqual(binfile[0xffff0000], 4)
        self.assertEqual(binfile[0xffff0002:0xffff0004], b'\xff\xff')
        self.assertEqual(binfile[0xffffffff:0x100000000], b'\x05')

    def test_i32hex_address_above_4gig(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(b'\x00', 0x100000000)

        with self.assertRaises(bincopy.Error) as cm:
            binfile.as_ihex(address_length_bits=32)

        self.assertEqual(
            str(cm.exception),
            'cannot address more than 4 GB in I32HEX files (32 bits '
            'addresses)')

    def test_binary(self):
        # Add data to 0..2.
        binfile = bincopy.BinFile()

        with open('tests/files/binary1.bin', 'rb') as fin:
            binfile.add_binary(fin.read())

        with open('tests/files/binary1.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(), fin.read())

        # Add and overwrite data to 15..179.
        binfile = bincopy.BinFile()
        binfile.add_binary_file('tests/files/binary2.bin', 15)
        binfile.add_binary_file('tests/files/binary2.bin', 15, overwrite=True)

        with self.assertRaises(bincopy.Error):
            # Cannot add overlapping segments.
            with open('tests/files/binary2.bin', 'rb') as fin:
                binfile.add_binary(fin.read(), 20)

        # Exclude the overlapping part and add.
        binfile.exclude(20, 1024)

        with open('tests/files/binary2.bin', 'rb') as fin:
            binfile.add_binary(fin.read(), 20)

        with open('tests/files/binary3.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(minimum_address=0,
                                               padding=b'\x00'), fin.read())

        # Exclude first byte and read it to test adjecent add before.
        binfile.exclude(0, 1)
        binfile.add_binary(b'1')

        with open('tests/files/binary3.bin', 'rb') as fin:
            reference = b'1' + fin.read()[1:]
            self.assertEqual(binfile.as_binary(minimum_address=0,
                                               padding=b'\x00'), reference)

        # Basic checks.
        self.assertEqual(binfile.minimum_address, 0)
        self.assertEqual(binfile.maximum_address, 184)
        self.assertEqual(len(binfile), 170)

        # Dump with start address beyond end of binary.
        self.assertEqual(binfile.as_binary(minimum_address=512), b'')

        # Dump with start address at maximum address.
        self.assertEqual(binfile.as_binary(minimum_address=184), b'')

        # Dump with start address one before maximum address.
        self.assertEqual(binfile.as_binary(minimum_address=183), b'\n')

        # Dump with start address one after minimum address.
        self.assertEqual(binfile.as_binary(minimum_address=1,
                                           padding=b'\x00'),
                         reference[1:])

        # Dump with start address 16 and end address 18.
        self.assertEqual(binfile.as_binary(minimum_address=16,
                                           maximum_address=18), b'\x32\x30')

        # Dump with start and end addresses 16.
        self.assertEqual(binfile.as_binary(minimum_address=16,
                                           maximum_address=16), b'')

        # Dump with end beyond end of binary.
        self.assertEqual(binfile.as_binary(maximum_address=1024,
                                           padding=b'\x00'),
                         reference)

        # Dump with end before start.
        self.assertEqual(binfile.as_binary(minimum_address=2,
                                           maximum_address=0), b'')

    def test_binary_16(self):
        binfile = bincopy.BinFile(word_size_bits=16)
        binfile.add_binary(b'\x35\x30\x36\x30\x37\x30', address=5)
        binfile.add_binary(b'\x61\x30\x62\x30\x63\x30', address=10)

        # Basic checks.
        self.assertEqual(binfile.minimum_address, 5)
        self.assertEqual(binfile.maximum_address, 13)
        self.assertEqual(len(binfile), 6)

        # Dump with start address beyond end of binary.
        self.assertEqual(binfile.as_binary(minimum_address=14), b'')

        # Dump with start address at maximum address.
        self.assertEqual(binfile.as_binary(minimum_address=13), b'')

        # Dump with start address one before maximum address.
        self.assertEqual(binfile.as_binary(minimum_address=12), b'c0')

        # Dump parts of both segments.
        self.assertEqual(binfile.as_binary(minimum_address=6,
                                           maximum_address=11),
                         b'\x36\x30\x37\x30\xff\xff\xff\xff\x61\x30')

        # Iterate over segments.
        self.assertEqual(list(binfile.segments),
                         [
                             (5, b'\x35\x30\x36\x30\x37\x30'),
                             (10, b'\x61\x30\x62\x30\x63\x30')
                         ])

        # Chunks of segments.
        self.assertEqual(list(binfile.segments.chunks(size=2)),
                         [
                             (5, b'\x35\x30\x36\x30'),
                             (7, b'\x37\x30'),
                             (10, b'\x61\x30\x62\x30'),
                             (12, b'\x63\x30')
                         ])

        # Hexdump output.
        self.assertEqual(
            binfile.as_hexdump(),
            '00000000                                 35 30 36 30 37 30  '
            '|          506070|\n'
            '00000008              61 30 62 30  63 30                    '
            '|    a0b0c0      |\n')

    def test_add(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.s19', 'r') as fin:
            binfile.add(fin.read())

        with open('tests/files/in.s19') as fin:
            self.assertEqual(binfile.as_srec(28, 16), fin.read())

        binfile = bincopy.BinFile()

        with open('tests/files/in.hex', 'r') as fin:
            binfile.add(fin.read())

        with open('tests/files/in.hex') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

        binfile = bincopy.BinFile()

        with self.assertRaises(bincopy.UnsupportedFileFormatError) as cm:
            binfile.add('invalid data')

        binfile = bincopy.BinFile()

        with self.assertRaises(bincopy.Error) as cm:
            binfile.add('S214400420ED044000E8B7FFFFFFF4660F1F440000EE\n'
                        'invalid data')

        self.assertEqual(str(cm.exception),
                         "record 'invalid data' not starting with an 'S'")

        binfile = bincopy.BinFile()

        with self.assertRaises(bincopy.Error) as cm:
            binfile.add(':020000040040BA\n'
                        'invalid data')

        self.assertEqual(str(cm.exception),
                         "record 'invalid data' not starting with a ':'")

        with self.assertRaises(bincopy.UnsupportedFileFormatError) as cm:
            binfile.add('junk')

    def test_add_file(self):
        binfile = bincopy.BinFile()
        binfile.add_file('tests/files/empty_main_rearranged.s19')

        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        binfile = bincopy.BinFile()
        binfile.add_file('tests/files/in.hex')

        with open('tests/files/in.hex') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

        binfile = bincopy.BinFile()

        with self.assertRaises(bincopy.UnsupportedFileFormatError) as cm:
            binfile.add_file('tests/files/hexdump.txt')

    def test_init_files(self):
        binfile = bincopy.BinFile('tests/files/empty_main_rearranged.s19')

        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        binfile = bincopy.BinFile(['tests/files/in.hex', 'tests/files/in.hex'],
                                  overwrite=True)

        with open('tests/files/in.hex') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

        with self.assertRaises(bincopy.UnsupportedFileFormatError) as cm:
            binfile = bincopy.BinFile('tests/files/hexdump.txt')

    def test_array(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.hex', 'r') as fin:
            binfile.add_ihex(fin.read())

        with open('tests/files/in.i') as fin:
            self.assertEqual(binfile.as_array() + '\n', fin.read())

    def test_hexdump_1(self):
        binfile = bincopy.BinFile()
        binfile.add_binary(b'12',address=17)
        binfile.add_binary(b'34', address=26)
        binfile.add_binary(b'5678', address=30)
        binfile.add_binary(b'9', address=47)

        with open('tests/files/hexdump.txt') as fin:
            self.assertEqual(binfile.as_hexdump(), fin.read())

    def test_hexdump_2(self):
        binfile = bincopy.BinFile()
        binfile.add_binary(b'34', address=0x150)
        binfile.add_binary(b'3', address=0x163)
        binfile.add_binary(b'\x01', address=0x260)
        binfile.add_binary(b'3', address=0x263)

        with open('tests/files/hexdump2.txt') as fin:
            self.assertEqual(binfile.as_hexdump(), fin.read())

    def test_hexdump_gaps(self):
        binfile = bincopy.BinFile()
        binfile.add_binary(b'1', address=0)
        # One line gap as "...".
        binfile.add_binary(b'3', address=32)
        # Two lines gap as "...".
        binfile.add_binary(b'6', address=80)

        with open('tests/files/hexdump3.txt') as fin:
            self.assertEqual(binfile.as_hexdump(), fin.read())

    def test_hexdump_empty(self):
        binfile = bincopy.BinFile()

        self.assertEqual(binfile.as_hexdump(), '\n')

    def test_srec_ihex_binary(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.hex', 'r') as fin:
            binfile.add_ihex(fin.read())

        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        with open('tests/files/binary1.bin', 'rb') as fin:
            binfile.add_binary(fin.read(), 1024)

        with open('tests/files/out.hex', 'r') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

        with open('tests/files/out.s19') as fin:
            self.assertEqual(binfile.as_srec(address_length_bits=16), fin.read())

        binfile.fill(b'\x00')

        with open('tests/files/out.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(), fin.read())

    def test_exclude_crop(self):
        # Exclude part of the data.
        binfile = bincopy.BinFile()

        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        binfile.exclude(2, 4)

        with open('tests/files/in_exclude_2_4.s19') as fin:
            self.assertEqual(binfile.as_srec(32, 16), fin.read())

        binfile = bincopy.BinFile()

        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        binfile.exclude(3, 1024)

        with open('tests/files/in_exclude_3_1024.s19') as fin:
            self.assertEqual(binfile.as_srec(32, 16), fin.read())

        binfile = bincopy.BinFile()

        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        binfile.exclude(0, 9)

        with open('tests/files/in_exclude_0_9.s19') as fin:
            self.assertEqual(binfile.as_srec(32, 16), fin.read())

        binfile = bincopy.BinFile()

        with open('tests/files/empty_main.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        binfile.exclude(0x400240, 0x400600)

        with open('tests/files/empty_main_mod.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        # Crop part of the data.
        binfile = bincopy.BinFile()
        binfile.add_srec_file('tests/files/in.s19')
        binfile.crop(2, 4)

        with open('tests/files/in_crop_2_4.s19') as fin:
            self.assertEqual(binfile.as_srec(32, 16), fin.read())

        binfile.exclude(2, 4)
        self.assertEqual(binfile.as_binary(), b'')

        # Exclude various parts of segments.
        binfile = bincopy.BinFile()
        binfile.add_binary(b'111111', address=8)
        binfile.add_binary(b'222222', address=16)
        binfile.add_binary(b'333333', address=24)

        binfile.exclude(7, 8)
        binfile.exclude(15, 16)
        binfile.exclude(23, 24)
        self.assertEqual(binfile.as_binary(),
                         b'111111' +
                         2 * b'\xff' +
                         b'222222' +
                         2 * b'\xff' +
                         b'333333')
        self.assertEqual(len(binfile.segments), 3)

        binfile.exclude(20, 24)
        self.assertEqual(binfile.as_binary(),
                         b'111111' +
                         2 * b'\xff' +
                         b'2222' +
                         4 * b'\xff' +
                         b'333333')
        self.assertEqual(len(binfile.segments), 3)

        binfile.exclude(12, 24)
        self.assertEqual(binfile.as_binary(),
                         b'1111' +
                         12 * b'\xff' +
                         b'333333')
        self.assertEqual(len(binfile.segments), 2)

        binfile.exclude(11, 25)
        self.assertEqual(binfile.as_binary(),
                         b'111' +
                         14 * b'\xff' +
                         b'33333')
        self.assertEqual(len(binfile.segments), 2)

        binfile.exclude(11, 26)
        self.assertEqual(binfile.as_binary(),
                         b'111' +
                         15 * b'\xff' +
                         b'3333')
        self.assertEqual(len(binfile.segments), 2)

        binfile.exclude(27, 29)
        self.assertEqual(binfile.as_binary(),
                         b'111' +
                         15 * b'\xff' +
                         b'3' + 2 * b'\xff' + b'3')
        self.assertEqual(len(binfile.segments), 3)

        # Exclude negative address range and expty address range.
        binfile = bincopy.BinFile()
        binfile.add_binary(b'111111')

        with self.assertRaises(bincopy.Error) as cm:
            binfile.exclude(4, 2)

        self.assertEqual(str(cm.exception), 'bad address range')
        binfile.exclude(2, 2)
        self.assertEqual(binfile.as_binary(), b'111111')

    def test_minimum_maximum_length(self):
        binfile = bincopy.BinFile()

        # Get the minimum address from an empty file.
        self.assertEqual(binfile.minimum_address, None)

        # Get the maximum address from an empty file.
        self.assertEqual(binfile.maximum_address, None)

        # Get the length of an empty file.
        self.assertEqual(len(binfile), 0)

        # Get from a small file.
        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        self.assertEqual(binfile.minimum_address, 0)
        self.assertEqual(binfile.maximum_address, 70)
        self.assertEqual(len(binfile), 70)

        # Add a second segment to the file.
        binfile.add_binary(9 * b'\x01', 80)

        self.assertEqual(binfile.minimum_address, 0)
        self.assertEqual(binfile.maximum_address, 89)
        self.assertEqual(len(binfile), 79)

    def test_iterate_segments(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        i = 0

        for address, data in binfile.segments:
            del address, data
            i += 1

        self.assertEqual(i, 1)
        self.assertEqual(len(binfile.segments), 1)

    def test_segments_list(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(b'\x00', address=0)
        binfile.add_binary(b'\x01\x02', address=10)
        binfile.add_binary(b'\x03', address=12)
        binfile.add_binary(b'\x04', address=1000)

        self.assertEqual(list(binfile.segments),
                         [
                             (0, b'\x00'),
                             (10, b'\x01\x02\x03'),
                             (1000, b'\x04')
                         ])

    def test_chunks_list(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(b'\x00\x00\x01\x01\x02', address=0)
        binfile.add_binary(b'\x04\x05\x05\x06\x06\x07', address=9)
        binfile.add_binary(b'\x09', address=19)
        binfile.add_binary(b'\x0a', address=21)

        self.assertEqual(binfile.as_binary(),
                         b'\x00\x00\x01\x01\x02\xff\xff\xff'
                         b'\xff\x04\x05\x05\x06\x06\x07\xff'
                         b'\xff\xff\xff\x09\xff\x0a')

        # Size 8, alignment 1.
        self.assertEqual(list(binfile.segments.chunks(size=8)),
                         [
                             (0, b'\x00\x00\x01\x01\x02'),
                             (9, b'\x04\x05\x05\x06\x06\x07'),
                             (19, b'\x09'),
                             (21, b'\x0a')
                         ])

        # Size 8, alignment 2.
        self.assertEqual(list(binfile.segments.chunks(size=8, alignment=2)),
                         [
                             (0, b'\x00\x00\x01\x01\x02'),
                             (9, b'\x04'),
                             (10, b'\x05\x05\x06\x06\x07'),
                             (19, b'\x09'),
                             (21, b'\x0a')
                         ])

        # Size 8, alignment 4.
        self.assertEqual(list(binfile.segments.chunks(size=8, alignment=4)),
                         [
                             (0, b'\x00\x00\x01\x01\x02'),
                             (9, b'\x04\x05\x05'),
                             (12, b'\x06\x06\x07'),
                             (19, b'\x09'),
                             (21, b'\x0a')
                         ])

        # Size 8, alignment 8.
        self.assertEqual(list(binfile.segments.chunks(size=8, alignment=8)),
                         [
                             (0, b'\x00\x00\x01\x01\x02'),
                             (9, b'\x04\x05\x05\x06\x06\x07'),
                             (19, b'\x09'),
                             (21, b'\x0a')
                         ])

        # Size 4, alignment 1.
        self.assertEqual(list(binfile.segments.chunks(size=4)),
                         [
                             (0, b'\x00\x00\x01\x01'),
                             (4, b'\x02'),
                             (9, b'\x04\x05\x05\x06'),
                             (13, b'\x06\x07'),
                             (19, b'\x09'),
                             (21, b'\x0a')
                         ])

        # Size 4, alignment 2.
        self.assertEqual(list(binfile.segments.chunks(size=4, alignment=2)),
                         [
                             (0, b'\x00\x00\x01\x01'),
                             (4, b'\x02'),
                             (9, b'\x04'),
                             (10, b'\x05\x05\x06\x06'),
                             (14, b'\x07'),
                             (19, b'\x09'),
                             (21, b'\x0a')
                         ])

        # Size 4, alignment 4.
        self.assertEqual(list(binfile.segments.chunks(size=4, alignment=4)),
                         [
                             (0, b'\x00\x00\x01\x01'),
                             (4, b'\x02'),
                             (9, b'\x04\x05\x05'),
                             (12, b'\x06\x06\x07'),
                             (19, b'\x09'),
                             (21, b'\x0a')
                         ])

    def test_chunks_bad_arguments(self):
        binfile = bincopy.BinFile()

        with self.assertRaises(bincopy.Error) as cm:
            list(binfile.segments.chunks(size=4, alignment=3))

        self.assertEqual(str(cm.exception),
                         'size 4 is not a multiple of alignment 3')

        with self.assertRaises(bincopy.Error) as cm:
            list(binfile.segments.chunks(size=4, alignment=8))

        self.assertEqual(str(cm.exception),
                         'size 4 is not a multiple of alignment 8')

    def test_segment(self):
        binfile = bincopy.BinFile()
        binfile.add_binary(b'\x00\x01\x02\x03\x04', 2)

        # Size 4, alignment 4.
        self.assertEqual(list(binfile.segments[0].chunks(size=4, alignment=4)),
                         [
                             (2, b'\x00\x01'),
                             (4, b'\x02\x03\x04')
                         ])

        # Bad arguments.
        with self.assertRaises(bincopy.Error) as cm:
            list(binfile.segments[0].chunks(size=4, alignment=8))

        self.assertEqual(str(cm.exception),
                         'size 4 is not a multiple of alignment 8')

        # Missing segment.
        with self.assertRaises(bincopy.Error) as cm:
            list(binfile.segments[1].chunks(size=4, alignment=8))

        self.assertEqual(str(cm.exception), 'segment does not exist')

    def test_add_files(self):
        binfile = bincopy.BinFile()
        binfile_1_2 = bincopy.BinFile()
        binfile.add_binary(b'\x00')
        binfile_1_2.add_binary(b'\x01', address=1)
        binfile += binfile_1_2
        self.assertEqual(binfile.as_binary(), b'\x00\x01')

    def test_info(self):
        binfile = bincopy.BinFile()

        with open('tests/files/empty_main.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        self.assertEqual(binfile.info(),
                         """Header:                  "bincopy/empty_main.s19"
Execution start address: 0x00400400
Data ranges:

    0x00400238 - 0x004002b4 (124 bytes)
    0x004002b8 - 0x0040033e (134 bytes)
    0x00400340 - 0x004003c2 (130 bytes)
    0x004003d0 - 0x00400572 (418 bytes)
    0x00400574 - 0x0040057d (9 bytes)
    0x00400580 - 0x004006ac (300 bytes)
    0x00600e10 - 0x00601038 (552 bytes)
""")

    def test_layout_empty_main(self):
        binfile = bincopy.BinFile('tests/files/empty_main.s19')

        self.assertEqual(
            binfile.layout(),
            "0x400238                                                           "
            "     0x601038\n"
            "-                                                                  "
            "            -\n")

    def test_layout_out(self):
        binfile = bincopy.BinFile('tests/files/out.hex')

        self.assertEqual(
            binfile.layout(),
            "0x0                                                                "
            "        0x403\n"
            "=====-               -====-                                        "
            "            -\n")

    def test_layout_in_exclude_2_4(self):
        binfile = bincopy.BinFile('tests/files/in_exclude_2_4.s19')

        self.assertEqual(
            binfile.layout(),
            "0x0                                                               "
            "0x46\n"
            "==  =============================================================="
            "====\n")

    def test_execution_start_address(self):
        binfile = bincopy.BinFile()

        with open('tests/files/empty_main.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        self.assertEqual(binfile.execution_start_address, 0x00400400)

        binfile.execution_start_address = 0x00400401
        self.assertEqual(binfile.execution_start_address, 0x00400401)

    def test_ihex_crc(self):
        self.assertEqual(bincopy.crc_ihex('0300300002337a'), 0x1e)
        self.assertEqual(bincopy.crc_ihex('00000000'), 0)

    def test_add_ihex_record_type_3(self):
        binfile = bincopy.BinFile()
        binfile.add_ihex(':0400000302030405EB')
        self.assertEqual(binfile.execution_start_address, 0x02030405)

    def test_add_ihex_record_type_5(self):
        binfile = bincopy.BinFile()
        binfile.add_ihex(':0400000501020304ED')
        self.assertEqual(binfile.execution_start_address, 0x01020304)

    def test_add_ihex_bad_record_type_6(self):
        binfile = bincopy.BinFile()

        with self.assertRaises(bincopy.Error) as cm:
            binfile.add_ihex(':00000006FA')

        self.assertEqual(str(cm.exception),
                         'expected type 1..5 in record :00000006FA, but got 6')

    def test_as_ihex_bad_address_length_bits(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(b'\x00')

        with self.assertRaises(bincopy.Error) as cm:
            binfile.as_ihex(address_length_bits=8)

        self.assertEqual(str(cm.exception),
                         'expected address length 16, 24 or 32, but got 8')

    def test_as_srec_bad_address_length(self):
        binfile = bincopy.BinFile()

        with self.assertRaises(bincopy.Error) as cm:
            binfile.as_srec(address_length_bits=40)

        self.assertEqual(str(cm.exception),
                         'expected data record type 1..3, but got 4')

    def test_as_srec_record_5(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(65535 * b'\x00')
        records = binfile.as_srec(number_of_data_bytes=1)

        self.assertEqual(len(records.splitlines()), 65536)
        self.assertIn('S503FFFFFE', records)

    def test_as_srec_record_6(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(65536 * b'\x00')

        records = binfile.as_srec(number_of_data_bytes=1)

        self.assertEqual(len(records.splitlines()), 65537)
        self.assertIn('S604010000FA', records)

    def test_as_srec_record_8(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(b'\x00')
        binfile.execution_start_address = 0x123456
        records = binfile.as_srec(address_length_bits=24)

        self.assertEqual(records,
                         'S20500000000FA\n'
                         'S5030001FB\n'
                         'S8041234565F\n')

    def test_word_size(self):
        binfile = bincopy.BinFile(word_size_bits=16)

        with open('tests/files/in_16bits_word.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        with open('tests/files/out_16bits_word.s19') as fin:
            self.assertEqual(binfile.as_srec(30, 24), fin.read())

    def test_word_size_default_padding(self):
        binfile = bincopy.BinFile(word_size_bits=16)

        with open('tests/files/in_16bits_word_padding.hex', 'r') as fin:
            binfile.add_ihex(fin.read())

        with open('tests/files/out_16bits_word_padding.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(), fin.read())

    def test_word_size_custom_padding(self):
        binfile = bincopy.BinFile(word_size_bits=16)

        with open('tests/files/in_16bits_word_padding.hex', 'r') as fin:
            binfile.add_ihex(fin.read())

        with open('tests/files/out_16bits_word_padding_0xff00.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\xff\x00'), fin.read())

    def test_print(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        print(binfile)

    def test_issue_4_1(self):
        binfile = bincopy.BinFile()

        with open('tests/files/issue_4_in.hex', 'r') as fin:
            binfile.add_ihex(fin.read())

        with open('tests/files/issue_4_out.hex', 'r') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

    def test_issue_4_2(self):
        binfile = bincopy.BinFile()

        with open('tests/files/empty_main.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        with open('tests/files/empty_main.hex', 'r') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

    def test_overwrite(self):
        binfile = bincopy.BinFile()

        # Overwrite in empty file.
        binfile.add_binary(b'1234', address=512, overwrite=True)
        self.assertEqual(binfile.as_binary(minimum_address=512), b'1234')

        # Test setting data with multiple existing segments.
        binfile.add_binary(b'123456', address=1024)
        binfile.add_binary(b'99', address=1026, overwrite=True)
        self.assertEqual(binfile.as_binary(minimum_address=512),
                         b'1234' + 508 * b'\xff' + b'129956')

        # Test setting data crossing the original segment limits.
        binfile.add_binary(b'abc', address=1022, overwrite=True)
        binfile.add_binary(b'def', address=1029, overwrite=True)
        self.assertEqual(binfile.as_binary(minimum_address=512),
                                           b'1234'
                                           + 506 * b'\xff'
                                           + b'abc2995def')

        # Overwrite a segment and write outside it.
        binfile.add_binary(b'111111111111', address=1021, overwrite=True)
        self.assertEqual(binfile.as_binary(minimum_address=512),
                                           b'1234'
                                           + 505 * b'\xff'
                                           + b'111111111111')

        # Overwrite multiple segments (all segments in this test).
        binfile.add_binary(1024 * b'1', address=256, overwrite=True)
        self.assertEqual(binfile.as_binary(minimum_address=256), 1024 * b'1')

    def test_non_sorted_segments(self):
        binfile = bincopy.BinFile()

        with open('tests/files/non_sorted_segments.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        with open('tests/files/non_sorted_segments_merged_and_sorted.s19', 'r') as fin:
            self.assertEqual(binfile.as_srec(), fin.read())

    def test_fill(self):
        binfile = bincopy.BinFile()

        # Fill empty file.
        binfile.fill()
        self.assertEqual(binfile.as_binary(), b'')

        # Add some data and fill again.
        binfile.add_binary(b'\x01\x02\x03\x04', address=0)
        binfile.add_binary(b'\x01\x02\x03\x04', address=8)
        binfile.fill()
        self.assertEqual(binfile.as_binary(),
                         b'\x01\x02\x03\x04\xff\xff\xff\xff\x01\x02\x03\x04')

    def test_fill_max_words(self):
        binfile = bincopy.BinFile()
        binfile.add_binary(b'\x01', address=0)
        binfile.add_binary(b'\x02', address=2)
        binfile.add_binary(b'\x03', address=5)
        binfile.add_binary(b'\x04', address=9)
        binfile.fill(b'\xaa', max_words=2)
        self.assertEqual(len(binfile.segments), 2)
        self.assertEqual(binfile.segments[0].address, 0)
        self.assertEqual(binfile.segments[0].data, b'\x01\xaa\x02\xaa\xaa\x03')
        self.assertEqual(binfile.segments[1].address, 9)
        self.assertEqual(binfile.segments[1].data, b'\x04')

    def test_fill_word_size_16(self):
        binfile = bincopy.BinFile(word_size_bits=16)
        binfile.add_binary(b'\x01\x02', address=0)
        binfile.add_binary(b'\x03\x04', address=2)
        binfile.add_binary(b'\x05\x06', address=5)
        binfile.add_binary(b'\x07\x08', address=9)
        binfile.fill(b'\xaa\xaa', max_words=2)
        self.assertEqual(len(binfile.segments), 2)
        self.assertEqual(binfile.segments[0].address, 0)
        self.assertEqual(binfile.segments[0].data,
                         b'\x01\x02\xaa\xaa\x03\x04\xaa\xaa\xaa\xaa\x05\x06')
        self.assertEqual(binfile.segments[1].address, 9)
        self.assertEqual(binfile.segments[1].data,
                         b'\x07\x08')

        # Fill the rest with the default value.
        binfile.fill()
        self.assertEqual(len(binfile.segments), 1)
        self.assertEqual(
            binfile.as_binary(),
            (b'\x01\x02\xaa\xaa\x03\x04\xaa\xaa\xaa\xaa\x05\x06\xff\xff\xff\xff'
             b'\xff\xff\x07\x08'))

    def test_set_get_item(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(b'\x01\x02\x03\x04', address=1)

        self.assertEqual(binfile[:], b'\x01\x02\x03\x04')

        with self.assertRaises(IndexError):
            binfile[0]

        self.assertEqual(binfile[1], 1)
        self.assertEqual(binfile[2], 2)
        self.assertEqual(binfile[3], 3)
        self.assertEqual(binfile[4], 4)

        with self.assertRaises(IndexError):
            binfile[5]

        self.assertEqual(binfile[3:5], b'\x03\x04')
        self.assertEqual(binfile[3:6], b'\x03\x04')

        binfile[1:3] = b'\x05\x06'
        self.assertEqual(binfile[:], b'\x05\x06\x03\x04')

        binfile[3:] = b'\x07\x08\x09'
        self.assertEqual(binfile[:], b'\x05\x06\x07\x08\x09')

        binfile[3:5] = b'\x0a\x0b'
        self.assertEqual(binfile[:], b'\x05\x06\x0a\x0b\x09')

        binfile[2:] = b'\x0c'
        self.assertEqual(binfile[:], b'\x05\x0c\x0a\x0b\x09')

        binfile[:] = b'\x01\x02\x03\x04\x05'
        self.assertEqual(binfile[:], b'\x01\x02\x03\x04\x05')

        binfile[0] = 0
        self.assertEqual(binfile[:], b'\x00\x01\x02\x03\x04\x05')

        binfile[7] = 7
        self.assertEqual(binfile[:], b'\x00\x01\x02\x03\x04\x05\xff\x07')
        self.assertEqual(binfile[6], 255)
        self.assertEqual(binfile[6:7], b'\xff')
        self.assertEqual(binfile[6:8], b'\xff\x07')
        self.assertEqual(binfile[5:8], b'\x05\xff\x07')

        # Add data at high address to test get performance.
        binfile[0x10000000] = 0x12
        self.assertEqual(binfile[0x10000000 - 1:], b'\xff\x12')

    def test_set_get_item_16(self):
        binfile = bincopy.BinFile(word_size_bits=16)

        binfile.add_binary(b'\x01\x02\x03\x04', address=1)

        self.assertEqual(binfile[:], b'\x01\x02\x03\x04')

        with self.assertRaises(IndexError):
            binfile[0]

        self.assertEqual(binfile[1], 0x0102)
        self.assertEqual(binfile[2], 0x0304)

        with self.assertRaises(IndexError):
            binfile[3]

        self.assertEqual(binfile[1:3], b'\x01\x02\x03\x04')
        self.assertEqual(binfile[1:4], b'\x01\x02\x03\x04')

        binfile[1:2] = b'\x05\x06'
        self.assertEqual(binfile[:], b'\x05\x06\x03\x04')

        binfile[2:] = b'\x07\x08\x09\xa0'
        self.assertEqual(binfile[:], b'\x05\x06\x07\x08\x09\xa0')

        binfile[5] = 0x1718
        self.assertEqual(binfile[:], b'\x05\x06\x07\x08\t\xa0\xff\xff\x17\x18')
        self.assertEqual(binfile[4], 0xffff)
        self.assertEqual(binfile[4:5], b'\xff\xff')
        self.assertEqual(binfile[3:8], b'\t\xa0\xff\xff\x17\x18')

    def test_header_default_encoding(self):
        binfile = bincopy.BinFile()
        binfile.add_file('tests/files/empty_main.s19')

        self.assertEqual(binfile.header, 'bincopy/empty_main.s19')

        binfile.header = 'bincopy/empty_main.s20'
        self.assertEqual(binfile.header, 'bincopy/empty_main.s20')

    def test_header_no_encoding(self):
        binfile = bincopy.BinFile(header_encoding=None)
        binfile.add_file('tests/files/empty_main.s19')

        self.assertEqual(binfile.header, b'bincopy/empty_main.s19')

        binfile.header = b'bincopy/empty_main.s20'
        self.assertEqual(binfile.header, b'bincopy/empty_main.s20')

        binfile.header = b'\x01\x80\x88\xaa\x90'
        self.assertEqual(binfile.header, b'\x01\x80\x88\xaa\x90')

        with self.assertRaises(TypeError) as cm:
            binfile.header = u'bincopy/empty_main.s21'

        self.assertIn("expected a bytes object, but got <",
                      str(cm.exception))

    def test_srec_no_header_encoding(self):
        binfile = bincopy.BinFile(header_encoding=None)

        binfile.add_srec('S0080000018088AA90B4')

        self.assertEqual(binfile.as_srec().splitlines()[0],
                         'S0080000018088AA90B4')

    def test_performance(self):
        binfile = bincopy.BinFile()

        # Add a 1MB consecutive binary.
        chunk = 1024 * b'1'

        for i in range(1024):
            binfile.add_binary(chunk, 1024 * i)

        self.assertEqual(binfile.minimum_address, 0)
        self.assertEqual(binfile.maximum_address, 1024 * 1024)

        ihex = binfile.as_ihex()
        srec = binfile.as_srec()

        binfile = bincopy.BinFile()
        binfile.add_ihex(ihex)

        binfile = bincopy.BinFile()
        binfile.add_srec(srec)

    def test_command_line_convert_input_formats(self):
        with open('tests/files/convert.hexdump') as fin:
            expected_output = fin.read()

        datas = [
            ('srec', 'tests/files/convert.s19'),
            ('ihex', 'tests/files/convert.hex'),
            ('ti_txt', 'tests/files/convert.s19.txt'),
            ('binary,0x100', 'tests/files/convert.bin'),
            ('auto', 'tests/files/convert.s19'),
            ('auto', 'tests/files/convert.hex'),
            ('auto', 'tests/files/convert.s19.txt')
        ]

        for input_format, test_file in datas:
            try:
                command = ['bincopy', 'convert', '-i', input_format, test_file, '-']
                self._test_command_line_ok(command, expected_output)
            except SystemExit as exc:
                print("Failed converting {} as {}".format(test_file, input_format))
                raise exc

    def test_command_line_convert_elf(self):
        with open('tests/files/elf.hexdump') as fin:
            expected_output = fin.read()

        datas = [
            ('elf', 'tests/files/elf.out'),
            ('auto', 'tests/files/elf.out')
        ]

        for input_format, test_file in datas:
            try:
                command = ['bincopy', 'convert', '-i', input_format, test_file, '-']
                self._test_command_line_ok(command, expected_output)
            except SystemExit as exc:
                print("Failed converting {} as {}".format(test_file, input_format))
                raise exc

    def test_command_line_convert_output_formats(self):
        test_file = 'tests/files/convert.hex'
        binfile = bincopy.BinFile(test_file)

        datas = [
            ('srec', binfile.as_srec()),
            ('srec,8', binfile.as_srec(8)),
            ('srec,16,24', binfile.as_srec(16, 24)),
            ('ihex', binfile.as_ihex()),
            ('ihex,16', binfile.as_ihex(16)),
            ('ihex,8,32', binfile.as_ihex(8, 32)),
            ('hexdump', binfile.as_hexdump()),
            ('ti_txt', binfile.as_ti_txt())
        ]

        for output_format, expected_output in datas:
            command = ['bincopy', 'convert', '-o', output_format, test_file, '-']
            self._test_command_line_ok(command, expected_output)

    def test_command_line_convert_output_formats_bad_parameters(self):
        test_file = 'tests/files/convert.hex'

        datas = [
            ('srec,x', "invalid srec number of data bytes 'x'"),
            ('srec,16,y', "invalid srec address length of 'y' bits"),
            ('ihex,x', "invalid ihex number of data bytes 'x'"),
            ('ihex,8,y', "invalid ihex address length of 'y' bits")
        ]

        for output_format, message in datas:
            command = ['bincopy', 'convert', '-o', output_format, test_file, '-']
            stderr = StringIO()

            with patch('sys.stderr', stderr):
                with self.assertRaises(SystemExit):
                    self._test_command_line_raises(command)

            self.assertIn(message, stderr.getvalue())

    def test_command_line_convert_output_format_binary(self):
        test_file = 'tests/files/convert.hex'
        binfile = bincopy.BinFile(test_file)

        datas = [
            ('binary', binfile.as_binary()),
            ('binary,0', binfile.as_binary(0)),
            ('binary,0,100', binfile.as_binary(0, 100))
        ]

        for output_format, expected_output in datas:
            command = ['bincopy', 'convert', '-o', output_format, test_file, '-']
            self._test_command_line_ok_bytes(command, expected_output)

    def test_command_line_convert_output_format_binary_bad_addresses(self):
        test_file = 'tests/files/convert.hex'

        datas = [
            ('binary,x', "invalid binary minimum address 'x'"),
            ('binary,0,y', "invalid binary maximum address 'y'")
        ]

        for output_format, message in datas:
            command = ['bincopy', 'convert', '-o', output_format, test_file, '-']
            stderr = StringIO()

            with patch('sys.stderr', stderr):
                with self.assertRaises(SystemExit):
                    self._test_command_line_raises(command)

            self.assertIn(message, stderr.getvalue())

    def test_command_line_convert_overlapping(self):
        test_file = 'tests/files/convert.hex'

        command = [
            'bincopy', 'convert', '-o', 'binary',
            test_file, test_file,
            '-'
        ]

        with self.assertRaises(SystemExit) as cm:
            self._test_command_line_raises(command)

        self.assertEqual(
            str(cm.exception),
            'error: overlapping segments detected, give --overwrite to '
            'overwrite overlapping segments')

    def test_command_line_convert_overwrite(self):
        test_file = 'tests/files/convert.hex'
        binfile = bincopy.BinFile(test_file)

        # Auto input format.
        command = [
            'bincopy', 'convert', '-o', 'binary',
            '--overwrite',
            test_file, test_file,
            '-'
        ]
        self._test_command_line_ok_bytes(command, binfile.as_binary())

        # Given ihex input format.
        command = [
            'bincopy', 'convert', '-i', 'ihex', '-o', 'binary',
            '--overwrite',
            test_file, test_file,
            '-'
        ]
        self._test_command_line_ok_bytes(command, binfile.as_binary())

    def test_command_line_pretty(self):
        pretty_files = [
            'tests/files/convert.pretty.s19',
            'tests/files/empty_main.pretty.hex',
            'tests/files/empty_main.pretty.s19',
            'tests/files/empty_main.pretty.hex.txt',
            'tests/files/in.pretty.hex',
            'tests/files/in.pretty.s19',
            'tests/files/in.pretty.hex.txt'
        ]

        for pretty_file in pretty_files:
            with open(pretty_file, 'r') as fin:
                expected_output = fin.read()

            command = ['bincopy', 'pretty', pretty_file.replace('.pretty', '')]
            self._test_command_line_ok(command, expected_output)

    def test_command_line_non_existing_file(self):
        subcommands = ['info', 'as_hexdump', 'as_srec', 'as_ihex']

        for subcommand in subcommands:
            command = ['bincopy', subcommand, 'non-existing-file']

            with self.assertRaises(SystemExit) as cm:
                self._test_command_line_raises(command)

            self.assertEqual(cm.exception.code,
                            "error: [Errno 2] No such file or directory: 'non-existing-file'")

    def test_command_line_non_existing_file_debug(self):
        subcommands = ['info', 'as_hexdump', 'as_srec', 'as_ihex']

        for subcommand in subcommands:
            command = ['bincopy', '--debug', subcommand, 'non-existing-file']

            with self.assertRaises(IOError):
                self._test_command_line_raises(command)

    def test_command_line_dump_commands_one_file(self):
        test_file = 'tests/files/empty_main.s19'
        binfile = bincopy.BinFile(test_file)

        datas = [
            ('as_hexdump', binfile.as_hexdump()),
            ('as_srec', binfile.as_srec()),
            ('as_ihex', binfile.as_ihex()),
            ('as_ti_txt', binfile.as_ti_txt())
        ]

        for subcommand, expected_output in datas:
            command = ['bincopy', subcommand, test_file]
            self._test_command_line_ok(command, expected_output)

    def test_command_line_info_one_file(self):
        with open('tests/files/empty_main.info.txt', 'r') as fin:
            expected_output = fin.read()

        self._test_command_line_ok(
            ['bincopy', 'info', 'tests/files/empty_main.s19'],
            expected_output)

    def test_command_line_info_two_files(self):
        with open('tests/files/empty_main_and_in.info.txt', 'r') as fin:
            expected_output = fin.read()

        self._test_command_line_ok(
            ['bincopy', 'info', 'tests/files/empty_main.s19', 'tests/files/in.s19'],
            expected_output)

    def test_command_line_info_two_files_with_header_encoding(self):
        with open('tests/files/empty_main_and_in_header.info.txt', 'r') as fin:
            expected_output = fin.read()

        self._test_command_line_ok(
            ['bincopy', 'info',
             '--header-encoding', 'utf-8',
             'tests/files/empty_main.s19',
             'tests/files/in.s19'],
            expected_output)

    def test_command_line_info_one_file_16_bits_words(self):
        with open('tests/files/in_16bits_word.info.txt', 'r') as fin:
            expected_output = fin.read()

        self._test_command_line_ok(
            [
                'bincopy', 'info',
                '--word-size-bits', '16',
                'tests/files/in_16bits_word.s19'
            ],
            expected_output)

    def test_command_line_fill(self):
        shutil.copy('tests/files/out.hex', 'fill.hex')

        self._test_command_line_ok(
            [
                'bincopy', 'fill',
                'fill.hex'
            ],
            '')

        self.assert_files_equal('fill.hex', 'tests/files/fill.hex')

    def test_command_line_fill_max_words(self):
        shutil.copy('tests/files/out.s19', 'fill_max_words.s19')

        self._test_command_line_ok(
            [
                'bincopy', 'fill',
                '--max-words', '200',
                'fill_max_words.s19'
            ],
            '')

        self.assert_files_equal('fill_max_words.s19',
                                'tests/files/fill_max_words.s19')

    def test_command_line_fill_value(self):
        shutil.copy('tests/files/out.hex.txt', 'fill_value.hex.txt')

        self._test_command_line_ok(
            [
                'bincopy', 'fill',
                '--value', '0',
                'fill_value.hex.txt'
            ],
            '')

        self.assert_files_equal('fill_value.hex.txt',
                                'tests/files/fill_value.hex.txt')

    def test_command_line_fill_outfile(self):
        shutil.copy('tests/files/out.hex', 'fill_outfile.hex')

        self._test_command_line_ok(
            [
                'bincopy', 'fill',
                'fill_outfile.hex',
                'fill_outfile_outfile.hex'
            ],
            '')

        self.assert_files_equal('fill_outfile.hex', 'tests/files/out.hex')
        self.assert_files_equal('fill_outfile_outfile.hex',
                                'tests/files/fill_outfile_outfile.hex')

    def test_command_line_fill_stdout(self):
        shutil.copy('tests/files/out.hex', 'fill_stdout.hex')

        self._test_command_line_ok(
            [
                'bincopy', 'fill',
                'fill_stdout.hex',
                '-'
            ],
            ':200000007C0802A6900100049421FFF07C6C1B787C8C23783C600000386300004BFFFFE5F8\n'
            ':20002000398000007D83637880010014382100107C0803A64E80002048656C6C6F20776F19\n'
            ':20004000726C642E0A00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF40\n'
            ':20006000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFA0\n'
            ':20008000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF80\n'
            ':2000A000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF60\n'
            ':2000C000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF40\n'
            ':2000E000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF20\n'
            ':20010000214601360121470136007EFE09D219012146017E17C20001FF5F16002148011979\n'
            ':20012000194E79234623965778239EDA3F01B2CA3F0156702B5E712B722B7321460134219F\n'
            ':20014000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFBF\n'
            ':20016000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF9F\n'
            ':20018000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7F\n'
            ':2001A000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5F\n'
            ':2001C000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF3F\n'
            ':2001E000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF1F\n'
            ':20020000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFE\n'
            ':20022000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFDE\n'
            ':20024000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFBE\n'
            ':20026000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF9E\n'
            ':20028000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7E\n'
            ':2002A000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5E\n'
            ':2002C000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF3E\n'
            ':2002E000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF1E\n'
            ':20030000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFD\n'
            ':20032000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFDD\n'
            ':20034000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFBD\n'
            ':20036000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF9D\n'
            ':20038000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7D\n'
            ':2003A000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D\n'
            ':2003C000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF3D\n'
            ':2003E000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF1D\n'
            ':0304000068656AC2\n'
            ':0400000500000000F7\n'
            ':00000001FF\n')

        self.assert_files_equal('fill_stdout.hex', 'tests/files/out.hex')

    def test_bad_word_size(self):
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.BinFile(word_size_bits=7)

        self.assertEqual(str(cm.exception),
                         'word size must be a multiple of 8 bits, but got 7 bits')

    def _test_command_line_raises(self, command):
        stdout = StringIO()

        try:
            with patch('sys.stdout', stdout):
                with patch('sys.argv', command):
                    bincopy._main()
        finally:
            self.assertEqual(stdout.getvalue(), '')

    def _test_command_line_ok(self, command, expected_output):
        stdout = StringIO()

        with patch('sys.stdout', stdout):
            with patch('sys.argv', command):
                bincopy._main()

        self.assertEqual(stdout.getvalue(), expected_output)

    def _test_command_line_ok_bytes(self, command, expected_output):
        if sys.version_info[0] >= 3:
            Stdout = namedtuple('stdout', ['buffer'])
            stdout = Stdout(BytesIO())

            with patch('sys.stdout', stdout):
                with patch('sys.argv', command):
                    bincopy._main()

            self.assertEqual(stdout.buffer.getvalue(), expected_output)
        else:
            stdout = StringIO()

            with patch('sys.stdout', stdout):
                with patch('sys.argv', command):
                    bincopy._main()

            self.assertEqual(stdout.getvalue(), expected_output)

    def test_ignore_blank_lines_hex(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in_blank_lines.hex', 'r') as fin:
            binfile.add_ihex(fin.read())

        with open('tests/files/in.hex', 'r') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

    def test_ignore_blank_lines_srec(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in_blank_lines.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        with open('tests/files/in.s19', 'r') as fin:
            self.assertEqual(binfile.as_srec(28, 16), fin.read())

    def test_add_elf(self):
        bf = bincopy.BinFile()
        bf.add_elf_file('tests/files/elf.out')

        with open('tests/files/elf.s19', 'r') as fin:
            self.assertEqual(bf.as_srec(), fin.read())

    def test_add_elf_blinky(self):
        bf = bincopy.BinFile()
        bf.add_elf_file('tests/files/evkbimxrt1050_iled_blinky_sdram.axf')
        actual_srec = bf.as_srec()

        bf = bincopy.BinFile()
        bf.add_srec_file('tests/files/evkbimxrt1050_iled_blinky_sdram.s19')
        expected_srec = bf.as_srec()

        self.assertEqual(actual_srec, expected_srec)

    def test_add_elf_gcc(self):
        bf = bincopy.BinFile()
        bf.add_elf_file('tests/files/elf/gcc.elf')

        with open('tests/files/elf/gcc.bin', 'rb') as fin:
            self.assertEqual(bf.as_binary(), fin.read())

    def test_add_elf_iar(self):
        bf = bincopy.BinFile()
        bf.add_elf_file('tests/files/elf/iar.out')

        with open('tests/files/elf/iar.bin', 'rb') as fin:
            self.assertEqual(bf.as_binary(), fin.read())

    def test_exclude_edge_cases(self):
        binfile = bincopy.BinFile()
        binfile.add_binary(b'1234', address=10)
        binfile.exclude(8, 10)
        binfile.exclude(14, 15)
        self.assertEqual(binfile.as_binary(), b"1234")
        self.assertEqual(len(binfile.segments), 1)
        binfile.exclude(8, 11)
        binfile.exclude(13, 15)
        self.assertEqual(binfile.as_binary(), b"23")
        self.assertEqual(len(binfile.segments), 1)

    def test_verilog_vmem(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in-8.vmem', 'r') as fin:
            binfile.add_verilog_vmem(fin.read())

        with open('tests/files/in-8.vmem', 'r') as fin:
            self.assertEqual(binfile.as_verilog_vmem(), fin.read())

        binfile = bincopy.BinFile(word_size_bits=32)

        with open('tests/files/in-32.vmem', 'r') as fin:
            binfile.add_verilog_vmem(fin.read())

        with open('tests/files/in-32.vmem', 'r') as fin:
            self.assertEqual(binfile.as_verilog_vmem(), fin.read())

        binfile = bincopy.BinFile()

        with open('tests/files/empty_main-8.vmem', 'r') as fin:
            binfile.add_verilog_vmem(fin.read())

        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())


if __name__ == '__main__':
    unittest.main()
