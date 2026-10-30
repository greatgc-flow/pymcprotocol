"""This file is collection of mcprotocol error.

"""

class MCProtocolError(Exception):
    """MC protocol command error returned by PLC when end code is non-zero.

    Attributes:
        errorcode(str):             Hexadecimal end code string (ex: "0xC051")
        endcode(int):               Integer end code (ex: 0xC051)
        network(int, optional):     Route network No. from error information
        pc(int, optional):          Route PC/station No. from error information
        module_io(int, optional):   Route destination module I/O No. from error information
        station(int, optional):     Route destination module station No. from error information
        command(int, optional):     Command code from error information
        subcommand(int, optional):  Subcommand code from error information

    """
    def __init__(self, errorcode, network=None, pc=None, module_io=None,
                 station=None, command=None, subcommand=None):
        self.endcode = int(errorcode)
        self.errorcode = "0x" + format(self.endcode, "x").rjust(4, "0").upper()
        self.network = network
        self.pc = pc
        self.module_io = module_io
        self.station = station
        self.command = command
        self.subcommand = subcommand
        super().__init__(self.__str__())

    def __str__(self):
        return "mc protocol error: error code {}".format(self.errorcode)


class MCProtocolResponseError(MCProtocolError, ValueError):
    """Raised when an MC protocol reply is empty or shorter than header + end code."""

    def __init__(self, message="Response is empty or shorter than header + end code"):
        self.endcode = None
        self.errorcode = None
        self.network = None
        self.pc = None
        self.module_io = None
        self.station = None
        self.command = None
        self.subcommand = None
        Exception.__init__(self, message)

    def __str__(self):
        return self.args[0] if self.args else ""


class UnsupportedComandError(Exception):
    """This command is not supported by the module you connected.  

    """
    def __init__(self):
        pass

    def __str__(self):
        return "This command is not supported by the module you connected." \
               "If you connect with CPU module, please use E71 module."

    
def check_mcprotocol_error(status, network=None, pc=None, module_io=None,
                           station=None, command=None, subcommand=None):
    """Check mc protocol command error.
    If errot exist(status != 0), raise Error.

    """
    if status == 0:
        return None
    elif status == 0xC059:
        raise UnsupportedComandError
    else:
        raise MCProtocolError(
            status,
            network=network,
            pc=pc,
            module_io=module_io,
            station=station,
            command=command,
            subcommand=subcommand,
        )
