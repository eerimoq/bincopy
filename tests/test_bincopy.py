from __future__ import print_function

import unittest
import bincopy

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

class BinCopyTest(unittest.TestCase):

    def test_srec(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())

        with open('tests/files/in.s19') as fin:
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
        # pack
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.pack_srec('q', 0, 0, '')

        self.assertEqual(str(cm.exception),
                         "expected record type 0..3 or 5..9, but got 'q'")

        # unpack too short record
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_srec('')

        self.assertEqual(str(cm.exception), "record '' too short")

        # unpack bad first character
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_srec('T0000011')

        self.assertEqual(str(cm.exception),
                         "record 'T0000011' not starting with an 'S'")

        # unpack bad type
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_srec('S.000011')

        self.assertEqual(str(cm.exception),
                         "expected record type 0..3 or 5..9, but got '.'")

        # unpack bad crc
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.unpack_srec('S1000011')

        self.assertEqual(str(cm.exception),
                         "expected crc 'FF' in record S1000011, but got '11'")

    def test_bad_ihex(self):
        # unpack
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

        with open('tests/files/in.hex') as fin:
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
                         ':01FFFF0002FF\n'
                         ':00000001FF\n')

        self.assertEqual(binfile.as_ihex(),
                         ':0100000001FE\n'
                         ':01FFFF0002FF\n'
                         ':00000001FF\n')
        self.assertEqual(binfile.minimum_address, 0)
        self.assertEqual(binfile.maximum_address, 0x10000)
        self.assertEqual(binfile[0], b'\x01')
        self.assertEqual(binfile[0xffff], b'\x02')

    def test_i16hex(self):
        """I16HEX files use only record types 00 through 03 (20 bit
        addresses).

        """

        binfile = bincopy.BinFile()

        binfile.add_ihex(':0100000001FE\n'
                         ':01FFFF0002FF\n'
                         ':02000002FFFFFE\n'
                         ':0100000004FB\n'
                         ':01FFFF0005FC\n'
                         ':020000021000EC\n'
                         ':0100000003FC\n'
                         ':00000001FF\n')

        self.assertEqual(binfile.as_ihex(),
                         ':0100000001FE\n'
                         ':02FFFF000203FB\n'
                         ':02000004000FEB\n'
                         ':01FFF000040C\n'
                         ':020000040010EA\n'
                         ':01FFEF00050C\n'
                         ':00000001FF\n')
        self.assertEqual(binfile.minimum_address, 0)
        self.assertEqual(binfile.maximum_address, 0x10fff0)
        self.assertEqual(binfile[0], b'\x01')
        self.assertEqual(binfile[0xffff], b'\x02')
        self.assertEqual(binfile[0x10000], b'\x03')
        self.assertEqual(binfile[0xffff0], b'\x04')
        self.assertEqual(binfile[0x10ffef], b'\x05')

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
                         ':00000001FF\n')

        self.assertEqual(binfile.as_ihex(),
                         ':0100000001FE\n'
                         ':02FFFF000203FB\n'
                         ':02000004FFFFFC\n'
                         ':0100000004FB\n'
                         ':01FFFF0005FC\n'
                         ':00000001FF\n')
        self.assertEqual(binfile.minimum_address, 0)
        self.assertEqual(binfile.maximum_address, 0x100000000)
        self.assertEqual(binfile[0], b'\x01')
        self.assertEqual(binfile[0xffff], b'\x02')
        self.assertEqual(binfile[0x10000], b'\x03')
        self.assertEqual(binfile[0xffff0000], b'\x04')
        self.assertEqual(binfile[0xffff0002:0xffff0004], b'\xff\xff')
        self.assertEqual(binfile[0xffffffff], b'\x05')

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
            # cannot add overlapping segments
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
        self.assertEqual(len(binfile), 184)

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
        binfile.add_binary(b'506070', address=5)
        binfile.add_binary(b'a0b0c0', address=10)

        # Basic checks.
        self.assertEqual(binfile.minimum_address, 5)
        self.assertEqual(binfile.maximum_address, 13)
        self.assertEqual(len(binfile), 8)

        # Dump with start address beyond end of binary.
        self.assertEqual(binfile.as_binary(minimum_address=14), b'')

        # Dump with start address at maximum address.
        self.assertEqual(binfile.as_binary(minimum_address=13), b'')

        # Dump with start address one before maximum address.
        self.assertEqual(binfile.as_binary(minimum_address=12), b'c0')

        # Dump parts of both segments.
        self.assertEqual(binfile.as_binary(minimum_address=6,
                                           maximum_address=11),
                         b'6070\xff\xff\xff\xffa0')

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

        with self.assertRaises(bincopy.Error) as cm:
            binfile.add('invalid data')

        self.assertEqual(str(cm.exception), 'unsupported file format')

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

        with self.assertRaises(bincopy.Error) as cm:
            binfile.add_file('tests/files/hexdump.txt')

        self.assertEqual(str(cm.exception), 'unsupported file format')

    def test_init_files(self):
        binfile = bincopy.BinFile('tests/files/empty_main_rearranged.s19')

        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        binfile = bincopy.BinFile(['tests/files/in.hex', 'tests/files/in.hex'],
                                  overwrite=True)

        with open('tests/files/in.hex') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

        with self.assertRaises(bincopy.Error) as cm:
            binfile = bincopy.BinFile('tests/files/hexdump.txt')

        self.assertEqual(str(cm.exception), 'unsupported file format')

    def test_array(self):
        binfile = bincopy.BinFile()

        with open('tests/files/in.hex', 'r') as fin:
            binfile.add_ihex(fin.read())

        with open('tests/files/in.i') as fin:
            self.assertEqual(binfile.as_array() + '\n', fin.read())

    def test_hexdump(self):
        binfile = bincopy.BinFile()
        binfile.add_binary(b'12',address=17)
        binfile.add_binary(b'34', address=26)
        binfile.add_binary(b'5678', address=30)
        binfile.add_binary(b'9', address=47)

        with open('tests/files/hexdump.txt') as fin:
            self.assertEqual(binfile.as_hexdump(), fin.read())

        binfile = bincopy.BinFile()
        binfile.add_binary(b'34', address=0x150)
        binfile.add_binary(b'3', address=0x163)
        binfile.add_binary(b'\x01', address=0x260)
        binfile.add_binary(b'3', address=0x263)

        with open('tests/files/hexdump2.txt') as fin:
            self.assertEqual(binfile.as_hexdump(), fin.read())

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

        binfile.exclude(20, 24)
        self.assertEqual(binfile.as_binary(),
                         b'111111' +
                         2 * b'\xff' +
                         b'2222' +
                         4 * b'\xff' +
                         b'333333')

        binfile.exclude(12, 24)
        self.assertEqual(binfile.as_binary(),
                         b'1111' +
                         12 * b'\xff' +
                         b'333333')

        binfile.exclude(11, 25)
        self.assertEqual(binfile.as_binary(),
                         b'111' +
                         14 * b'\xff' +
                         b'33333')

        binfile.exclude(11, 26)
        self.assertEqual(binfile.as_binary(),
                         b'111' +
                         15 * b'\xff' +
                         b'3333')

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
Data address ranges:
                         0x00400238 - 0x004002b4
                         0x004002b8 - 0x0040033e
                         0x00400340 - 0x004003c2
                         0x004003d0 - 0x00400572
                         0x00400574 - 0x0040057d
                         0x00400580 - 0x004006ac
                         0x00600e10 - 0x00601038
