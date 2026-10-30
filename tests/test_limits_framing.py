import socket
import pytest

try:
    from src.pymcprotocol import Type3E, Type4E
    from src.pymcprotocol.mcprotocolerror import (
        MCProtocolError,
        MCProtocolResponseError,
        UnsupportedComandError,
    )
    from src.pymcprotocol.mcprotocolconst import DeviceConstants, DeviceCodeError
    from src.pymcprotocol.type3e import CommTypeError, PLCTypeError
except ImportError:
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from src.pymcprotocol import Type3E, Type4E
    from src.pymcprotocol.mcprotocolerror import (
        MCProtocolError,
        MCProtocolResponseError,
        UnsupportedComandError,
    )
    from src.pymcprotocol.mcprotocolconst import DeviceConstants, DeviceCodeError
    from src.pymcprotocol.type3e import CommTypeError, PLCTypeError


class FakeSocket:
    """Fake socket that returns pre-configured byte chunks on recv()."""

    def __init__(self, chunks, timeout=2.0):
        self.chunks = list(chunks)
        self.sent = []
        self.timeout = timeout
        self.timeout_history = []
        self.closed = False

    def send(self, data):
        self.sent.append(data)
        return len(data)

    def recv(self, bufsize):
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if isinstance(chunk, BaseException):
            raise chunk
        if len(chunk) > bufsize:
            self.chunks.insert(0, chunk[bufsize:])
            return chunk[:bufsize]
        return chunk

    def settimeout(self, timeout):
        self.timeout = timeout
        self.timeout_history.append(timeout)

    def gettimeout(self):
        return self.timeout

    def close(self):
        self.closed = True


def _make_3e_bin_ok_reply(payload=b""):
    data_len = 2 + len(payload)
    return (
        b"\xd0\x00\x00\xff\xff\x03\x00"
        + data_len.to_bytes(2, "little")
        + b"\x00\x00"
        + payload
    )


def _make_3e_ascii_ok_reply(payload_ascii=b""):
    data_len = 4 + len(payload_ascii)
    return (
        b"D00000FF03FF00"
        + format(data_len, "04X").encode()
        + b"0000"
        + payload_ascii
    )


def _make_4e_bin_ok_reply(payload=b""):
    data_len = 2 + len(payload)
    return (
        b"\xd4\x00\x01\x00\x00\x00\x00\xff\xff\x03\x00"
        + data_len.to_bytes(2, "little")
        + b"\x00\x00"
        + payload
    )


def _make_4e_ascii_ok_reply(payload_ascii=b""):
    data_len = 4 + len(payload_ascii)
    return (
        b"D4000001000000FF03FF00"
        + format(data_len, "04X").encode()
        + b"0000"
        + payload_ascii
    )


# ---------------------------------------------------------------------------
# (4) Client-side random-access limit checks before send
# ---------------------------------------------------------------------------

