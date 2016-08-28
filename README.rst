|buildstatus|_

Installation
============

.. code-block:: python

    pip install bincopy


Example usage
=============

See the test suite:
https://github.com/eerimoq/bincopy/blob/master/tests/test_bincopy.py

A basic example converting from Intel HEX to Intel HEX, SREC, binary
and array formats:

.. code-block:: python

    >>> import bincopy
    >>> f = bincopy.BinFile()
    >>> f.add_ihex_file("tests/files/in.hex")
    >>> print(f.as_ihex())
    :20010000214601360121470136007EFE09D219012146017E17C20001FF5F16002148011979
    :20012000194E79234623965778239EDA3F01B2CA3F0156702B5E712B722B7321460134219F
    :00000001FF
    
    >>> print(f.as_srec())
    S32500000100214601360121470136007EFE09D219012146017E17C20001FF5F16002148011973
    S32500000120194E79234623965778239EDA3F01B2CA3F0156702B5E712B722B73214601342199
    S5030002FA
    
    >>> f.as_binary()
    b'!F\x016\x01!G\x016\x00~\xfe\t\xd2\x19\x01!F\x01~\x17\xc2\x00\x01\xff_\x16\x00!H\x01\x19\x19Ny#F#\x96Wx#\x9e\xda?\x01\xb2\xca?\x01Vp+^q+r+s!F\x014!'
    
    >>> f.as_array()
    '0x21, 0x46, 0x01, 0x36, 0x01, 0x21, 0x47, 0x01, 0x36, 0x00, 0x7e, 0xfe, 0x09, 0xd2, 0x19, 0x01, 0x21, 0x46, 0x01, 0x7e, 0x17, 0xc2, 0x00, 0x01, 0xff, 0x5f, 0x16, 0x00, 0x21, 0x48, 0x01, 0x19, 0x19, 0x4e, 0x79, 0x23, 0x46, 0x23, 0x96, 0x57, 0x78, 0x23, 0x9e, 0xda, 0x3f, 0x01, 0xb2, 0xca, 0x3f, 0x01, 0x56, 0x70, 0x2b, 0x5e, 0x71, 0x2b, 0x72, 0x2b, 0x73, 0x21, 0x46, 0x01, 0x34, 0x21'



.. |buildstatus| image:: https://travis-ci.org/eerimoq/bincopy.svg
.. _buildstatus: https://travis-ci.org/eerimoq/bincopy