""")

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
            binfile.as_ihex(address_length_bits=24)

        self.assertEqual(str(cm.exception),
                         'expected address length 32, but got 24')

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

        # overwrite in empty file
        binfile.add_binary(b'1234', address=512, overwrite=True)
        self.assertEqual(binfile.as_binary(minimum_address=512), b'1234')

        # test setting data with multiple existing segments
        binfile.add_binary(b'123456', address=1024)
        binfile.add_binary(b'99', address=1026, overwrite=True)
        self.assertEqual(binfile.as_binary(minimum_address=512),
                         b'1234' + 508 * b'\xff' + b'129956')

        # test setting data crossing the original segment limits
        binfile.add_binary(b'abc', address=1022, overwrite=True)
        binfile.add_binary(b'def', address=1029, overwrite=True)
        self.assertEqual(binfile.as_binary(minimum_address=512),
                                           b'1234'
                                           + 506 * b'\xff'
                                           + b'abc2995def')

        # overwrite a segment and write outside it
        binfile.add_binary(b'111111111111', address=1021, overwrite=True)
        self.assertEqual(binfile.as_binary(minimum_address=512),
                                           b'1234'
                                           + 505 * b'\xff'
                                           + b'111111111111')

        # overwrite multiple segments (all segments in this test)
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

        # fill empty file
        binfile.fill()
        self.assertEqual(binfile.as_binary(), b'')

    def test_set_get_item(self):
        binfile = bincopy.BinFile()

        binfile.add_binary(b'\x01\x02\x03\x04', address=1)

        self.assertEqual(binfile[:], b'\x01\x02\x03\x04')
        self.assertEqual(binfile[0], b'')
        self.assertEqual(binfile[1], b'\x01')
        self.assertEqual(binfile[2], b'\x02')
        self.assertEqual(binfile[3], b'\x03')
        self.assertEqual(binfile[4], b'\x04')
        self.assertEqual(binfile[5], b'')
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

        binfile[0] = b'\x00'
        self.assertEqual(binfile[:], b'\x00\x01\x02\x03\x04\x05')

        binfile[7] = b'\x07'
        self.assertEqual(binfile[:], b'\x00\x01\x02\x03\x04\x05\xff\x07')
        self.assertEqual(binfile[6], b'\xff')
        self.assertEqual(binfile[6:7], b'\xff')
        self.assertEqual(binfile[6:8], b'\xff\x07')
        self.assertEqual(binfile[5:8], b'\x05\xff\x07')

        # Add data at high address to test get performance.
        binfile[0x10000000] = b'\x12'
        self.assertEqual(binfile[0x10000000 - 1:], b'\xff\x12')

    def test_set_get_item_16(self):
        binfile = bincopy.BinFile(word_size_bits=16)

        binfile.add_binary(b'\x01\x02\x03\x04', address=1)

        self.assertEqual(binfile[:], b'\x01\x02\x03\x04')
        self.assertEqual(binfile[0], b'')
        self.assertEqual(binfile[1], b'\x01\x02')
        self.assertEqual(binfile[2], b'\x03\x04')
        self.assertEqual(binfile[3], b'')
        self.assertEqual(binfile[1:3], b'\x01\x02\x03\x04')
        self.assertEqual(binfile[1:4], b'\x01\x02\x03\x04')

        binfile[1:2] = b'\x05\x06'
        self.assertEqual(binfile[:], b'\x05\x06\x03\x04')

        binfile[2:] = b'\x07\x08\x09\xa0'
        self.assertEqual(binfile[:], b'\x05\x06\x07\x08\x09\xa0')

        binfile[5] = b'\x17\x18'
        self.assertEqual(binfile[:], b'\x05\x06\x07\x08\t\xa0\xff\xff\x17\x18')
        self.assertEqual(binfile[4], b'\xff\xff')
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
        chunk = 1024 * b"1"

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

    def test_command_line_non_existing_file(self):
        subcommands = ['info', 'as_hexdump', 'as_srec', 'as_ihex']

        for subcommand in subcommands:
            argv = ['bincopy', subcommand, 'non-existing-file']
            output = ""

            with self.assertRaises(SystemExit) as cm:
                self._test_command_line_raises(argv, output)

            self.assertEqual(cm.exception.code,
                            "[Errno 2] No such file or directory: 'non-existing-file'")

    def test_command_line_non_existing_file_debug(self):
        subcommands = ['info', 'as_hexdump', 'as_srec', 'as_ihex']

        for subcommand in subcommands:
            argv = ['bincopy', '--debug', subcommand, 'non-existing-file']
            output = ""

            with self.assertRaises(IOError):
                self._test_command_line_raises(argv, output)


    def test_command_line_dump_commands_one_file(self):
        test_file = "tests/files/empty_main.s19"
        binfile = bincopy.BinFile(test_file)

        datas = [
            ('as_hexdump', binfile.as_hexdump()),
            ('as_srec', binfile.as_srec()),
            ('as_ihex', binfile.as_ihex())
        ]

        for subcommand, expected_output in datas:
            command = ['bincopy', subcommand, test_file]
            self._test_command_line_ok(command, expected_output)

    def test_command_line_info_one_file(self):
        self._test_command_line_ok(
            ['bincopy', 'info', 'tests/files/empty_main.s19'],
            """\
