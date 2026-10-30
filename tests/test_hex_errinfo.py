import pytest

try:
    from src.pymcprotocol import Type3E, Type4E
    from src.pymcprotocol import mcprotocolerror
    from src.pymcprotocol.mcprotocolerror import MCProtocolError
    from src.pymcprotocol.mcprotocolconst import DeviceCodeError
    from src.pymcprotocol.type3e import get_device_number
except ImportError:
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from src.pymcprotocol import Type3E, Type4E
    from src.pymcprotocol import mcprotocolerror
    from src.pymcprotocol.mcprotocolerror import MCProtocolError
    from src.pymcprotocol.mcprotocolconst import DeviceCodeError
    from src.pymcprotocol.type3e import get_device_number


# ---------------------------------------------------------------------------
# (1) ASCII mode _make_devicedata & hex device-name parsing
# ---------------------------------------------------------------------------

class TestAsciiHexDeviceData:
    def test_ascii_q_hex_devices(self):
        plc = Type3E("Q")
        plc.setaccessopt(commtype="ascii")
        assert plc._make_devicedata("X1A") == b"X*00001A"
        assert plc._make_devicedata("X10") == b"X*000010"
        assert plc._make_devicedata("Y1F") == b"Y*00001F"
        assert plc._make_devicedata("B100") == b"B*000100"
        assert plc._make_devicedata("W1A") == b"W*00001A"
        assert plc._make_devicedata("SB1A") == b"SB00001A"
        assert plc._make_devicedata("SW1A") == b"SW00001A"
        assert plc._make_devicedata("DX1A") == b"DX00001A"
        assert plc._make_devicedata("DY1A") == b"DY00001A"
        assert plc._make_devicedata("ZR1A") == b"ZR00001A"

    def test_ascii_iqr_hex_devices(self):
        plc = Type3E("iQ-R")
        plc.setaccessopt(commtype="ascii")
        assert plc._make_devicedata("W1F") == b"W***0000001F"
        assert plc._make_devicedata("X1A") == b"X***0000001A"
        assert plc._make_devicedata("Y10") == b"Y***00000010"
        assert plc._make_devicedata("SB1A") == b"SB**0000001A"
        assert plc._make_devicedata("SW1F") == b"SW**0000001F"
        assert plc._make_devicedata("DX1A") == b"DX**0000001A"
        assert plc._make_devicedata("DY1A") == b"DY**0000001A"
        assert plc._make_devicedata("ZR1A") == b"ZR**0000001A"

    def test_ascii_decimal_devices_unchanged(self):
        plc = Type3E("Q")
        plc.setaccessopt(commtype="ascii")
        assert plc._make_devicedata("D100") == b"D*000100"
        assert plc._make_devicedata("M10") == b"M*000010"
        assert plc._make_devicedata("L10") == b"L*000010"
        assert plc._make_devicedata("F10") == b"F*000010"
        assert plc._make_devicedata("V10") == b"V*000010"
        assert plc._make_devicedata("SM10") == b"SM000010"
        assert plc._make_devicedata("SD10") == b"SD000010"
        assert plc._make_devicedata("TS10") == b"TS000010"
        assert plc._make_devicedata("TC10") == b"TC000010"
        assert plc._make_devicedata("TN10") == b"TN000010"
        assert plc._make_devicedata("CS10") == b"CS000010"
        assert plc._make_devicedata("CC10") == b"CC000010"
        assert plc._make_devicedata("CN10") == b"CN000010"
        assert plc._make_devicedata("R10") == b"R*000010"

        iqr = Type3E("iQ-R")
        iqr.setaccessopt(commtype="ascii")
        assert iqr._make_devicedata("D100") == b"D***00000100"
        assert iqr._make_devicedata("LZ1") == b"LZ**00000001"
        assert iqr._make_devicedata("RD10") == b"RD**00000010"

    def test_binary_mode_unchanged(self):
        plc = Type3E("Q")
        plc.setaccessopt(commtype="binary")
        assert plc._make_devicedata("X1A") == b"\x1a\x00\x00\x9c"
        assert plc._make_devicedata("X10") == b"\x10\x00\x00\x9c"
        assert plc._make_devicedata("D100") == b"\x64\x00\x00\xa8"

        iqr = Type3E("iQ-R")
        iqr.setaccessopt(commtype="binary")
        assert iqr._make_devicedata("W1F") == b"\x1f\x00\x00\x00\xb4\x00"
        assert iqr._make_devicedata("D100") == b"\x64\x00\x00\x00\xa8\x00"

    def test_hex_letter_leading_device_numbers_and_backward_compat(self):
        plc_ascii = Type3E("Q")
        plc_ascii.setaccessopt(commtype="ascii")
        plc_bin = Type3E("Q")
        plc_bin.setaccessopt(commtype="binary")

        # Leading hex letters (XA0, XFFF, etc.)
        assert get_device_number("XA0") == "A0"
        assert get_device_number("XFFF") == "FFF"
        assert plc_ascii._make_devicedata("XA0") == b"X*0000A0"
        assert plc_bin._make_devicedata("XA0") == b"\xa0\x00\x00\x9c"
        assert plc_ascii._make_devicedata("XFFF") == b"X*000FFF"
        assert plc_bin._make_devicedata("XFFF") == b"\xff\x0f\x00\x9c"
        assert plc_ascii._make_devicedata("YA") == b"Y*00000A"
        assert plc_ascii._make_devicedata("BA0") == b"B*0000A0"
        assert plc_ascii._make_devicedata("WFF") == b"W*0000FF"
        assert plc_ascii._make_devicedata("SBA0") == b"SB0000A0"
        assert plc_ascii._make_devicedata("SWFF") == b"SW0000FF"
        assert plc_ascii._make_devicedata("DXA0") == b"DX0000A0"
        assert plc_ascii._make_devicedata("DYF0") == b"DY0000F0"
        assert plc_ascii._make_devicedata("ZRAB") == b"ZR0000AB"

        # Backward compatibility for X0A, X0FFF, X0x1A
        assert plc_ascii._make_devicedata("X0A") == b"X*00000A"
        assert plc_bin._make_devicedata("X0A") == b"\x0a\x00\x00\x9c"
        assert plc_ascii._make_devicedata("X0FFF") == b"X*000FFF"
        assert plc_ascii._make_devicedata("X0x1A") == b"X*00001A"

        # Invalid device names still fail appropriately
        with pytest.raises(DeviceCodeError):
            plc_ascii._make_devicedata("Q10")
        with pytest.raises(DeviceCodeError):
            plc_ascii._make_devicedata("DA0")
        with pytest.raises(ValueError):
            plc_ascii._make_devicedata("100")
        with pytest.raises(ValueError):
            plc_ascii._make_devicedata("X")


