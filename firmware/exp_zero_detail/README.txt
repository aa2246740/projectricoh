OFFICIAL RICOH GXR 1.51 DIAGNOSTIC IMAGE - MENU-DETAIL ZEROED
==============================================================

This is the genuine official Ricoh GXR 1.51 firmware with ONLY a 84-byte
menu-detail data region (7 stock menu-detail rows at file offset 0x1F4F38)
zeroed in the body file ilaunch3, and the header checksum recomputed.

PURPOSE: Diagnostic probe to test whether the 50mm boot-hang condition
(green LED blink, black LCD) is caused by those detail rows or other
factors in the base firmware.

STAGED ilaunch3 SHA256:
1c177c1ccefebd9d1385ba7baec4ee1dbb988ce9e11efd1a97240e76097630a3

RECOVERY: Card A (Stage2l) with the 50mm lens attached. Flash via
"+ & playback" at power-on. After power-off and reset, the 50mm will
boot with the baseline official firmware (no menu details loaded).
