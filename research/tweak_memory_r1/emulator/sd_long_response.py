"""Pack the SD controller's R2 registers without the trailing CRC/end byte."""
LONG_COMMANDS=frozenset((2,9))


def response_registers(value,long_response):
    register_value=value>>8 if long_response else value
    return tuple((register_value>>(16*i))&0xffff for i in range(8))


def install():
    import sdcard
    original=sdcard.SdHost.set_response
    if getattr(original,'v310_long_response',False):return
    def set_response(self,value):
        original(self,value)
        words=response_registers(value,self.command_value in LONG_COMMANDS)
        for i,word in enumerate(words):self.regs[0x1a+4*i]=word
    set_response.v310_long_response=True
    sdcard.SdHost.set_response=set_response