class TestRandomAccessLimits:
    @pytest.mark.parametrize("plctype,max_points", [("Q", 192), ("L", 192), ("iQ-R", 96)])
    def test_randomread_limits_enforced_for_q_l_iqr(self, plctype, max_points):
        plc = Type3E(plctype)
        sent = []
        plc._send = lambda data: sent.append(data)
        plc._recv = lambda: _make_3e_bin_ok_reply(b"\x00\x00" * max_points)

        # Exactly N (all words) succeeds
        words_n = [f"D{i}" for i in range(max_points)]
        w_vals, dw_vals = plc.randomread(words_n, [])
        assert len(w_vals) == max_points
        assert len(dw_vals) == 0
        assert len(sent) == 1

        # Exactly N (mixed words + dwords) succeeds
        sent.clear()
        plc._recv = lambda: _make_3e_bin_ok_reply(b"\x00\x00" * (max_points - 10) + b"\x00\x00\x00\x00" * 10)
        w_vals, dw_vals = plc.randomread([f"D{i}" for i in range(max_points - 10)], [f"D{i}" for i in range(10)])
        assert len(w_vals) == max_points - 10
        assert len(dw_vals) == 10
        assert len(sent) == 1

        # N + 1 fails before send
        sent.clear()
        with pytest.raises(ValueError):
            plc.randomread([f"D{i}" for i in range(max_points + 1)], [])
        assert sent == []

        with pytest.raises(ValueError):
            plc.randomread([f"D{i}" for i in range(max_points)], ["D0"])
        assert sent == []

        # 0 total fails before send
        with pytest.raises(ValueError):
            plc.randomread([], [])
        assert sent == []

    @pytest.mark.parametrize("plctype", ["QnA", "iQ-L"])
    def test_randomread_limits_skipped_for_qna_and_iql(self, plctype):
        plc = Type3E(plctype)
        sent = []
        plc._send = lambda data: sent.append(data)
        plc._recv = lambda: _make_3e_bin_ok_reply(b"\x00\x00" * 193)

        words = [f"D{i}" for i in range(193)]
        w_vals, _ = plc.randomread(words, [])
        assert len(w_vals) == 193
        assert len(sent) == 1

    @pytest.mark.parametrize("plctype,max_words", [("Q", 160), ("L", 160), ("iQ-R", 80)])
    def test_randomwrite_limits_enforced_for_q_l_iqr(self, plctype, max_words):
        # max_words * 12 == 1920 (Q/L) or 960 (iQ-R)
        plc = Type3E(plctype)
        sent = []
        plc._send = lambda data: sent.append(data)
        plc._recv = lambda: _make_3e_bin_ok_reply()

        # Exactly N (max_words * 12 == limit) succeeds
        plc.randomwrite([f"D{i}" for i in range(max_words)], [0] * max_words, [], [])
        assert len(sent) == 1

        # N + 1 words ((max_words + 1) * 12 > limit) fails before send
        sent.clear()
        with pytest.raises(ValueError):
            plc.randomwrite([f"D{i}" for i in range(max_words + 1)], [0] * (max_words + 1), [], [])
        assert sent == []

        # Mixed words*12 + dwords*14 > limit fails before send
        # (max_words - 1) * 12 + 1 * 14 = limit + 2 > limit
        with pytest.raises(ValueError):
            plc.randomwrite(
                [f"D{i}" for i in range(max_words - 1)],
                [0] * (max_words - 1),
                ["D1000"],
                [0],
            )
        assert sent == []

        # (max_words - 2) * 12 + 1 * 14 = limit - 10 <= limit succeeds
        plc.randomwrite(
            [f"D{i}" for i in range(max_words - 2)],
            [0] * (max_words - 2),
            ["D1000"],
            [0],
        )
        assert len(sent) == 1

        # 0 total fails before send
        sent.clear()
        with pytest.raises(ValueError):
            plc.randomwrite([], [], [], [])
        assert sent == []

    @pytest.mark.parametrize("plctype", ["QnA", "iQ-L"])
    def test_randomwrite_limits_skipped_for_qna_and_iql(self, plctype):
        plc = Type3E(plctype)
        sent = []
        plc._send = lambda data: sent.append(data)
        plc._recv = lambda: _make_3e_bin_ok_reply()

        plc.randomwrite([f"D{i}" for i in range(161)], [0] * 161, [], [])
        assert len(sent) == 1

    @pytest.mark.parametrize("plctype,max_bits", [("Q", 188), ("L", 188), ("iQ-R", 94)])
    def test_randomwrite_bitunits_limits_enforced_for_q_l_iqr(self, plctype, max_bits):
        plc = Type3E(plctype)
        sent = []
        plc._send = lambda data: sent.append(data)
        plc._recv = lambda: _make_3e_bin_ok_reply()

        # Exactly N succeeds
        plc.randomwrite_bitunits([f"M{i}" for i in range(max_bits)], [1] * max_bits)
        assert len(sent) == 1

        # N + 1 fails before send
        sent.clear()
        with pytest.raises(ValueError):
            plc.randomwrite_bitunits([f"M{i}" for i in range(max_bits + 1)], [1] * (max_bits + 1))
        assert sent == []

        # 0 total fails before send
        with pytest.raises(ValueError):
            plc.randomwrite_bitunits([], [])
        assert sent == []

    @pytest.mark.parametrize("plctype", ["QnA", "iQ-L"])
    def test_randomwrite_bitunits_limits_skipped_for_qna_and_iql(self, plctype):
        plc = Type3E(plctype)
        sent = []
        plc._send = lambda data: sent.append(data)
        plc._recv = lambda: _make_3e_bin_ok_reply()

        plc.randomwrite_bitunits([f"M{i}" for i in range(189)], [1] * 189)
        assert len(sent) == 1


