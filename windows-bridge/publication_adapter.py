"""Guarded legacy multi-image WhatsApp Business adapter, no retries or transport resets."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = 'http://127.0.0.1:4743/wd/hub'


def refused():
    return {'state': 'FAILED_BEFORE_PUBLICATION', 'evidence': 'preflight_refused'}


def sessions(endpoint):
    with urllib.request.urlopen(endpoint + '/sessions', timeout=5) as response:
        return json.load(response)['value']


def ensure_pilot_server():
    try:
        sessions(ENDPOINT)
        return
    except (OSError, urllib.error.URLError):
        pass
    entry = Path(os.environ['APPDATA']) / 'npm/node_modules/appium/index.js'
    node = shutil.which('node')
    if not node or not entry.is_file():
        raise RuntimeError('LOCAL_APPIUM_REQUIRED')
    process = subprocess.Popen([node, str(entry), '--address', '127.0.0.1', '--port', '4743',
                                '--base-path', '/wd/hub', '--log-level', 'error'],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    for _attempt in range(20):
        if process.poll() is not None:
            raise RuntimeError('PILOT_APPIUM_START_FAILED')
        time.sleep(1)
        try:
            sessions(ENDPOINT); return
        except (OSError, urllib.error.URLError):
            pass
    raise RuntimeError('PILOT_APPIUM_START_TIMEOUT')


def driver_for(serial):
    from appium import webdriver
    from appium.options.android import UiAutomator2Options
    # Refuse a competing controller on the historical endpoint. Never kill it.
    try:
        if sessions('http://127.0.0.1:4723/wd/hub'):
            raise RuntimeError('EXISTING_APPIUM_CONTROLLER_BUSY')
    except (OSError, urllib.error.URLError):
        pass
    ensure_pilot_server()
    current = sessions(ENDPOINT)
    if current:
        if len(current) != 1 or current[0]['capabilities'].get('udid', current[0]['capabilities'].get('appium:udid')) != serial:
            raise RuntimeError('PILOT_APPIUM_SESSION_REFUSED')
        # Borrow only the dedicated pilot endpoint; do not issue DELETE /session.
        options = UiAutomator2Options().load_capabilities({'platformName': 'Android', 'appium:automationName': 'UiAutomator2'})
        class BorrowedRemote(webdriver.Remote):
            def start_session(self, _capabilities):
                self.session_id = current[0]['id']; self.caps = current[0]['capabilities']
        return BorrowedRemote(ENDPOINT, options=options)
    options = UiAutomator2Options().load_capabilities({
        'platformName': 'Android', 'appium:automationName': 'UiAutomator2', 'appium:udid': serial,
        'appium:noReset': True, 'appium:autoGrantPermissions': False, 'appium:adbPort': 5037,
        'appium:newCommandTimeout': 900, 'appium:ignoreHiddenApiPolicyError': True,
        'appium:appPackage': 'com.sec.android.gallery3d',
        'appium:appActivity': 'com.sec.android.gallery3d.app.GalleryActivity',
    })
    return webdriver.Remote(ENDPOINT, options=options)


def execute(root, adb, payload, original, authorize=None):
    if payload['platform'] != 'WhatsApp' or payload['engine'] != 'multi' or not 1 <= payload['count'] <= 30:
        return refused()
    if payload.get('page') or payload.get('page_name'):
        return refused()
    if authorize is None or any(character in (payload['album2'] or payload['album']) for character in ('"', "'", '\n', '\r')):
        return refused()
    result = subprocess.run([str(adb), '-d', 'get-serialno'], capture_output=True, text=True, check=True, timeout=15)
    serial = result.stdout.strip()
    if serial not in {original.get('adb_serial'), original.get('device_id')}:
        return refused()
    driver = driver_for(serial)
    if driver.is_locked():
        return refused()
    sys.path.insert(0, str(root))
    from engine import core, engine_multi, platforms
    from appium.webdriver.common.appiumby import AppiumBy
    class Borrowed:
        def __getattr__(self, key): return getattr(driver, key)
        def quit(self): pass
    publication_clicked = False
    verified = False

    def unique(xpath):
        found = driver.find_elements(AppiumBy.XPATH, xpath)
        if len(found) != 1:
            raise RuntimeError('PROVIDER_ELEMENT_NOT_UNIQUE')
        return found[0]

    recent_xpath = "//*[@text='Just now' or @text='À l’instant' or @text=\"À l'instant\"]"
    # Establish that no pre-existing own status can be mistaken for this attempt.
    try:
        driver.activate_app('com.whatsapp.w4b')
        unique("//*[@text='Updates' or @text='Actus' or @text='Mises à jour']").click()
        unique("//*[@text='My status' or @text='Mon statut']").click()
        time.sleep(1)
        if driver.find_elements(AppiumBy.XPATH, recent_xpath):
            return refused()
        driver.activate_app('com.sec.android.gallery3d')
    except Exception:
        return refused()

    def business(_driver, _profile=None):
        count = payload['count']
        # Samsung's share sheet exposes the selected media count before the destination.
        unique(f"//*[contains(@text,'{count} image') or contains(@text,'{count} photo')]")
        unique("//*[contains(@text,'WhatsApp') and contains(@text,'Business')]").click()
        time.sleep(2)
        if driver.current_package != 'com.whatsapp.w4b':
            raise RuntimeError('PROVIDER_PACKAGE_REFUSED')

    def share(_driver):
        nonlocal publication_clicked, verified
        if driver.current_package != 'com.whatsapp.w4b':
            raise RuntimeError('PROVIDER_PACKAGE_REFUSED')
        unique("//*[@resource-id='com.whatsapp.w4b:id/contactpicker_row_name' and (@text='My status' or @text='Mon statut')]").click()
        time.sleep(1)
        unique("//*[@text='1 selected' or @text='1 sélectionné' or @text='1 sélectionnée']")
        unique("//*[@resource-id='com.whatsapp.w4b:id/send']").click()
        time.sleep(2)
        unique("//*[contains(@text,'Status (Contacts)') or contains(@text,'Statut (Contacts)')]")
        authorize()
        publication_clicked = True  # Reserve uncertainty before the final provider action.
        unique("//*[@resource-id='com.whatsapp.w4b:id/send']").click()
        time.sleep(8)
        unique("//*[@text='My status' or @text='Mon statut']").click()
        time.sleep(2)
        recent = driver.find_elements(AppiumBy.XPATH, recent_xpath)
        # A fresh baseline had no recent statuses; the final own-status list must
        # now contain exactly the number shared by the guarded gallery selection.
        verified = len(recent) == payload['count']

    profile = {**original, 'device_id': serial, 'profile_name': payload['device']}
    changes = [(module, 'log', lambda _value: None) for module in (core, engine_multi, platforms)]
    changes += [(core, 'debug_dump_thumbnails', lambda _driver: None),
                (engine_multi, 'debug_dump_thumbnails', lambda _driver: None),
                (engine_multi, 'make_driver', lambda *args, **kwargs: Borrowed()),
                (engine_multi, 'ensure_adb_connected', lambda value: value == serial),
                (engine_multi, 'choose_whatsapp_business_if_needed', business),
                (engine_multi, 'share_to_my_status', share)]
    originals = [(module, name, getattr(module, name)) for module, name, _value in changes]
    try:
        for module, name, value in changes: setattr(module, name, value)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            engine_multi.run(profile, payload['album2'] or payload['album'], payload['count'], 'WhatsApp')
    except Exception:
        pass
    finally:
        for module, name, value in originals: setattr(module, name, value)
    return ({'state': 'CONFIRMED', 'evidence': 'own_status_verified'} if verified else
            {'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain'} if publication_clicked else refused())