# ---------------------------------------------------------------------------
# (2) MCProtocolError attributes & error info parsing in _check_cmdanswer
# ---------------------------------------------------------------------------

class TestMCProtocolErrorInfo:
    def test_mcprotocolerror_direct_instantiation(self):
        err = MCProtocolError(0xC051)
        assert err.errorcode == "0xC051"
        assert err.endcode == 0xC051
        assert err.network is None
        assert err.pc is None
        assert err.module_io is None
        assert err.station is None
        assert err.command is None
        assert err.subcommand is None
        assert str(err) == "mc protocol error: error code 0xC051"
        assert err.args == ("mc protocol error: error code 0xC051",)
        assert "devicecode error" not in (MCProtocolError.__doc__ or "")

    def test_mcprotocolerror_with_optional_fields(self):
        err = MCProtocolError(
            0xC051,
            network=1,
            pc=0xFE,
            module_io=0x03FF,
            station=2,
            command=0x0401,
            subcommand=0x0002,
        )
        assert err.errorcode == "0xC051"
        assert err.endcode == 0xC051
        assert err.network == 1
        assert err.pc == 0xFE
        assert err.module_io == 0x03FF
        assert err.station == 2
        assert err.command == 0x0401
        assert err.subcommand == 0x0002
        assert str(err) == "mc protocol error: error code 0xC051"

    def test_3e_binary_abnormal_response_with_error_info(self):
        plc = Type3E("Q")
        plc.setaccessopt(commtype="binary")
        # 9-byte header + 2-byte endcode (0xC051) + 9-byte error info
        recv = (
            b"\xd0\x00\x00\xff\xff\x03\x00\x0b\x00"
            + b"\x51\xc0"
            + b"\x01\xfe\xff\x03\x02\x01\x04\x02\x00"
        )
        with pytest.raises(MCProtocolError) as exc_info:
            plc._check_cmdanswer(recv)
        err = exc_info.value
        assert err.errorcode == "0xC051"
        assert err.endcode == 0xC051
        assert err.network == 1
        assert err.pc == 0xFE
        assert err.module_io == 0x03FF
        assert err.station == 2
        assert err.command == 0x0401
        assert err.subcommand == 0x0002

    def test_3e_ascii_abnormal_response_with_error_info(self):
        plc = Type3E("Q")
        plc.setaccessopt(commtype="ascii")
        # 18-char header + 4-char endcode ("C051") + 18-char error info
        recv = b"D00000FF03FF000016" + b"C051" + b"01FE03FF0204010002"
        with pytest.raises(MCProtocolError) as exc_info:
            plc._check_cmdanswer(recv)
        err = exc_info.value
        assert err.errorcode == "0xC051"
        assert err.endcode == 0xC051
        assert err.network == 1
        assert err.pc == 0xFE
        assert err.module_io == 0x03FF
        assert err.station == 2
        assert err.command == 0x0401
        assert err.subcommand == 0x0002

    def test_4e_binary_abnormal_response_with_error_info(self):
        plc = Type4E("Q")
        plc.setaccessopt(commtype="binary")
        # 13-byte header + 2-byte endcode (0xC051) + 9-byte error info
        recv = (
            b"\xd4\x00\x34\x12\x00\x00\x00\xff\xff\x03\x00\x0b\x00"
            + b"\x51\xc0"
            + b"\x03\xff\xe0\x03\x00\x01\x14\x00\x00"
        )
        with pytest.raises(MCProtocolError) as exc_info:
            plc._check_cmdanswer(recv)
        err = exc_info.value
        assert err.errorcode == "0xC051"
        assert err.endcode == 0xC051
        assert err.network == 3
        assert err.pc == 0xFF
        assert err.module_io == 0x03E0
        assert err.station == 0
        assert err.command == 0x1401
        assert err.subcommand == 0x0000

    def test_4e_ascii_abnormal_response_with_error_info(self):
        plc = Type4E("Q")
        plc.setaccessopt(commtype="ascii")
        # 26-char header + 4-char endcode ("C051") + 18-char error info
        recv = b"D4001234000000FF03FF000016" + b"C051" + b"03FF03E00014010000"
        with pytest.raises(MCProtocolError) as exc_info:
            plc._check_cmdanswer(recv)
        err = exc_info.value
        assert err.errorcode == "0xC051"
        assert err.endcode == 0xC051
        assert err.network == 3
        assert err.pc == 0xFF
        assert err.module_io == 0x03E0
        assert err.station == 0
        assert err.command == 0x1401
        assert err.subcommand == 0x0000

    def test_abnormal_response_without_error_info(self):
        plc_bin = Type3E("Q")
        plc_bin.setaccessopt(commtype="binary")
        recv_bin = b"\xd0\x00\x00\xff\xff\x03\x00\x02\x00\x51\xc0"
        with pytest.raises(MCProtocolError) as exc_info:
            plc_bin._check_cmdanswer(recv_bin)
        err = exc_info.value
        assert err.errorcode == "0xC051"
        assert err.endcode == 0xC051
        assert err.network is None
        assert err.pc is None
        assert err.module_io is None
        assert err.station is None
        assert err.command is None
        assert err.subcommand is None

        plc_ascii = Type3E("Q")
        plc_ascii.setaccessopt(commtype="ascii")
        recv_ascii = b"D00000FF03FF000004C051"
        with pytest.raises(MCProtocolError) as exc_info:
            plc_ascii._check_cmdanswer(recv_ascii)
        err_a = exc_info.value
        assert err_a.errorcode == "0xC051"
        assert err_a.endcode == 0xC051
        assert err_a.network is None
        assert err_a.subcommand is None