Header:                  "bincopy/empty_main.s19"
Execution start address: 0x00400400
Data address ranges:
                         0x00400238 - 0x004002b4
                         0x004002b8 - 0x0040033e
                         0x00400340 - 0x004003c2
                         0x004003d0 - 0x00400572
                         0x00400574 - 0x0040057d
                         0x00400580 - 0x004006ac
                         0x00600e10 - 0x00601038

""")

    def test_command_line_info_two_files(self):
        self._test_command_line_ok(
            ['bincopy', 'info', 'tests/files/empty_main.s19', 'tests/files/in.s19'],
            """\
Header:                  "bincopy/empty_main.s19"
Execution start address: 0x00400400
Data address ranges:
                         0x00400238 - 0x004002b4
                         0x004002b8 - 0x0040033e
                         0x00400340 - 0x004003c2
                         0x004003d0 - 0x00400572
                         0x00400574 - 0x0040057d
                         0x00400580 - 0x004006ac
                         0x00600e10 - 0x00601038

Header:                  "hello     \\x00\\x00"
Execution start address: 0x00000000
Data address ranges:
                         0x00000000 - 0x00000046

""")

    def test_command_line_info_two_files_with_header_encoding(self):
        self._test_command_line_ok(
            ['bincopy',
             'info',
             '--header-encoding', 'utf-8',
             'tests/files/empty_main.s19',
             'tests/files/in.s19'],
            """\
