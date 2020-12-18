
# Window placement manager for Windows

Small Python script that will save and restore window placements between WM_DISPLAYCHANGE events. It will also force new windows to be created on the display where the cursor is located.

## Requirements

- Python >3.8 (I have only tested it on 3.8)
- PyWin32
- black (only required to autoformat code)

## TODO

- [ ] Fancy systray integration
- [ ] `argparse` for configuring settings
- [ ] Investigate resizing windows when moving them to active display
- [ ] Investigate maximizing windows if they are larger than display
- [ ] Investigate transferring placement settings across displays
- [ ] Per-window settings
