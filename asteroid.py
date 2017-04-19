
import argparse
import datetime
import itertools
import random
import struct
import time
import xml
import bleee
from gi.repository import GLib


class Asteroid:

    UUID_BATTERY = "00002a19-0000-1000-8000-00805f9b34fb"
    UUID_TIME = "00005001-0000-0000-0000-00a57e401d05"
    UUID_SCREENSHOT_REQ = "00006001-0000-0000-0000-00a57e401d05"
    UUID_SCREENSHOT_RESP = "00006002-0000-0000-0000-00a57e401d05"
    UUID_NOTIF_UPD = "00009001-0000-0000-0000-00a57e401d05"

    def __init__(self, address):
        self.ble = bleee.BLE()
        self.address = address
        self.dev = self.ble.device_by_address(self.address)
        # TODO: Manage this more properly
        self.dev.connect()

    def battery_level(self):
        return self.dev.char_by_uuid(Asteroid.UUID_BATTERY).read()[0]

    def update_time(self, to=None):
        if to is None:
            to = datetime.datetime.now()
        data = [
            to.year - 1900,
            to.month - 1,
            to.day,
            to.hour,
            to.minute,
            to.second
        ]
        self.dev.char_by_uuid(Asteroid.UUID_TIME).write(data)

    def screenshot(self):
        # TODO: This disconnects after a few callbacks, fix
        crsp = self.dev.char_by_uuid(Asteroid.UUID_SCREENSHOT_RESP)
        loop = GLib.MainLoop()
        data_rem = None
        def cb(*args):
            print(args)
            #loop.quit()
        crsp.start_notify()
        crsp.properties_changed.connect(cb)
        self.dev.char_by_uuid(Asteroid.UUID_SCREENSHOT_REQ).write(b"\x00")
        loop.run()

    def notify(self, summary, body=None, id_=None, package_name=None,
               app_name=None, app_icon=None):
        if id_ is None:
            id_ = random.randint(0, 2 ** 31)
        id_ = str(id_)
        xinsert = xml.etree.ElementTree.Element("insert")
        for vl, xn in ((summary, "su"),
                       (body, "bo"),
                       (id_, "id"),
                       (package_name, "pn"),
                       (app_name, "an"),
                       (app_icon, "ai")):
            if vl is not None:
                xel = xml.etree.ElementTree.SubElement(xinsert, xn)
                xel.text = vl
        data = xml.etree.ElementTree.tostring(xinsert)
        self.dev.char_by_uuid(Asteroid.UUID_NOTIF_UPD).write(data)
        return id_


class DBusEavesdropper:

    def __init__(self, bus, interface, member, callback):
        self.bus = bus
        self.interface = interface
        self.member = member
        self.callback = callback
        self._dbus_ctl = self.bus.get("org.freedesktop.DBus")
        # TODO: Escaping
        # TODO: We probably want to unregister when destroyed?
        self._match_id = self._dbus_ctl.AddMatch(
                            "interface=%s,member=%s,eavesdrop=true" %
                            (interface, member))
        self.bus.con.add_filter(self._filter_func)

    def _filter_func(self, con, msg, bl):
        if msg.get_interface() == self.interface and \
                msg.get_member() == self.member:
            self.callback(msg)