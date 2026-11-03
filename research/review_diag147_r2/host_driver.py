"""Run the copied acceptance with existing offset metadata and fenced outputs."""
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
module = scope.load(HERE / 'accept_diag147.py', 'review147_acceptance')

def offsets():
    reader = scope.load(scope.ROOT / 'firmware/stage2l_switch/tools/build.py',
                        'review147_offset_reader')
    original = scope.ROOT / 'research/diag147/local/layout147/offsets.o'
    elf = reader.Elf(original)
    symbol = elf.symbols['diag_offsets']
    blob = elf.content(elf.sections[symbol['section']])[
        symbol['value']:symbol['value'] + 4*len(module.FIELDS)]
    result = dict(zip(module.FIELDS, struct.unpack('>%dI' % len(module.FIELDS), blob)))
    scope.save(HERE / 'host-offsets.json', dict(source=str(original.relative_to(scope.ROOT)),
                                             sha256=scope.sha(original), offsets=result))
    return result

module.offsets = offsets
sessions = []
original_boot = module.boot
original_note = module.Card.note

def boot(unit, card):
    result = original_boot(unit, card)
    card.review_harness = result[1]
    card.review_events = []
    sessions.append(card)
    return result

def note(card, operation, **fields):
    if hasattr(card, 'review_harness'):
        h = card.review_harness
        card.review_events.append(dict(operation=operation,
                                      executed_instructions=sum(h.b.visits.values()),
                                      psw=h.b.core.psw))
    return original_note(card, operation, **fields)

module.boot = boot
module.Card.note = note
module.main()
scope.save(HERE / ('host-counts-%s-%s.json' % tuple(sys.argv[1:3])), dict(
    events=[card.review_events for card in sessions],
    definition='Sum of executed decoded instruction rows; native card, locks and time are modeled.',
    limits='Instruction count is not cycles, milliseconds or an RTOS timing bound.'))
