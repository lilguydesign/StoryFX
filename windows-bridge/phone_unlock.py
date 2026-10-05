"""One bounded PIN attempt on already trusted phones; secrets stay off Appium."""
import hashlib
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

from secure_state import read

def marker_for(root, serial):
    digest = hashlib.sha256(serial.encode()).hexdigest()
    return Path(root) / '.runtime/windows-bridge' / ('unlock-attempt-' + digest)


def load_pin(root, profile, serial):
    state = read(Path(root) / '.runtime/windows-bridge/phone-unlock.dpapi')
    if state.get('schema') != 1 or state.get('phones', {}).get(profile) != serial:
        raise RuntimeError('PHONE_UNLOCK_SCOPE_REFUSED')
    pin = state.get('pin')
    if not isinstance(pin, str) or not re.fullmatch(r'\d{4,16}', pin, flags=re.ASCII):
        raise RuntimeError('PHONE_UNLOCK_SECRET_INVALID')
    return pin


def pin_keyguard(source):
    # Only the numeric System UI lock screen. Never type into an app/password form.
    nodes = list(ET.fromstring(source).iter('node'))
    entry = any(n.get('resource-id') == 'com.android.systemui:id/pinEntry'
                and n.get('package') == 'com.android.systemui' for n in nodes)
    keypad = {n.get('text') for n in nodes if n.get('package') == 'com.android.systemui'
              and n.get('resource-id', '').startswith('com.android.systemui:id/key')}
    return entry and set('0123456789') <= keypad


def unlock(root, adb, serial, profile, driver, authorize, pause=time.sleep, hardware=None):
    hardware = hardware or serial
    marker = marker_for(root, hardware)
    try:
        if not driver.is_locked():
            marker.unlink(missing_ok=True)
            return True
        authorize()
        driver.press_keycode(224)
        size = driver.get_window_size()
        driver.swipe(size['width'] // 2, int(size['height'] * .85),
                     size['width'] // 2, int(size['height'] * .25), 700)
        pause(1)
        if not driver.is_locked():
            marker.unlink(missing_ok=True)
            return True
        if marker.exists() or not pin_keyguard(driver.page_source):
            return False
        pin = load_pin(root, profile, hardware)
        authorize()
        if not driver.is_locked() or not pin_keyguard(driver.page_source):
            return False
        marker.parent.mkdir(parents=True, exist_ok=True)
        with marker.open('x', encoding='ascii') as handle:
            handle.write('A previous locked-screen attempt requires review.\n')
        # stdin only: no PIN in argv, Appium capabilities, files, or diagnostics.
        locked_guard = ("dumpsys window policy | grep -Eq "
                        "'(^|[[:space:]])showing=true([[:space:]]|$)' || exit 17\n")
        commands = ''.join(locked_guard + 'input keyevent ' + str(7 + int(digit)) + '\n'
                           for digit in pin)
        commands += locked_guard + 'input keyevent 66\nexit\n'
        pin = None
        result = subprocess.run([str(adb), '-s', serial, 'shell', '-T'],
                                input=commands, text=True, capture_output=True, timeout=20)
        commands = None
        if result.returncode:
            return False
        pause(2)
        if driver.is_locked():
            return False  # Persistent marker prevents repeated wrong PIN attempts.
        marker.unlink(missing_ok=True)
        return True
    except Exception:
        return False  # Never include secret-bearing exception text in logs.
