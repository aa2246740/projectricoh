/* Image tables. Runtime never writes these pointer slots.
 * labels[i] = 0x2005276C + 96*i
 * table[i]  = 0x20052D6C + 4*i
 */
    .section .probe_glyphs,"a",@progbits
    .global probe_glyphs
probe_glyphs:
    .space 16 * 96, 0
    .size probe_glyphs, . - probe_glyphs

    .section .probe_labels,"a",@progbits
    .global probe_labels
probe_labels:
    .long 0x2005276c + 0 * 96
    .long 0x2005276c + 1 * 96
    .long 0x2005276c + 2 * 96
    .long 0x2005276c + 3 * 96
    .long 0x2005276c + 4 * 96
    .long 0x2005276c + 5 * 96
    .long 0x2005276c + 6 * 96
    .long 0x2005276c + 7 * 96
    .long 0x2005276c + 8 * 96
    .long 0x2005276c + 9 * 96
    .long 0x2005276c + 10 * 96
    .long 0x2005276c + 11 * 96
    .long 0x2005276c + 12 * 96
    .long 0x2005276c + 13 * 96
    .long 0x2005276c + 14 * 96
    .long 0x2005276c + 15 * 96
    .size probe_labels, . - probe_labels

    .section .probe_table,"a",@progbits
    .global probe_table
probe_table:
    .long 0x20052d6c + 0 * 4
    .long 0x20052d6c + 1 * 4
    .long 0x20052d6c + 2 * 4
    .long 0x20052d6c + 3 * 4
    .long 0x20052d6c + 4 * 4
    .long 0x20052d6c + 5 * 4
    .long 0x20052d6c + 6 * 4
    .long 0x20052d6c + 7 * 4
    .long 0x20052d6c + 8 * 4
    .long 0x20052d6c + 9 * 4
    .long 0x20052d6c + 10 * 4
    .long 0x20052d6c + 11 * 4
    .long 0x20052d6c + 12 * 4
    .long 0x20052d6c + 13 * 4
    .long 0x20052d6c + 14 * 4
    .long 0x20052d6c + 15 * 4
    .size probe_table, . - probe_table

    .section .probe_no_details,"a",@progbits
    .global probe_no_details
probe_no_details:
    .space 16 * 12, 0
    .size probe_no_details, . - probe_no_details
