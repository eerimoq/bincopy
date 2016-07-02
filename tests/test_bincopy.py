from __future__ import print_function

import unittest
import bincopy


class BinCopyTest(unittest.TestCase):

    def test_srec(self):
        binfile = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        with open('tests/files/in.s19') as fin:
            self.assertEqual(binfile.as_srec(28, 16), fin.read())

        binfile = bincopy.File()
        with open('tests/files/empty_main.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        binfile = bincopy.File()
        with open('tests/files/empty_main_rearranged.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

        try:
            with open('tests/files/bad_crc.s19', 'r') as fin:
                binfile.add_srec(fin.read())
            self.fail()
        except bincopy.Error as e:
            print(e)

    def test_ihex(self):
        binfile = bincopy.File()
        with open('tests/files/in.hex', 'r') as fin:
            binfile.add_ihex(fin.read())
        with open('tests/files/in.hex') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

    def test_binary(self):
        binfile = bincopy.File()
        with open('tests/files/binary1.bin', 'rb') as fin:
            binfile.add_binary(fin.read())
        with open('tests/files/binary1.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(), fin.read())

        binfile = bincopy.File()
        with open('tests/files/binary2.bin', 'rb') as fin:
            binfile.add_binary(fin.read(), 15)
        try:
            # cannot add overlapping segments
            with open('tests/files/binary2.bin', 'rb') as fin:
                binfile.add_binary(fin.read(), 20)
            self.fail()
        except bincopy.Error as err:
            print(err)
            # exclude the overlapping part and add
            binfile.exclude(20, 1024)
            with open('tests/files/binary2.bin', 'rb') as fin:
                binfile.add_binary(fin.read(), 20)
            with open('tests/files/binary3.bin', 'rb') as fin:
                self.assertEqual(binfile.as_binary(minimum=0, padding=b'\x00'),
                                 fin.read())

    def test_srec_ihex_binary(self):
        binfile = bincopy.File()
        with open('tests/files/in.hex', 'r') as fin:
            binfile.add_ihex(fin.read())
        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        with open('tests/files/binary1.bin', 'rb') as fin:
            binfile.add_binary(fin.read(), 1024)
        with open('tests/files/out.hex', 'r') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())
        with open('tests/files/out.s19') as fin:
            self.assertEqual(binfile.as_srec(address_length=16), fin.read())
        with open('tests/files/out.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

    def test_exclude(self):
        binfile = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        binfile.exclude(2, 4)
        with open('tests/files/in_exclude_2_4.s19') as fin:
            self.assertEqual(binfile.as_srec(32, 16), fin.read())

        binfile = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        binfile.exclude(3, 1024)
        with open('tests/files/in_exclude_3_1024.s19') as fin:
            self.assertEqual(binfile.as_srec(32, 16), fin.read())

        binfile = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        binfile.exclude(0, 9)
        with open('tests/files/in_exclude_0_9.s19') as fin:
            self.assertEqual(binfile.as_srec(32, 16), fin.read())

        binfile = bincopy.File()
        with open('tests/files/empty_main.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        binfile.exclude(0x400240, 0x400600)
        with open('tests/files/empty_main_mod.bin', 'rb') as fin:
            self.assertEqual(binfile.as_binary(padding=b'\x00'), fin.read())

    def test_minimum_maximum(self):
        binfile = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        self.assertEqual(binfile.get_minimum_address(), 0)
        self.assertEqual(binfile.get_maximum_address(), 70)

    def test_iter_segments(self):
        binfile = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        i = 0
        for begin, end, data in binfile.iter_segments():
            del begin, end, data
            i += 1
        self.assertEqual(i, 1)

    def test_ihex_crc(self):
        self.assertEqual(bincopy.crc_ihex('0300300002337a'), 0x1e)
        self.assertEqual(bincopy.crc_ihex('00000000'), 0)

    def test_word_size(self):
        binfile = bincopy.File(word_size=16)
        with open('tests/files/in_16bits_word.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        with open('tests/files/out_16bits_word.s19') as fin:
            self.assertEqual(binfile.as_srec(30, 24), fin.read())

    def test_print(self):
        binfile = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        print(binfile)

    def test_issue_4_1(self):
        binfile = bincopy.File()
        with open('tests/files/issue_4_in.hex', 'r') as fin:
            binfile.add_ihex(fin.read())
        with open('tests/files/issue_4_out.hex', 'r') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

    def test_issue_4_2(self):
        binfile = bincopy.File()
        with open('tests/files/empty_main.s19', 'r') as fin:
            binfile.add_srec(fin.read())
        with open('tests/files/empty_main.hex', 'r') as fin:
            self.assertEqual(binfile.as_ihex(), fin.read())

    def test_performance(self):
        binfile = bincopy.File()

        # Add a 1MB consecutive binary.
        chunk = 1024 * b"1"
        for i in range(1024):
            binfile.add_binary(chunk, 1024 * i)

        self.assertEqual(binfile.get_minimum_address(), 0)
        self.assertEqual(binfile.get_maximum_address(), 1024 * 1024)

        ihex = binfile.as_ihex()
        srec = binfile.as_srec()

        binfile = bincopy.File()
        binfile.add_ihex(ihex)

        binfile = bincopy.File()
        binfile.add_srec(srec)


if __name__ == '__main__':
    unittest.main()