# ---------------------------------------------------------------------------
# (3) Empty / short replies must raise an error instead of reading as success
# ---------------------------------------------------------------------------

class TestEmptyAndShortReplies:
    @pytest.mark.parametrize(
        "recv",
        [
            b"",
            b"\xd0\x00",
            b"\xd0\x00\x00\xff\xff\x03\x00\x02\x00",       # 9 bytes (header only)
            b"\xd0\x00\x00\xff\xff\x03\x00\x02\x00\x00",   # 10 bytes (1 byte short)
        ],
    )
    def test_3e_binary_short_replies_raise(self, recv):
        plc = Type3E("Q")
        plc.setaccessopt(commtype="binary")
        with pytest.raises((ValueError, MCProtocolError)):
            plc._check_cmdanswer(recv)

    @pytest.mark.parametrize(
        "recv",
        [
            b"",
            b"D000",
            b"D00000FF03FF000004",       # 18 bytes (header only)
            b"D00000FF03FF000004000",    # 21 bytes (1 byte short, even with '0's)
        ],
    )
    def test_3e_ascii_short_replies_raise(self, recv):
        plc = Type3E("Q")
        plc.setaccessopt(commtype="ascii")
        with pytest.raises((ValueError, MCProtocolError)):
            plc._check_cmdanswer(recv)

    @pytest.mark.parametrize(
        "recv",
        [
            b"",
            b"\xd4\x00\x00\x00\x00\x00\x00\xff\xff\x03\x00\x02\x00",       # 13 bytes
            b"\xd4\x00\x00\x00\x00\x00\x00\xff\xff\x03\x00\x02\x00\x00",   # 14 bytes
        ],
    )
    def test_4e_binary_short_replies_raise(self, recv):
        plc = Type4E("Q")
        plc.setaccessopt(commtype="binary")
        with pytest.raises((ValueError, MCProtocolError)):
            plc._check_cmdanswer(recv)

    @pytest.mark.parametrize(
        "recv",
        [
            b"",
            b"D4000000000000FF03FF000004",       # 26 bytes
            b"D4000000000000FF03FF000004000",    # 29 bytes
        ],
    )
    def test_4e_ascii_short_replies_raise(self, recv):
        plc = Type4E("Q")
        plc.setaccessopt(commtype="ascii")
        with pytest.raises((ValueError, MCProtocolError)):
            plc._check_cmdanswer(recv)

    def test_batchread_empty_reply_raises_and_is_compatible_with_both_catch_types(self, monkeypatch):
        plc = Type3E("Q")
        plc.setaccessopt(commtype="binary")
        monkeypatch.setattr(plc, "_send", lambda data: None)
        monkeypatch.setattr(plc, "_recv", lambda: b"")

        with pytest.raises(ValueError):
            plc.batchread_wordunits("D100", 1)

        with pytest.raises(MCProtocolError):
            plc.batchwrite_wordunits("D100", [1])
