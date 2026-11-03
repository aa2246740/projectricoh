"""Expose two additional matrix inputs already present in the official HID tables."""
EXTRA_KEYS={'ADJ_LEFT':27,'ADJ_RIGHT':26}


def install():
    import panel
    panel.KEY_CODES.update(EXTRA_KEYS)


def proof(image):
    import struct
    def read(at,n):
        offset=image.offset(at,n)
        if offset is None:raise ValueError('input table outside image')
        return image.raw[offset:offset+n]
    codes=struct.unpack('>72I',read(0x200c5e78,288));rows=[]
    mapping=[struct.unpack('>HH',read(0x20375f14+4*i,4)) for i in range(29)]
    for name,code in EXTRA_KEYS.items():
        index=codes.index(code);words=struct.unpack('>10I',read(0x200c5338+40*index,40))
        assert index in (32,33) and words[1]==0 and words[3]>>24 in (1,2)
        event=dict(mapping)[code]+29;assert event in (47,48)
        rows.append(dict(name=name,raw=code,HID_index=index,row=0,column_mask=words[3]>>24,
            native_pressed_event=event,source='Official HID matrix and C01 conversion table'))
    return rows
