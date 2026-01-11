# USB Floppy Formatter - Testing Guide

## ✅ Software Testing Status: COMPLETE

All software tests pass successfully without requiring physical hardware:

```
📊 TEST RESULTS
├─ Unit Tests: 77/77 PASSED ✓
├─ Integration Tests: 47/47 PASSED ✓
└─ Total: 124/124 PASSED ✓
```

## Running Software Tests

### Quick Test (All Tests)
```bash
python -m pytest tests/ -v
```

### Unit Tests Only
```bash
python -m pytest tests/unit/ -v
```

### Integration Tests Only
```bash
python -m pytest tests/integration/ -v
```

### With Coverage Report
```bash
python -m pytest tests/ --cov=floppy_formatter --cov-report=html
```

## 🔧 Hardware Testing

### Prerequisites

1. **Windows 11** (required for IOCTL support)
2. **Administrator privileges** (required for physical drive access)
3. **USB Floppy Drive** - TEAC USB UF000x or compatible
4. **Floppy Disk** - 1.44MB 3.5" floppy disk inserted in drive

### Running Hardware Compatibility Test

**Option 1: Using Batch File (Recommended)**
1. Insert floppy disk into USB drive
2. Right-click `run_hardware_test.bat`
3. Select "Run as Administrator"

**Option 2: Command Line**
```bash
# Open PowerShell or CMD as Administrator
python tests/hardware_compatibility_test.py
```

### Expected Hardware Test Output

If a USB floppy drive is connected and working:
```
✓ Found floppy drive at \\.\PhysicalDrive1
  Geometry: 80C/2H/18S
  Sector size: 512 bytes
  Capacity: 1440 KB
```

If no floppy drive is detected:
```
✗ No floppy drive found
  Make sure:
  - TEAC USB UF000x is connected
  - Floppy disk is inserted
  - Running as Administrator
```

## Current Status

### ✅ Completed (Software Testing)

- **Phase 9: Error Handling & Edge Cases** - All utilities implemented and tested
- **Phase 10: Compatibility Testing** - Complete test suite with 124 passing tests
- All code validated through comprehensive unit and integration tests
- Mock-based testing allows validation without physical hardware

### ⏳ Pending (Hardware Testing)

- Physical USB floppy drive access validation
- IOCTL compatibility with actual TEAC USB UF000x hardware
- Real-world sector read/write operations
- Format operation validation on physical media

## Troubleshooting

### Issue: "pywin32 is not installed"

If using `py` launcher, try using `python` instead:
```bash
python tests/hardware_compatibility_test.py
```

Or install pywin32 for the specific Python version:
```bash
python -m pip install pywin32
python -m pywin32_postinstall.pywin32_postinstall -install
```

### Issue: "NOT running as Administrator"

The hardware test requires admin privileges to access physical drives:
1. Right-click PowerShell or CMD
2. Select "Run as Administrator"
3. Run the test script again

### Issue: "No floppy drive found"

Verify:
1. USB floppy drive is connected and powered on
2. Floppy disk is inserted in the drive
3. Drive appears in Windows Device Manager
4. Drive letter is assigned (e.g., A: or B:)

Check Windows Device Manager:
- Open Device Manager
- Look under "Floppy disk drives" or "Disk drives"
- Verify TEAC USB device is listed and has no errors

## Test Coverage

### What's Tested (Without Hardware)

✅ **Geometry Calculations** - CHS addressing, sector mapping
✅ **Sector I/O Logic** - Read/write operations, error handling
✅ **Recovery Algorithms** - Convergence detection, fixed passes, pattern rotation
✅ **Format Workflows** - Track formatting, progress tracking, verification
✅ **Error Handling** - Windows error codes, device disconnection, retryable errors
✅ **Context Management** - Safe resource cleanup, power management
✅ **Partial Results** - Operation interruption, state saving

### What Requires Hardware

⏳ **Physical Drive Access** - Actual `\\.\PhysicalDrive#` enumeration
⏳ **IOCTL Support** - `IOCTL_DISK_FORMAT_TRACKS_EX` compatibility
⏳ **Real Sector I/O** - Physical read/write with actual media
⏳ **Format Operations** - Low-level track formatting on real floppy
⏳ **Bad Sector Recovery** - Testing with genuinely degraded media

## Next Steps

1. **Without USB Floppy Drive**: All software testing is complete! The application is ready for hardware validation when hardware becomes available.

2. **With USB Floppy Drive**:
   - Connect the drive and insert a floppy disk
   - Run `run_hardware_test.bat` as Administrator
   - Verify all 4 hardware tests pass
   - Proceed to full application testing

## Test Files Reference

```
tests/
├── unit/                          # Unit tests (77 tests)
│   ├── test_geometry.py          # Disk geometry & CHS (18 tests)
│   ├── test_sector_io.py         # Sector I/O operations (29 tests)
│   └── test_recovery.py          # Recovery algorithms (30 tests)
│
├── integration/                   # Integration tests (47 tests)
│   ├── test_format_flow.py       # Format workflows (19 tests)
│   └── test_recovery_flow.py     # Recovery workflows (28 tests)
│
├── fixtures/                      # Test fixtures
│   ├── __init__.py               # Fixture exports
│   └── mock_devices.py           # Mock floppy drive (382 lines)
│
└── hardware_compatibility_test.py # Standalone hardware test (320 lines)
```

## Success Criteria

**Software Testing** ✅
- All 124 pytest tests pass
- No import errors
- No linter errors
- All modules load successfully

**Hardware Testing** ⏳ (Pending Hardware)
- Physical drive enumeration succeeds
- IOCTL operations supported
- Sector read/write operations work
- Format operations complete successfully
