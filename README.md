
# Window placement manager for Windows

Small Python script that will save and restore window placements between WM_DISPLAYCHANGE events. It will also force new windows to be created on the display where the cursor is located.

## Requirements
- Python >3.8 (I have only tested it on 3.8)
- PyWin32
- black (only required to autoformat code)

## TODO
- :white_large_square: Fancy systray integration
- :white_large_square: `argparse` for configuring settings
- :white_large_square: Investigate resizing windows when moving them to active display
- :white_large_square: Investigate maximizing windows if they are larger than display
- :white_large_square: Investigate transferring placement settings across displays
- :white_large_square: Per-window settings
