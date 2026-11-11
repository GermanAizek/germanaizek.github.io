.set noreorder
.set noat
.globl my_probe
.globl my_read
.text

my_probe:
    # Function prologue
    addiu   $sp, $sp, -32
    sw      $ra, 28($sp)
    sw      $s0, 24($sp)
    sw      $s1, 20($sp)
    move    $s0, $a0            # s0 = map

    # 1. Allocate 512 bytes for struct mtd_info
    li      $a0, 512
    jal     0x8008e5a0          # kmalloc
    nop

    beqz    $v0, .probe_fail
    nop

    move    $s1, $v0            # s1 = mtd

    # 2. Zero entire 512 bytes: memset(mtd, 0, 512)
    move    $a0, $s1
    move    $a1, $zero
    li      $a2, 512
    jal     0x800140c0          # memset
    nop

    # 3. Initialize fields in struct mtd_info:
    # mtd->type = 3 (MTD_NORFLASH)
    li      $t0, 3
    sb      $t0, 0($s1)

    # mtd->size = 0x00200000 (2MB flash)
    lui     $t0, 0x0020
    sw      $t0, 12($s1)

    # mtd->erasesize = 0x10000 (64KB sectors)
    lui     $t0, 0x0001
    sw      $t0, 16($s1)

    # mtd->writesize = 1
    li      $t0, 1
    sw      $t0, 20($s1)

    # mtd->name = map->name (0($s0))
    lw      $t0, 0($s0)
    sw      $t0, 48($s1)

    # mtd->priv = map
    sw      $s0, 56($s1)

    # mtd->read = my_read (at 0x801709c0)
    lui     $t0, 0x8017
    addiu   $t0, $t0, 0x09c0
    sw      $t0, 88($s1)

    move    $v0, $s1            # return mtd

.probe_fail:
    lw      $s1, 20($sp)
    lw      $s0, 24($sp)
    lw      $ra, 28($sp)
    addiu   $sp, $sp, 32
    jr      $ra
    nop

    # Pad with NOPs up to offset 0xa0 (address 0x801709c0)
    nop
    nop
    nop

my_read:
    # int (*read) (struct mtd_info *mtd, loff_t from, size_t len, size_t *retlen, u_char *buf);
    # a0 = mtd
    # a2 = from_hi
    # a3 = from_lo (flash byte offset)
    # 16(sp) = len
    # 20(sp) = retlen ptr
    # 24(sp) = buf ptr (destination in RAM)

    # 1. Update *retlen if not null
    lw      $t0, 16($sp)        # t0 = remaining_len
    lw      $t1, 20($sp)        # t1 = retlen ptr
    beqz    $t1, 1f
    nop
    sw      $t0, 0($t1)         # *retlen = len
1:
    # 2. Setup loop variables
    lw      $t1, 24($sp)        # t1 = dest buf (in RAM)
    move    $t2, $a3            # t2 = cur_addr (flash byte offset)
    lui     $t3, 0xfffe
    ori     $t3, $t3, 0x0c00    # t3 = 0xfffe0c00 (BCM63XX_SPI_BASE)

.read_loop:
    blez    $t0, .read_done
    nop

    # chunk = min(remaining_len, 60)
    li      $t4, 60
    sltu    $t5, $t0, $t4
    movn    $t4, $t0, $t5       # t4 = chunk

    # Set SPI_MSG_CTL (0x40): rx_len | 0x80
    ori     $t5, $t4, 0x80
    sb      $t5, 0x40($t3)

    # Write 4-byte command to SPI_MSG_DATA (0x41..0x44):
    # tx[0] = 0x03 (SPI READ command)
    li      $t5, 0x03
    sb      $t5, 0x41($t3)
    # tx[1] = (cur_addr >> 16) & 0xff
    srl     $t5, $t2, 16
    sb      $t5, 0x42($t3)
    # tx[2] = (cur_addr >> 8) & 0xff
    srl     $t5, $t2, 8
    sb      $t5, 0x43($t3)
    # tx[3] = cur_addr & 0xff
    sb      $t2, 0x44($t3)

    # Clear status register (0x02)
    li      $t5, 0x1f
    sb      $t5, 0x02($t3)

    # Start SPI transfer: SPI_CMD (0x00) = (4 << 8) | 0x03 = 0x0403
    li      $t5, 0x0403
    sh      $t5, 0x00($t3)

    # Poll SPI status register bit 0 for completion
.poll_spi:
    lbu     $t5, 0x02($t3)
    andi    $t5, $t5, 0x01
    beqz    $t5, .poll_spi
    nop

    # Clear status register (0x02)
    li      $t5, 0x1f
    sb      $t5, 0x02($t3)

    # Copy chunk bytes from SPI_RX_DATA (0x80) to RAM dest ($t1)
    move    $t6, $zero          # i = 0
.copy_rx:
    addu    $t7, $t3, $t6
    lbu     $t8, 0x80($t7)      # load byte from 0xfffe0c80 + i
    addu    $t7, $t1, $t6
    sb      $t8, 0($t7)         # store byte to dest + i
    addiu   $t6, $t6, 1
    bne     $t6, $t4, .copy_rx
    nop

    # Advance pointers and decrement remaining len
    addu    $t1, $t1, $t4       # dest += chunk
    addu    $t2, $t2, $t4       # cur_addr += chunk
    subu    $t0, $t0, $t4       # remaining_len -= chunk
    b       .read_loop
    nop

.read_done:
    move    $v0, $zero          # return 0 (success)
    jr      $ra
    nop
