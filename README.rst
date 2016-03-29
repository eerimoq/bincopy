|buildstatus|_

Installation
============

.. code-block:: python

    pip install bincopy


Example usage
=============

See the test suite: https://github.com/eerimoq/bincopy/blob/master/tests/test_bincopy.py

A basic example converting from Intel HEX to Intel HEX, SREC and binary formats:

.. code-block:: python

    >>> import bincopy
    >>> f = bincopy.File()
    >>> with open("tests/files/in.hex", "r") as fin:
    ...     f.add_ihex(fin)
    >>> print(f.as_ihex())
    :020000040000FA
    :20010000214601360121470136007EFE09D219012146017E17C20001FF5F16002148011979
    :20012000194E79234623965778239EDA3F01B2CA3F0156702B5E712B722B7321460134219F
    :00000001FF
    
    >>> print(f.as_srec())
    S32500000100214601360121470136007EFE09D219012146017E17C20001FF5F16002148011973
    S32500000120194E79234623965778239EDA3F01B2CA3F0156702B5E712B722B73214601342199
    S5030002FA
    
    >>> f.as_binary()
    b'!F\x016\x01!G\x016\x00~\xfe\t\xd2\x19\x01!F\x01~\x17\xc2\x00\x01\xff_\x16\x00!H\x01\x19\x19Ny#F#\x96Wx#\x9e\xda?\x01\xb2\xca?\x01Vp+^q+r+s!F\x014!'

.. |buildstatus| image:: https://travis-ci.org/eerimoq/bincopy.svg
.. _buildstatus: https://travis-ci.org/eerimoq/bincopy
