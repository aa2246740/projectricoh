"""Use the native NAND driver's halfword column addresses at the device boundary."""
import devices

OriginalNAND=devices.NAND


class WordColumnNAND(OriginalNAND):
    contract=dict(OriginalNAND.contract,word_columns={
        'full_page':'0x20050100 supplies 1024 halfwords, then 0x20050130 supplies 32 halfwords',
        'transfer':'0x200509bc reads a word for two count units; 0x200509d4 reads one halfword',
        'spare':'0x2004ffec and 0x200501b4 send column 1024 for the spare area',
        'scope':'2048 data bytes plus 64 spare bytes; column cycles count halfwords; identity unchanged'})

    def write(self,addr,data):
        value=int.from_bytes(data,'big')&255
        if addr==0x10000 and value in (0x30,0x10):
            setup=0 if value==0x30 else 0x80
            if self.command!=setup or len(self.addresses) not in (4,5):
                return super().write(addr,data)
            column=2*int.from_bytes(bytes(self.addresses[:2]),'little')
            row=int.from_bytes(bytes(self.addresses[2:]),'little')
            self.commands.append(value)
            if value==0x30:
                self.cursor,self.row=column,row
            else:
                page=bytearray(self.pages.get(row,bytes([255])*2112))
                end=min(2112,column+len(self.program))
                if column>2112:raise devices.DeviceBoundary('NAND word column exceeds page')
                page[column:end]=self.program[:end-column]
                self.pages[row]=bytes(page)
            self.command,self.busy=value,2
            return
        return super().write(addr,data)


def install():
    devices.NAND=WordColumnNAND