# ---------------------------------------------------------------------------
# (5) Framed receive in _recv
# ---------------------------------------------------------------------------

class TestFramedRecv:
    def test_single_chunk_complete_replies(self):
        # 3E binary
        plc3b = Type3E("Q")
        frame3b = _make_3e_bin_ok_reply(b"\x34\x12\x78\x56")
        plc3b._sock = FakeSocket([frame3b])
        plc3b._is_connected = True
        assert plc3b.batchread_wordunits("D100", 2) == [0x1234, 0x5678]

        # 3E ASCII
        plc3a = Type3E("Q")
        plc3a.setaccessopt(commtype="ascii")
        frame3a = _make_3e_ascii_ok_reply(b"12345678")
        plc3a._sock = FakeSocket([frame3a])
        plc3a._is_connected = True
        assert plc3a.batchread_wordunits("D100", 2) == [0x1234, 0x5678]

        # 4E binary
        plc4b = Type4E("Q")
        frame4b = _make_4e_bin_ok_reply(b"\x34\x12")
        plc4b._sock = FakeSocket([frame4b])
        plc4b._is_connected = True
        assert plc4b.batchread_wordunits("D100", 1) == [0x1234]

        # 4E ASCII
        plc4a = Type4E("Q")
        plc4a.setaccessopt(commtype="ascii")
        frame4a = _make_4e_ascii_ok_reply(b"1234")
        plc4a._sock = FakeSocket([frame4a])
        plc4a._is_connected = True
        assert plc4a.batchread_wordunits("D100", 1) == [0x1234]

    def test_split_header_and_body_across_chunks_3e_and_4e(self):
        # 3E binary split across header and payload
        plc3b = Type3E("Q")
        frame3b = _make_3e_bin_ok_reply(b"\x01\x00\x02\x00\x03\x00")
        chunks3b = [frame3b[:3], frame3b[3:8], frame3b[8:11], frame3b[11:14], frame3b[14:]]
        plc3b._sock = FakeSocket(chunks3b)
        plc3b._is_connected = True
        assert plc3b.batchread_wordunits("D100", 3) == [1, 2, 3]

        # 3E ASCII split inside length field and payload
        plc3a = Type3E("Q")
        plc3a.setaccessopt(commtype="ascii")
        frame3a = _make_3e_ascii_ok_reply(b"00010002")
        chunks3a = [frame3a[:5], frame3a[5:16], frame3a[16:20], frame3a[20:25], frame3a[25:]]
        plc3a._sock = FakeSocket(chunks3a)
        plc3a._is_connected = True
        assert plc3a.batchread_wordunits("D100", 2) == [1, 2]

        # 4E binary split across header and payload
        plc4b = Type4E("Q")
        frame4b = _make_4e_bin_ok_reply(b"\x0a\x00\x14\x00")
        chunks4b = [frame4b[:4], frame4b[4:12], frame4b[12:15], frame4b[15:]]
        plc4b._sock = FakeSocket(chunks4b)
        plc4b._is_connected = True
        assert plc4b.batchread_wordunits("D100", 2) == [10, 20]

        # 4E ASCII split across header and payload
        plc4a = Type4E("Q")
        plc4a.setaccessopt(commtype="ascii")
        frame4a = _make_4e_ascii_ok_reply(b"000A0014")
        chunks4a = [frame4a[:10], frame4a[10:24], frame4a[24:31], frame4a[31:]]
        plc4a._sock = FakeSocket(chunks4a)
        plc4a._is_connected = True
        assert plc4a.batchread_wordunits("D100", 2) == [10, 20]

    def test_peer_closing_mid_frame_raises_mcprotocolresponseerror(self):
        # Empty on first read
        plc = Type3E("Q")
        plc._sock = FakeSocket([b""])
        plc._is_connected = True
        with pytest.raises(MCProtocolResponseError):
            plc._recv()

        # Closed mid-header (only 5 of 9 header bytes)
        plc._sock = FakeSocket([b"\xd0\x00\x00\xff\xff", b""])
        with pytest.raises(MCProtocolResponseError):
            plc._recv()

        # Closed mid-body (header claims 6 bytes of data = 2 endcode + 4 payload, only 2 arrive)
        header_claiming_6 = b"\xd0\x00\x00\xff\xff\x03\x00\x06\x00"
        plc._sock = FakeSocket([header_claiming_6, b"\x00\x00", b""])
        with pytest.raises(MCProtocolResponseError):
            plc._recv()

        # 3E ASCII closed mid-body (header claims 8 chars = 4 endcode + 4 payload, only 4 arrive)
        plc_a = Type3E("Q")
        plc_a.setaccessopt(commtype="ascii")
        plc_a._sock = FakeSocket([b"D00000FF03FF000008", b"0000", b""])
        plc_a._is_connected = True
        with pytest.raises(MCProtocolResponseError):
            plc_a._recv()

    def test_claimed_length_cap_raises_mcprotocolresponseerror(self):
        # 3E binary claiming 0xFFFF bytes (total frame 9 + 65535 = 65544 > 64 KiB)
        plc = Type3E("Q")
        plc._sock = FakeSocket([b"\xd0\x00\x00\xff\xff\x03\x00\xff\xff\x00\x00"])
        plc._is_connected = True
        with pytest.raises(MCProtocolResponseError):
            plc._recv()

        # 3E ASCII claiming FFFF chars (total frame 18 + 65535 = 65553 > 64 KiB)
        plc_a = Type3E("Q")
        plc_a.setaccessopt(commtype="ascii")
        plc_a._sock = FakeSocket([b"D00000FF03FF00FFFF0000"])
        plc_a._is_connected = True
        with pytest.raises(MCProtocolResponseError):
            plc_a._recv()

        # Claimed length smaller than endcode size (e.g. 0 or 1 in binary) also raises
        plc._sock = FakeSocket([b"\xd0\x00\x00\xff\xff\x03\x00\x01\x00\x00"])
        with pytest.raises(MCProtocolResponseError):
            plc._recv()

    def test_recv_bounded_by_socket_timeout(self):
        plc = Type3E("Q")
        plc._sock = FakeSocket([b"\xd0\x00\x00", socket.timeout("timed out")])
        plc._is_connected = True
        with pytest.raises(socket.timeout):
            plc._recv()


