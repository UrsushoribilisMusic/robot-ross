"""Single-key terminal input for calibration on Windows, macOS and Linux."""
import os
import sys
import time


def getch(timeout=None):
    if os.name == 'nt':
        import msvcrt
        if timeout is not None:
            deadline = time.monotonic() + timeout
            while not msvcrt.kbhit():
                if time.monotonic() >= deadline: return None
                time.sleep(.01)
        return msvcrt.getch()
    import termios
    import tty
    fd = sys.stdin.fileno()
    if not os.isatty(fd):
        raise RuntimeError('Calibration requires an interactive terminal.')
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        if timeout is not None:
            import select
            if not select.select([fd], [], [], timeout)[0]: return None
        value = os.read(fd, 1)
        if value == b'\x03':
            raise KeyboardInterrupt
        if not value:
            raise EOFError('Calibration terminal closed.')
        return value
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
