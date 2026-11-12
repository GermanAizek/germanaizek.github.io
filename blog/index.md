---
layout: blog
title: Technical Research Blog - Herman Semenoff
---

# Technical Research & Engineering Blog

[← Back to Main Page](/)

Welcome to my technical research blog. Here I document deep-dive reverse engineering, kernel internals, embedded hardware hacking, and low-level architecture optimizations.

---

## Articles / Статьи / 文章

### 1. Porting OpenWrt to Broadcom BCM6338 with 8MB RAM (D-Link DSL-2500U D3) — Part 1
*Published: November 2026 | Tags: `MIPS`, `OpenWrt`, `Reverse Engineering`, `Kernel`, `Hardware SPI`, `BCM6338`*

A comprehensive technical post-mortem on resurrecting a locked-down legacy ADSL modem with only 8 MB SDRAM and 2 MB SPI Flash. How we bypassed vendor bootloader locks, debugged MIPS Data Bus Errors, wrote a custom hardware MMIO SPI driver in pure assembly, re-engineered the kernel's internal Ethernet PHY clocking, and conquered the 8MB RAM barrier.

- 📖 **[Read in English (Part 1)](openwrt-dsl2500u-part1-en.html)**
- 📖 **[Читать на русском (Часть 1)](openwrt-dsl2500u-part1-ru.html)**
- 📖 **[阅读中文版 (第1部分)](openwrt-dsl2500u-part1-zh.html)**

---