Header:                  "bincopy/empty_main.s19"
Execution start address: 0x00400400
Data address ranges:
                         0x00400238 - 0x004002b4
                         0x004002b8 - 0x0040033e
                         0x00400340 - 0x004003c2
                         0x004003d0 - 0x00400572
                         0x00400574 - 0x0040057d
                         0x00400580 - 0x004006ac
                         0x00600e10 - 0x00601038

Header:                  "hello     \x00\x00"
Execution start address: 0x00000000
Data address ranges:
                         0x00000000 - 0x00000046

""")

    def test_bad_word_size(self):
        with self.assertRaises(bincopy.Error) as cm:
            bincopy.BinFile(word_size_bits=7)

        self.assertEqual(str(cm.exception),
                         'word size must be a multiple of 8 bits, but got 7 bits')

    def _test_command_line_raises(self, argv, expected_output):
        stdout = StringIO()

        try:
            with patch('sys.stdout', stdout):
                with patch('sys.argv', argv):
                    bincopy._main()
        finally:
            self.assertEqual(stdout.getvalue(), expected_output)

    def _test_command_line_ok(self, argv, expected_output):
        stdout = StringIO()

        with patch('sys.stdout', stdout):
            with patch('sys.argv', argv):
                bincopy._main()

        self.assertEqual(stdout.getvalue().rstrip(), expected_output.rstrip())


if __name__ == '__main__':
    unittest.main()
