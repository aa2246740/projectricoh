"""Decode the eight-character gen 126 ERR label into the legacy E/S/P/QQ tuple."""
import argparse
import json

ENTRIES = (1,6,7,8)
STAGES = ('IDLE','T','ROWS','SETTINGS','PREVIEW','COMMITTED','BROWSING')
STATUSES = ('OK','REJECTED','UNCERTAIN','STALE','IO','FAULT')

def encode(entry, stage, status, sequence):
    value = (((ENTRIES.index(entry)*7+stage)*6+status)*256)+(sequence & 255)
    chars = []
    for _ in range(4):
        chars.append('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'[value % 36])
        value //= 36
    return 'ERR ' + ''.join(reversed(chars))

def decode(label):
    if len(label) != 8 or not label.startswith('ERR ') or any(c not in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ' for c in label[4:]):
        raise ValueError('expected ERR followed by four uppercase base-36 characters')
    value = int(label[4:],36)
    if value >= 4*7*6*256:
        raise ValueError('ERR tuple outside the supported domain')
    value, sequence = divmod(value,256)
    value, status = divmod(value,6)
    entry, stage = divmod(value,7)
    return dict(E=ENTRIES[entry], S=stage, P=status, QQ=f'{sequence:02X}',
                stage=STAGES[stage], status=STATUSES[status])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    args = parser.parse_args()
    try:
        print(json.dumps(decode(args.label),indent=2))
    except ValueError as error:
        parser.exit(2,str(error)+'\n')
