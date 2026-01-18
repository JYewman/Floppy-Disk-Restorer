# Hardware Requirements

This page covers all the hardware you need to use Floppy Workbench effectively.

## Table of Contents

- [Required Hardware](#required-hardware)
- [Greaseweazle Controller](#greaseweazle-controller)
- [Floppy Drives](#floppy-drives)
- [Cables and Connectors](#cables-and-connectors)
- [Power Supply](#power-supply)
- [Optional Hardware](#optional-hardware)
- [Where to Buy](#where-to-buy)

---

## Required Hardware

To use Floppy Workbench, you need:

| Component | Required | Notes |
|-----------|----------|-------|
| Greaseweazle V4/V4.1 | Yes | USB floppy controller |
| 3.5" Floppy Drive | Yes | PC-compatible, 34-pin |
| USB Cable | Yes | USB-A to Micro-B |
| Floppy Cable | Yes | 34-pin ribbon cable |
| Power Supply | Maybe | Some drives need external power |

---

## Greaseweazle Controller

### What is Greaseweazle?

Greaseweazle is an open-source USB floppy controller created by Keir Fraser. It reads and writes raw magnetic flux data, enabling:

- Reading any floppy format (PC, Amiga, Atari, Mac, etc.)
- Bit-perfect disk preservation
- Recovery of damaged disks
- Writing disk images to physical media

### Supported Models

| Model | Recommended | Notes |
|-------|-------------|-------|
| **Greaseweazle V4.1** | Yes | Latest version, best support |
| **Greaseweazle V4** | Yes | Fully supported |
| **Greaseweazle F7** | Yes | STM32F7 variant |
| **Greaseweazle F1** | Limited | Older version, basic support |

### Greaseweazle Specifications

- **USB**: Full-speed USB 1.1 (12 Mbps)
- **Sample Rate**: 72 MHz flux sampling
- **Supported Drives**: Up to 2 floppy drives
- **Power Output**: 5V for drive logic (not motor)

### Getting a Greaseweazle

**Official Sources:**
- [Greaseweazle GitHub](https://github.com/keirf/greaseweazle) - Build your own
- [Greaseweazle Wiki](https://github.com/keirf/greaseweazle/wiki) - Documentation

**Pre-built Units:**
- Various retro computing vendors sell assembled units
- eBay and Etsy often have assembled boards
- Some maker communities produce kits

---

## Floppy Drives

### Recommended Drive Types

#### 3.5" High Density (HD) Drives

Best for general use:

| Drive | Formats Supported | Notes |
|-------|-------------------|-------|
| **Sony MPF920** | HD/DD | Excellent, widely available |
| **Panasonic JU-257** | HD/DD | Very reliable |
| **TEAC FD-235HF** | HD/DD | Professional quality |
| **Alps DF354H** | HD/DD | Good performance |
| **NEC FD1231H** | HD/DD | Reliable |

**HD drives can read/write:**
- 1.44MB HD disks (18 sectors/track)
- 720KB DD disks (9 sectors/track)

#### 3.5" Double Density (DD) Drives

For reading only DD disks:

| Drive | Notes |
|-------|-------|
| **Sony MPF52A** | DD only |
| **Various OEM** | Check specifications |

**Important**: DD drives cannot read HD disks!

#### 5.25" Drives (Experimental)

| Drive | Formats | Notes |
|-------|---------|-------|
| **TEAC FD-55GFR** | HD/DD | 1.2MB/360KB |
| **Various OEM** | DD | 360KB only |

5.25" support is experimental and may require additional configuration.

### Drive Selection Tips

1. **Use PC drives** - Ensure the drive has a standard 34-pin PC interface
2. **Check jumper settings** - Most drives should be set to DS1 (Drive Select 1)
3. **Avoid laptop drives** - These often have non-standard interfaces
4. **Test before use** - Try a known-good disk first

### Drive Condition

For best results:
- Clean drive heads before use
- Avoid drives with excessive wear
- Listen for unusual sounds (clicking, grinding)
- Check for belt deterioration on older drives

---

## Cables and Connectors

### Floppy Ribbon Cable

**Requirements:**
- 34-pin IDC connector
- Standard PC floppy cable
- Length: 30-50cm recommended

**Connector Types:**

```
Pin 1 →  ■■■■■■■■■■■■■■■■■
         ■■■■■■■■■■■■■■■■■ ← Pin 34
```

**Important**: The cable has a twist between drive connectors. Connect your drive to the connector AFTER the twist (this makes it Drive A/DS0).

### USB Cable

- USB-A to Micro-B
- Data-capable (not charge-only)
- Length: 1-2m recommended

---

## Power Supply

### Does Your Drive Need External Power?

**Self-powered setups** (USB power sufficient):
- Some modern drives
- Low-power drives
- Greaseweazle V4.1 with power jumper set

**External power required**:
- Most vintage 3.5" drives
- All 5.25" drives
- Drives with separate motor power

### Power Connections

Most 3.5" drives use a 4-pin Berg connector:

```
┌─────────────────┐
│ +5V  GND GND +12V │
│  ●    ●   ●   ●  │
└─────────────────┘
  Red  Blk Blk Yel
```

**Voltage Requirements:**
| Voltage | Purpose |
|---------|---------|
| +5V | Drive logic, head positioning |
| +12V | Spindle motor |

**Note**: Some 3.5" drives only need +5V. Check your drive's specifications.

### Power Supply Options

1. **ATX Power Supply** - Use a PC PSU with Berg/Molex connectors
2. **Dedicated Floppy PSU** - Purpose-built power supplies
3. **USB Power** - Greaseweazle can power some drives via USB (limited current)
4. **Bench Power Supply** - For testing/development

### Greaseweazle Power Jumper

Greaseweazle V4.1 has a jumper to enable 5V power to the floppy drive through pin 3:

- **Jumper ON**: 5V supplied via floppy cable
- **Jumper OFF**: No power via floppy cable (use external PSU)

**Warning**: Only enable if your drive supports it and doesn't need 12V!

---

## Optional Hardware

### Cleaning Supplies

- **Isopropyl alcohol** (90%+) - For cleaning heads
- **Lint-free swabs** - For applying alcohol
- **Compressed air** - For dust removal
- **Head cleaning disk** - Commercial cleaning disk

### Testing Equipment

- **Known-good floppy disks** - For testing drives
- **Blank formatted disks** - For write testing
- **Multimeter** - For checking power supplies

### Multiple Drives

Greaseweazle supports up to 2 drives:
- Drive 0 (after cable twist)
- Drive 1 (before cable twist)

Useful for:
- Copying between drives
- Comparing different drive reads
- Testing drive alignment

---

## Where to Buy

### Greaseweazle

| Source | Type | Notes |
|--------|------|-------|
| eBay | Assembled | Search "Greaseweazle V4" |
| Etsy | Assembled/Kit | Various sellers |
| Retro computing forums | Various | Community members |
| DIY | PCB + parts | Use official design files |

### Floppy Drives

| Source | Type | Notes |
|--------|------|-------|
| eBay | Used | Test before buying |
| Retro computing stores | Refurbished | Often tested |
| Computer recyclers | Used | Check condition |
| Old computers | Salvage | Free if you have them |

### Cables and Power Supplies

| Component | Source |
|-----------|--------|
| Floppy cables | Amazon, eBay, electronics stores |
| USB cables | Any electronics retailer |
| ATX PSU | Computer stores, used |
| Berg connectors | Electronics suppliers |

---

## Hardware Setup Checklist

Before first use, verify:

- [ ] Greaseweazle connected via USB
- [ ] Greaseweazle LED illuminated
- [ ] Floppy drive connected via 34-pin cable
- [ ] Cable orientation correct (pin 1 aligned)
- [ ] Drive jumpered correctly (usually DS1)
- [ ] Power connected (if required)
- [ ] Drive motor spins when activated
- [ ] Test disk inserted and detected

---

**Next:** [[Software Requirements]] - Operating system and dependencies
