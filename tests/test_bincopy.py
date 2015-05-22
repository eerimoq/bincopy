import unittest
import io
import bincopy


class BinCopyTest(unittest.TestCase):

    def test_srec(self):
        f = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            f.add_srec(fin)
        with open('tests/files/in.s19') as fin:
            self.assertEqual(f.as_srec(28, 16), fin.read())

        f = bincopy.File()
        with open('tests/files/empty_main.s19', 'r') as fin:
            f.add_srec(fin)
        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(f.as_binary(padding=b'\x00'), fin.read())

        f = bincopy.File()
        with open('tests/files/empty_main_rearranged.s19', 'r') as fin:
            f.add_srec(fin)
        with open('tests/files/empty_main.bin', 'rb') as fin:
            self.assertEqual(f.as_binary(padding=b'\x00'), fin.read())

        try:
            with open('tests/files/bad_crc.s19', 'r') as fin:
                f.add_srec(fin)
            self.fail()
        except ValueError as e:
            print(e)

    def test_ihex(self):
        f = bincopy.File()
        with open('tests/files/in.hex', 'r') as fin:
            f.add_ihex(fin)
        with open('tests/files/in.hex') as fin:
            self.assertEqual(f.as_ihex(), fin.read())

    def test_binary(self):
        f = bincopy.File()
        with open('tests/files/binary1.bin', 'rb') as fin:
            f.add_binary(fin)
        with open('tests/files/binary1.bin', 'rb') as fin:
            self.assertEqual(f.as_binary(), fin.read())

        f = bincopy.File()
        with open('tests/files/binary2.bin', 'rb') as fin:
            f.add_binary(fin, 15)
        try:
            # cannot add overlapping segments
            with open('tests/files/binary2.bin', 'rb') as fin:
                f.add_binary(fin, 20)
            self.fail()
        except ValueError as e:
            print(e)
            # exclude the overlapping part and add
            f.exclude(20, 1024)
            with open('tests/files/binary2.bin', 'rb') as fin:
                f.add_binary(fin, 20)
            with open('tests/files/binary3.bin', 'rb') as fin:
                self.assertEqual(f.as_binary(begin=0, padding=b'\x00'),
                                 fin.read())

    def test_srec_ihex_binary(self):
        f = bincopy.File()
        with open('tests/files/in.hex', 'r') as fin:
            f.add_ihex(fin)
        with open('tests/files/in.s19', 'r') as fin:
            f.add_srec(fin)
        with open('tests/files/binary1.bin', 'rb') as fin:
            f.add_binary(fin, 1024)
        with open('tests/files/out.hex', 'r') as fin:
            self.assertEqual(f.as_ihex(), fin.read())
        with open('tests/files/out.s19') as fin:
            self.assertEqual(f.as_srec(address_length=16), fin.read())
        with open('tests/files/out.bin', 'rb') as fin:
            self.assertEqual(f.as_binary(padding=b'\x00'), fin.read())

    def test_exclude(self):
        f = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            f.add_srec(fin)
        f.exclude(2, 4)
        with open('tests/files/in_exclude_2_4.s19') as fin:
            self.assertEqual(f.as_srec(32, 16), fin.read())

        f = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            f.add_srec(fin)
        f.exclude(3, 1024)
        with open('tests/files/in_exclude_3_1024.s19') as fin:
            self.assertEqual(f.as_srec(32, 16), fin.read())

        f = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            f.add_srec(fin)
        f.exclude(0, 9)
        with open('tests/files/in_exclude_0_9.s19') as fin:
            self.assertEqual(f.as_srec(32, 16), fin.read())

        f = bincopy.File()
        with open('tests/files/empty_main.s19', 'r') as fin:
            f.add_srec(fin)
        f.exclude(0x400240, 0x400600)
        with open('tests/files/empty_main_mod.bin', 'rb') as fin:
            self.assertEqual(f.as_binary(padding=b'\x00'), fin.read())

    def test_minimum_maximum(self):
        f = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            f.add_srec(fin)
        self.assertEqual(f.get_minimum_address(), 0)
        self.assertEqual(f.get_maximum_address(), 70)

    def test_iter_segments(self):
        f = bincopy.File()
        with open('tests/files/in.s19', 'r') as fin:
            f.add_srec(fin)
        i = 0
        for begin, end, data in f.iter_segments():
            i += 1
        self.assertEqual(1, 1)

    def test_cmd_cat(self):
        stdout = io.StringIO()
        bincopy.main(['cat',
                      'tests/files/in.s19',
                      'tests/files/in.hex',
                      '--ihex',
                      'tests/files/binary1.bin',
                      '--binary',
                      '--offset', '1024',
                      '--output',
                      '--address-length', '16'], stdout)
        stdout.seek(0)
        with open('tests/files/out.s19') as fin:
            self.assertEqual(stdout.read(), fin.read())

    def test_cmd_info(self):
        stdout = io.StringIO()
        bincopy.main(['info',
                      'tests/files/in.s19',
                      'tests/files/in.hex',
                      '--ihex',
                      'tests/files/binary1.bin',
                      '--binary',
                      '--offset', '1024'], stdout)
        stdout.seek(0)
        with open('tests/files/info.txt') as fin:
            self.assertEqual(stdout.read(), fin.read())

    def test_cmd_info_exclude_0x0_0x103(self):
        stdout = io.StringIO()
        bincopy.main(['info',
                      'tests/files/out.s19',
                      '--exclude', '0', '0x103'], stdout)
        stdout.seek(0)
        with open('tests/files/info_exclude_0_103.txt') as fin:
            self.assertEqual(stdout.read(), fin.read())

    def test_cmd_info_exclude_0x107_0x401(self):
        stdout = io.StringIO()
        bincopy.main(['info',
                      'tests/files/out.s19',
                      '--exclude', '0x107', '0x401'], stdout)
        stdout.seek(0)
        with open('tests/files/info_exclude_0x107_0x401.txt') as fin:
            self.assertEqual(stdout.read(), fin.read())

    def test_help(self):
        bincopy.main(['--help'])

    def test_ihex_crc(self):
        self.assertEqual(bincopy.crc_ihex('0300300002337a'), 0x1e)
        self.assertEqual(bincopy.crc_ihex('00000000'), 0)

    def test_word_size(self):
        f = bincopy.File(word_size=16)
        with open('tests/files/in_16bits_word.s19', 'r') as fin:
            f.add_srec(fin)
        with open('tests/files/out_16bits_word.s19') as fin:
            self.assertEqual(f.as_srec(30, 24), fin.read())


if __name__ == '__main__':
    unittest.main()