# ---------------------------------------------------------------------------
# (6) setaccessopt with 0 and socket.settimeout(0) guard
# ---------------------------------------------------------------------------

class TestSetAccessOptZero:
    def test_setaccessopt_zero_applies_to_all_numeric_options(self):
        plc = Type3E("Q")
        plc.setaccessopt(
            network=5,
            pc=10,
            dest_moduleio=0x0123,
            dest_modulesta=4,
            timer_sec=5,
        )
        assert plc.network == 5
        assert plc.pc == 10
        assert plc.dest_moduleio == 0x0123
        assert plc.dest_modulesta == 4
        assert plc.timer == 20

        plc.setaccessopt(
            network=0,
            pc=0,
            dest_moduleio=0,
            dest_modulesta=0,
            timer_sec=0,
        )
        assert plc.network == 0
        assert plc.pc == 0
        assert plc.dest_moduleio == 0
        assert plc.dest_modulesta == 0
        assert plc.timer == 0

    def test_setaccessopt_timer_sec_zero_never_sets_socket_timeout_zero(self):
        plc = Type3E("Q")
        fake_sock = FakeSocket([])
        plc._sock = fake_sock
        plc._is_connected = True

        plc.setaccessopt(timer_sec=0)
        # PLC monitoring timer is 0 (0 * 250ms)
        assert plc.timer == 0
        # Socket timeout must be > 0 (never 0, which would make socket non-blocking)
        assert plc.soc_timeout >= 1
        assert 0 not in fake_sock.timeout_history
        assert fake_sock.gettimeout() >= 1


