"""Known Python model overrides must retain reference execution semantics."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE
enable();import bootstrap


def main():
    context=bootstrap.construct('fast','main','edge-guards-final1');m=context.machine
    from native_machine import NativeMachine
    import unit_link,sdcard
    driver=NativeMachine(m.cpu);assert driver.supported()
    class CustomLink(unit_link.UnitLink):pass
    m.devices['startup'].standby_model=CustomLink('50mm')
    assert not driver.supported()
    m.devices['startup'].standby_model=None
    original=sdcard.SdHost.present
    sdcard.SdHost.present=property(lambda _:False)
    assert not driver.supported()
    sdcard.SdHost.present=original
    assert driver.supported()
    assert m.cpu.run(1000).reason=='max_steps'
    result=dict(status='passed',checks=['unit-subclass-reference','SD-property-reference','default-native'],native=m.cpu._native_driver.stats())
    (HERE/'runs/edge-guards-final1.json').write_text(json.dumps(result,indent=2)+'\n')
    m.close();print(json.dumps(dict(status='passed',checks=3)))


if __name__=='__main__':main()
