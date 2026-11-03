import struct


def section(raw, wanted):
    order = '>' if raw[5] == 2 else '<'
    start = struct.unpack_from(order + 'I', raw, 32)[0]
    step, count, names_index = struct.unpack_from(order + 'HHH', raw, 46)
    rows = [struct.unpack_from(order + '10I', raw, start + i * step) for i in range(count)]
    row = rows[names_index]
    names = raw[row[4]:row[4] + row[5]]
    for row in rows:
        name = names[row[0]:names.find(b'\0', row[0])].decode()
        if name == wanted:
            return raw[row[4]:row[4] + row[5]]
    raise KeyError(wanted)


def symbol(raw, wanted):
    order = '>' if raw[5] == 2 else '<'
    start = struct.unpack_from(order + 'I', raw, 32)[0]
    step, count = struct.unpack_from(order + 'HH', raw, 46)
    sections = [struct.unpack_from(order + '10I', raw, start + i * step) for i in range(count)]
    for section in sections:
        if section[1] != 2:
            continue
        names_section = sections[section[6]]
        names = raw[names_section[4]:names_section[4] + names_section[5]]
        for offset in range(section[4], section[4] + section[5], section[9]):
            name, value, size, info, other, index = struct.unpack_from(order + 'IIIBBH', raw, offset)
            text = names[name:names.find(b'\0', name)].decode()
            if text == wanted:
                body = sections[index]
                at = body[4] + value - body[3]
                return value, bytes(raw[at:at + size])
    raise KeyError(wanted)