# ---------------------------------------------------------------------------
# (7) Exception hygiene
# ---------------------------------------------------------------------------

class TestExceptionHygiene:
    def test_all_exceptions_call_super_init_and_have_clean_docstrings(self):
        excs = [
            CommTypeError(),
            PLCTypeError(),
            UnsupportedComandError(),
            DeviceCodeError("Q", "P"),
            MCProtocolError(0xC051),
            MCProtocolResponseError("short frame"),
        ]
        for exc in excs:
            assert len(exc.args) >= 1
            assert exc.args[0] == str(exc)

        assert "Communication type" in (CommTypeError.__doc__ or "")
        assert "PLC type" in (PLCTypeError.__doc__ or "")
        assert "not supported" in (UnsupportedComandError.__doc__ or "")
        assert "devicecode" in (DeviceCodeError.__doc__ or "").lower()
        assert "devicecode error" not in (MCProtocolError.__doc__ or "").lower()


# ---------------------------------------------------------------------------
# (8) LSTC device, LTN dword type, and signed word write guard
# ---------------------------------------------------------------------------

class TestLSTCAndLTNAndWordWriteGuard:
    def test_lstc_and_ltn_device_constants(self):
        assert DeviceConstants.get_binary_devicecode("iQ-R", "LSTC") == (0x58, 10)
        assert DeviceConstants.get_binary_devicecode("iQ-R", "LSTS") == (0x59, 10)
        assert DeviceConstants.get_binary_devicecode("iQ-R", "LSTN") == (0x5A, 10)

        assert DeviceConstants.get_ascii_devicecode("iQ-R", "LSTC") == ("LSTC", 10)
        assert DeviceConstants.get_ascii_devicecode("iQ-R", "LSTS") == ("LSTS", 10)
        assert DeviceConstants.get_ascii_devicecode("iQ-R", "LSTN") == ("LSTN", 10)

        assert DeviceConstants.get_devicetype("iQ-R", "LSTC") == DeviceConstants.BIT_DEVICE
        assert DeviceConstants.get_devicetype("iQ-R", "LSTS") == DeviceConstants.BIT_DEVICE
        assert DeviceConstants.get_devicetype("iQ-R", "LSTN") == DeviceConstants.DWORD_DEVICE
        assert DeviceConstants.get_devicetype("iQ-R", "LTN") == DeviceConstants.DWORD_DEVICE

        with pytest.raises(DeviceCodeError):
            DeviceConstants.get_binary_devicecode("Q", "LSTC")
        with pytest.raises(DeviceCodeError):
            DeviceConstants.get_ascii_devicecode("Q", "LSTC")
        with pytest.raises(DeviceCodeError):
            DeviceConstants.get_devicetype("Q", "LSTC")

        iqr = Type3E("iQ-R")
        assert iqr._make_devicedata("LSTC10") == b"\x0a\x00\x00\x00\x58\x00"
        iqr.setaccessopt(commtype="ascii")
        assert iqr._make_devicedata("LSTC10") == b"LSTC00000010"

    def test_word_writes_still_reject_32768(self):
        for commtype in ("binary", "ascii"):
            plc = Type3E("Q")
            plc.setaccessopt(commtype=commtype)
            sent = []
            plc._send = lambda data: sent.append(data)
            plc._recv = lambda: _make_3e_bin_ok_reply()

            with pytest.raises(ValueError):
                plc.batchwrite_wordunits("D100", [32768])
            assert sent == []

            with pytest.raises(ValueError):
                plc.randomwrite(["D100"], [32768], [], [])
            assert sent == []
