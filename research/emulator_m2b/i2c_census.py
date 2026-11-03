#!/usr/bin/env python3
"""Read-only census of the native RX byte budget and declared peer inputs."""
import hashlib
import json
from pathlib import Path
import pickle

HERE = Path(__file__).resolve().parent
OUT = HERE/'local'
source = OUT/'i2c-rx-census-r1.json'
checkpoint = OUT/'i2c-rx-census-r1-stop.pkl'
metadata = json.loads(checkpoint.with_suffix('.json').read_text())
assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == metadata['sha256']
state = pickle.loads(checkpoint.read_bytes())
def integer(address):
    for base, data, _ in state['regions']:
        if base <= address and address+4 <= base+len(data):
            return int.from_bytes(data[address-base:address-base+4], 'big')
    raise ValueError('native receive state is not mapped')
remaining = integer(0x204ebb80)
peer = state['devices'][state['device_types'].index('I2cRegisters')]
selector = peer['selector']
requested = list(range(selector, selector+remaining+1))
assert remaining == 1 and selector == 0x41
assert requested == [0x41, 0x42]
assert 0x41 in peer['registers'] and 0x42 not in peer['registers']
result = {
    'premise': 'A one-byte caller request means one register byte on this native controller.',
    'status': 'PREMISE_FALSE',
    'native_driver': {'rounding_pc': '0x200da254/258',
                      'rule': '(caller_length+1) & 0xfffe',
                      'caller_length': 1, 'controller_length': 2,
                      'remaining_before_first_data_read': remaining},
    'peer': {'requested_registers': requested,
             'declared_registers': sorted(peer['registers']),
             'missing_registers': [value for value in requested if value not in peer['registers']]},
    'decision': 'Declare the adjacent padding input 0x42 as zero for this synthetic profile; '
                'retain rejection for other unwritten inputs.',
    'inputs': [{'file': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()},
               {'file': checkpoint.name, 'sha256': metadata['sha256']}],
}
target = OUT/'i2c-byte-census-r1.json'
with target.open('x') as stream:
    stream.write(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
