
__version__ = "1.0"

import logging
import collections

import win32.winxpgui as win32gui
import win32.win32api as win32api
import win32.timer as timer
import win32con
import time


kenny = logging.getLogger(__name__)

_window_state = collections.defaultdict(dict)
_handeling_display_change = False
_diplay_change_delay = 100
_create_only_on_cursor = True
_first_update = True


def display_change(hwnd, msg, wp, lp):
    kenny.debug("Received WM_DISPLAYCHANGE event")
    global _handeling_display_change
    _handeling_display_change = True

    def delayed_restore(timer_id, c_time):
        global _handeling_display_change
        global _first_update
        kenny.debug("Delayed restore triggered")
        restore_state()
        timer.kill_timer(timer_id)
        _handeling_display_change = False
        _first_update = True

    timer.set_timer(2000, delayed_restore)


def create_window_class(events):
    def destroy(hwnd, msg, wp, lp):
        kenny.info("Destroying window listener")
        win32gui.PostQuitMessage(0)

    windows_class_name = "WindHolds Class"
    wc = win32gui.WNDCLASS()
    wc.lpszClassName = windows_class_name
    hinst = wc.hInstance = win32gui.GetModuleHandle(None)
    wc.lpfnWndProc = {win32con.WM_DESTROY: destroy, **events}

    window_class = win32gui.RegisterClass(wc)

    hwnd = win32gui.CreateWindow(
        window_class,
        windows_class_name,
        0,
        0,
        0,
        win32con.CW_USEDEFAULT,
        win32con.CW_USEDEFAULT,
        0,
        0,
        hinst,
        None,
    )
    win32gui.UpdateWindow(hwnd)

    return hwnd


def handle_ctrl_c(hwnd):
    def ctrl_handler(ctrl_type) -> bool:
        kenny.debug("Received ctrl events: %d", ctrl_type)
        if ctrl_type == win32con.CTRL_C_EVENT:
            win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return False

    win32api.SetConsoleCtrlHandler(ctrl_handler, True)


def get_display_info():
    return (win32api.GetMonitorInfo(hdsp) for hdsp, *_ in win32api.EnumDisplayMonitors())


def get_display_key():
    return tuple(info["Monitor"] for info in get_display_info())


def save_state():
    states = {}
    active_windows = set()

    def wins(hwnd, lParam) -> bool:
        active_windows.add(hwnd)

        if win32gui.IsWindowVisible(hwnd) == 0:
            return not _handeling_display_change

        states[hwnd] = win32gui.GetWindowPlacement(hwnd)

        return not _handeling_display_change

    win32gui.EnumWindows(wins, None)

    if _handeling_display_change:
        return

    removed = 0
    key = get_display_key()
    old_states = _window_state[key]
    for hwnd in list(old_states.keys()):
        if hwnd not in active_windows:
            removed += 1
            del old_states[hwnd]

    if removed > 0:
        kenny.info("Removed %d windows", removed)

    if _create_only_on_cursor and not _first_update and len(key) > 1:
        new_windows = {}
        for hwnd, state in states.items():
            if hwnd not in old_states:
                new_windows[hwnd] = state
        if len(new_windows) > 0:
            move_windows(new_windows)

    old_states.update(states)


def are_rect_intersecting(rect1, rect2):
    l1, t1, r1, b1 = rect1
    l2, t2, r2, b2 = rect2 if len(rect2) == 4 else (*rect2, *rect2)
    return not (l2 > r1 or r2 < l1 or t2 > b1 or b2 < t1)


def get_placement_ratio(rect, point):
    left, top, right, bottom = rect
    x, y = point
    return ((x - left) / (right - left), (y - top) / (bottom - top))


def get_new_placement(state, cur_monitor, active_monitor):
    """Place window on active_monitor keeping its original size"""
    # TODO: Conditionally shrink or grow window depending on
    # TODO: Make sure window fits in active_monitor :)

    rx, ry = get_placement_ratio(cur_monitor["Work"], state[-1][0:2])
    left, top, right, bottom = state[-1]
    a_left, a_top, a_right, a_bottom = active_monitor["Work"]
    n_left, n_top = a_left + round((a_right - a_left) * rx), a_top + round((a_bottom - a_top) * ry)
    new_rect = (n_left, n_top, n_left + (right - left), n_top + (bottom - top))
    # Reusing flags, showCmd, and ptMinPosition
    # Setting ptMaxPosition to work area of active_monitor
    # TODO: Conditionally maximize window if it is bigger than active_monitor's work area
    return (*state[0:3], active_monitor["Work"][0:2], new_rect)


def move_window(hwnd, state, monitors, active_monitor):
    cur_monitor = None
    for monitor in monitors:
        if are_rect_intersecting(monitor["Monitor"], state[-1]):
            if cur_monitor == None:
                cur_monitor = monitor
            else:
                kenny.info("Skipping window placed on more than one monitor")
                return

    if cur_monitor == None:
        kenny.warning("Unable to determin on which monitor window resides")
        return

    new_state = get_new_placement(state, cur_monitor, active_monitor)
    win32gui.SetWindowPlacement(hwnd, new_state)


def move_windows(windows: dict):
    cursor = win32api.GetCursorPos()
    # Since we will be iterating multiple times through monitors, we need to listify the generator
    monitors = list(get_display_info())
    active_monitor = None
    for monitor in monitors:
        if are_rect_intersecting(monitor["Monitor"], cursor):
            active_monitor = monitor
            break

    moved = 0
    for hwnd, state in windows.items():
        if not are_rect_intersecting(active_monitor["Monitor"], state[-1]):
            move_window(hwnd, state, monitors, active_monitor)
            moved += 1
        else:
            kenny.debug("Skipping, window already in active_monitor")

    if moved > 0:
        kenny.info("Moved %d windows to active_monitor", moved)


def restore_state():
    states = _window_state[get_display_key()]
    skipped_flags = 0
    skipped_same = 0
    updated = 0
    errors = 0

    def wins(hwnd, lParam):
        nonlocal skipped_flags
        nonlocal skipped_same
        nonlocal updated
        nonlocal errors
        if hwnd not in states or win32gui.IsWindowVisible(hwnd) == 0:
            return True

        new_state = win32gui.GetWindowPlacement(hwnd)
        old_state = states[hwnd]
        if any(n != o for n, o in zip(new_state[0:2], old_state[0:2])):
            kenny.debug("Window flags no longer match, skipping update")
            skipped_flags += 1
            return True

        if all(n == o for n, o in zip(new_state[2:], old_state[2:])):
            kenny.debug("Window still in the same location, no need to update")
            skipped_same += 1
            return True

        kenny.debug("Restoring window location")
        try:
            win32gui.SetWindowPlacement(hwnd, old_state)
            updated += 1
        except Exception as e:
            kenny.warning("Unable to restore windows location (%s)", old_state, exc_info=e)
            errors += 1
        return True

    win32gui.EnumWindows(wins, None)
    kenny.info(
        "Restored state, flags=%d same=%d updated=%d errors=%d",
        skipped_flags,
        skipped_same,
        updated,
        errors,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    hwnd = create_window_class({win32con.WM_DISPLAYCHANGE: display_change})

    handle_ctrl_c(hwnd)

    def timed_update(timer_id, c_time):
        global _first_update
        if _handeling_display_change:
            kenny.debug("Skipping, display change still in progress")
            return
        save_state()
        _first_update = False

    timer.set_timer(500, timed_update)

    win32gui.PumpMessages()
