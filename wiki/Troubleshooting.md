# Troubleshooting

This guide helps resolve common issues with Floppy Workbench.

## Table of Contents

- [Connection Problems](#connection-problems)
- [Read/Write Errors](#readwrite-errors)
- [Application Issues](#application-issues)
- [Performance Problems](#performance-problems)
- [Hardware Issues](#hardware-issues)
- [Getting Help](#getting-help)

---

## Connection Problems

### "No Greaseweazle Found"

**Symptoms:**
- Connect button shows error
- Device not appearing

**Solutions:**

1. **Check physical connection**
   - Verify USB cable is securely connected
   - Try a different USB port
   - Try a different USB cable (data-capable)

2. **Check device status**
   - Greaseweazle LED should be lit
   - If no LED, check USB power

3. **Windows-specific:**
   ```
   - Open Device Manager
   - Look for "Greaseweazle" or "Unknown device"
   - If unknown, install driver with Zadig
   ```

4. **Linux-specific:**
   ```bash
   # Check if device is detected
   lsusb | grep -i greaseweazle

   # Check permissions
   ls -la /dev/bus/usb/*/*

   # Add user to plugdev group
   sudo usermod -a -G plugdev $USER
   # Then log out and back in
   ```

5. **Try command line test:**
   ```bash
   gw info
   ```

### "Device Busy"

**Symptoms:**
- Connection fails with "busy" error

**Solutions:**

1. Close other applications that might use the device
2. Unplug and replug Greaseweazle
3. Restart Floppy Workbench
4. Check for background processes

### "Connection Lost During Operation"

**Symptoms:**
- Operation fails mid-way
- Device disconnects

**Solutions:**

1. Check for loose USB connection
2. Avoid USB hubs - connect directly
3. Check USB power (try powered hub)
4. Shorter USB cable may help

---

## Read/Write Errors

### "No Disk Detected"

**Symptoms:**
- Disk present but not recognized
- No index pulse detected

**Solutions:**

1. **Check disk insertion**
   - Ensure disk is fully seated
   - Try removing and reinserting

2. **Check drive connection**
   - Verify 34-pin cable is connected
   - Check cable orientation (pin 1)

3. **Check drive power**
   - Motor should spin when activated
   - Some drives need external 12V

4. **Try different disk**
   - Test with known-good disk
   - Check for damaged shutter

### "All Sectors Bad"

**Symptoms:**
- Every sector shows CRC error
- Complete read failure

**Solutions:**

1. **Verify disk type setting**
   - HD disk selected for HD disk?
   - DD disk selected for DD disk?

2. **Check disk media**
   - Visible damage?
   - Mold or contamination?

3. **Clean drive heads**
   - Use cleaning disk
   - Or manual cleaning

4. **Try different drive**
   - Alignment may differ between drives

5. **Check for write protection**
   - Shouldn't affect reads, but verify

### "Scattered Bad Sectors"

**Symptoms:**
- Random sectors fail
- Pattern varies between scans

**Solutions:**

1. **Multiple scans**
   - Run 2-3 scans and compare
   - Consistent failures = media damage

2. **Thorough scan mode**
   - Use multi-read verification
   - May recover marginal sectors

3. **Recovery mode**
   - Try Standard recovery
   - Progress to Aggressive if needed

4. **Check drive speed**
   - Run RPM diagnostics
   - Unstable speed causes read errors

### "Write Fails / Verify Errors"

**Symptoms:**
- Format fails
- Write doesn't verify

**Solutions:**

1. **Check write protection**
   - 3.5": Close the hole (slide tab)
   - 5.25": Cover the notch

2. **Check disk condition**
   - Old disks may not reliably write
   - Try new/different disk

3. **Check drive**
   - Write heads may be dirty
   - Drive may be read-only (worn heads)

4. **Reduce write speed**
   - Some drives are sensitive

---

## Application Issues

### Application Won't Start

**Symptoms:**
- Crashes on launch
- Window doesn't appear

**Solutions:**

1. **Check Python version**
   ```bash
   python --version
   # Must be 3.10 or higher
   ```

2. **Reinstall dependencies**
   ```bash
   pip uninstall floppy-workbench
   pip install floppy-workbench
   ```

3. **Check for conflicts**
   ```bash
   pip list | grep -i pyqt
   # Remove conflicting versions
   ```

4. **Run from command line for errors**
   ```bash
   python -m floppy_formatter
   # Check error messages
   ```

### UI Display Problems

**Symptoms:**
- Blank areas
- Garbled graphics
- Missing elements

**Solutions:**

1. **Update graphics drivers**

2. **Try different theme**
   - Switch between dark/light

3. **Linux: Install display libraries**
   ```bash
   sudo apt install libxcb-xinerama0 libxcb-cursor0
   ```

4. **Reset settings**
   - Delete settings file and restart

### Crashes During Operation

**Symptoms:**
- Application closes unexpectedly
- Freeze during scan/format

**Solutions:**

1. **Check log file**
   - Location shown in settings
   - Look for error messages

2. **Update to latest version**
   ```bash
   pip install --upgrade floppy-workbench
   ```

3. **Reduce operations**
   - Try Quick scan instead of Thorough
   - Fewer revolutions in flux capture

4. **Check memory**
   - Close other applications
   - Monitor RAM usage

---

## Performance Problems

### Slow Scanning

**Symptoms:**
- Scans take much longer than expected
- Progress stalls

**Solutions:**

1. **Check scan mode**
   - Quick: ~15 seconds
   - Standard: ~45 seconds
   - Thorough: ~2-5 minutes

2. **Reduce retries**
   - Lower retry count in settings

3. **Check disk condition**
   - Bad sectors cause retries
   - Heavily damaged disk = slower

4. **Check USB bandwidth**
   - Don't use with other USB devices
   - Avoid USB 1.1 hubs

### High Memory Usage

**Symptoms:**
- Application uses excessive RAM
- System slows down

**Solutions:**

1. **Reduce flux captures**
   - Lower revolution count
   - Disable "Store Raw Flux"

2. **Close unused features**
   - Close flux viewer when not needed

3. **Clear cached data**
   - Export and close disk
   - Restart application

### Interface Lag

**Symptoms:**
- Slow UI response
- Delayed updates

**Solutions:**

1. **Disable animations**
   - Settings → Display → Animate Operations: Off

2. **Reduce sector map updates**
   - During intensive operations

3. **Check system resources**
   - Close other applications

---

## Hardware Issues

### Drive Motor Issues

**Symptoms:**
- Motor doesn't spin
- Irregular spinning
- Wrong speed

**Solutions:**

| Problem | Solution |
|---------|----------|
| No spin | Check power connection |
| Slow start | May be normal, wait longer |
| Wrong RPM | Belt issue or motor problem |
| Noise | Bearing wear, needs replacement |

### Head Seek Problems

**Symptoms:**
- Clicking sounds
- Can't reach all tracks
- Seek errors

**Solutions:**

1. **Recalibrate**
   - Seek to track 0
   - Some drives need this after power-on

2. **Check for obstructions**
   - Dust or debris on rails
   - Clean with compressed air

3. **Lubrication**
   - Very rarely needed
   - Use proper lubricant if required

### Cable Issues

**Symptoms:**
- Intermittent connection
- Specific tracks fail
- Random errors

**Solutions:**

1. **Check cable seating**
   - Remove and reinsert
   - Ensure proper alignment

2. **Inspect cable**
   - Look for damage
   - Check for bent pins

3. **Try different cable**
   - Cables do wear out

---

## Getting Help

### Collect Information

Before seeking help, gather:

1. **Version information**
   ```bash
   floppy-workbench --version
   python --version
   ```

2. **Error messages**
   - Screenshots
   - Log file contents

3. **System information**
   - Operating system
   - Hardware details

4. **Steps to reproduce**
   - What you were doing
   - What happened

### Log Files

Find log files at:

| Platform | Location |
|----------|----------|
| Windows | `%APPDATA%\FloppyWorkbench\logs\` |
| Linux | `~/.config/floppy-workbench/logs/` |
| macOS | `~/Library/Logs/FloppyWorkbench/` |

### Support Channels

1. **GitHub Issues**
   - [Report a bug](https://github.com/JYewman/Floppy-Disk-Restorer/issues)
   - Search existing issues first

2. **Documentation**
   - Check this wiki thoroughly
   - Review README

3. **Community Forums**
   - Vintage computing forums
   - Greaseweazle community

---

## Quick Troubleshooting Checklist

```
□ USB connection secure?
□ Greaseweazle LED on?
□ Floppy cable connected correctly?
□ Drive powered (if needed)?
□ Correct disk type selected?
□ Disk not write-protected (for writes)?
□ Drive heads clean?
□ Different disk tried?
□ Different drive tried?
□ Latest software version?
□ Log files checked?
```

---

**Next:** [[Technical Reference]] - Detailed technical information
