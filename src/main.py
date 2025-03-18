#!/usr/bin/env python3
import datetime
import os
from time import sleep

import gi
import threading
import time
import argparse

from peewee import JOIN

import src.sc_dbms as sc_dbms

gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

CURRDIR = os.path.dirname(os.path.abspath(__file__))

LOCK = threading.Lock()


class Handler:
    @staticmethod
    def on_destroy(window):
        Gtk.main_quit()

    @staticmethod
    def button_toggled(cur_btn, con_btn, scale_id, operation):
        try:
            if sc_dbms.sc_is_closed():
                sc_dbms.sc_connect()

            sc_scale = sc_dbms.ScScales.get_by_id(scale_id)

            if not (cur_btn.get_active()):
                sc_scale.operation = None
            else:
                sc_scale.operation = operation

            sc_scale.save()
        except BaseException as ex:
            print(f"Can't set operation {scale_id}: {ex}")

            cur_btn.set_sensitive(False)
        else:
            con_btn.set_sensitive(not (cur_btn.get_active()))
        finally:
            sc_dbms.sc_close()


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--host', required=False, type=str, default='localhost')
    parser.add_argument('-p', '--port', required=False, type=str, default='5432')
    parser.add_argument('-d', '--dbname', required=False, type=str, default='scaledb')
    parser.add_argument('-u', '--user', required=False, type=str, default='scale')
    parser.add_argument('-pas', '--password', required=False, type=str, default='scale')

    return parser

def update_labels_colors(number,color):
    css_str = f"""
        #label_r{number}_name {{
            color: {color};
        }}

        #label_r{number}_time {{
            color: {color};
        }}

        #label_r{number}_date {{
            color: {color};
        }}

        #label_r{number}_value {{
            color: {color};
        }}
        """

    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(bytes(css_str, 'utf-8'))

    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(Gdk.Screen.get_default(), css_provider,
                                          Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    return False

def update_labels_datetime(label_date, str_date, label_time, str_time):
    label_date.set_text(str_date)
    label_time.set_text(str_time)

    return False


def update_label_value(label_value, str_value):
    label_value.set_text(str_value)

    return False


def update_label_time(label_time, time_str):
    label_time.set_text(time_str)

    return False

def update_status_box(color):
    css_str = f"""
        #status_box {{
            background: {color};
        }}
        """

    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(bytes(css_str, 'utf-8'))

    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(Gdk.Screen.get_default(), css_provider,
                                          Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    return False


def update_statusbar(label_time):
    connection_closed = True

    while True:
        try:
            sc_dbms.sc_connect()

            while True:
                time_stamp = sc_dbms.sc_current_timestamp()

                if time_stamp is None:
                    if not connection_closed:
                        connection_closed = True

                        GLib.idle_add(update_status_box, '#FF0000')

                    break
                else:
                    if connection_closed:
                        connection_closed = False

                        GLib.idle_add(update_status_box, '#000000')

                    GLib.idle_add(update_label_time, label_time, str(time_stamp.strftime('%H:%M:%S')))

                sleep(1)
        except BaseException as ex:
            if not connection_closed:
                connection_closed = True

                GLib.idle_add(update_status_box, '#FF0000')

                with LOCK:
                    print(f"Update status: {ex}")
        finally:
            sc_dbms.sc_close()

        sleep(1)

def set_indicator_status(status, number, btn1, btn2, label_value, label_date, label_time, operation=None):
    if status == 0:
        update_labels_colors(number, '#FFFFFF')

        label_value.set_visible(True)

        label_date.set_visible(False)
        label_time.set_visible(False)

        if operation == 'up':
            btn2.set_active(False)

            btn1.set_sensitive(True)

            if not btn1.get_active():
                btn1.set_active(True)
            else:
                btn2.set_sensitive(False)
        elif operation == 'down':
            btn1.set_active(False)

            btn2.set_sensitive(True)

            if not btn2.get_active():
                btn2.set_active(True)
            else:
                btn1.set_sensitive(False)
        else:
            btn1.set_active(False)
            btn2.set_active(False)

            btn1.set_sensitive(True)
            btn2.set_sensitive(True)
    else:
        update_labels_colors(number, '#FF0000')

        label_value.set_visible(True)

        label_date.set_visible(True)
        label_time.set_visible(True)

        btn1.set_sensitive(False)
        btn2.set_sensitive(False)


def update_indicator(number, btn1, btn2, label_value, label_date, label_time, scale_id):
    sc_scales = sc_dbms.ScScales

    scale_status = -1

    while True:
        try:
            sc_dbms.sc_connect()

            while True:
                sc_scale = sc_scales.get_by_id(scale_id)

                GLib.idle_add(update_labels_datetime,
                              label_date, str(sc_scale.last_seen.strftime('%d.%m.%Y')),
                              label_time, str(sc_scale.last_seen.strftime('%H:%M:%S')))

                if (datetime.datetime.now().astimezone() - sc_scale.last_seen).total_seconds() > 5:
                    if scale_status != 1:
                        scale_status = 1

                        GLib.idle_add(set_indicator_status, scale_status, number, btn1, btn2, label_value, label_date,
                                      label_time)
                else:
                    if scale_status != 0:
                        scale_status = 0

                        GLib.idle_add(set_indicator_status, scale_status, number, btn1, btn2, label_value, label_date,
                                      label_time, sc_scale.operation)

                GLib.idle_add(update_label_value, label_value, str(sc_scale.basic_value))

                sleep(1)
        except BaseException as ex:
            if scale_status != -1:
                scale_status = -1

                GLib.idle_add(set_indicator_status, scale_status, number, btn1, btn2, label_value, label_date,
                              label_time)

                with LOCK:
                    print(f"Update {scale_id}: {ex}")
        finally:
            if not sc_dbms.sc_is_closed():
                sc_dbms.sc_close()

        sleep(1)


def main():
    parser = create_parser()
    namespace = parser.parse_args()

    builder = Gtk.Builder()
    builder.add_from_file(os.path.join(CURRDIR, 'ui', 'main-window.glade'))
    #    builder.connect_signals(Handler())

    css_str = """
    #toggle_in:checked{
        background: #00FF00;
    }    

    #toggle_in:disabled{
        background: #101010;
    }    

    #toggle_in{
        color: #000000;
        font-size: 32px;
    }    
    
    #toggle_out:checked{
        background: #0000FF;
    }    

    #toggle_out:disabled{
        background: #101010;
    }    

    #toggle_out{
        color: #000000;
        font-size: 32px;
    }    

    #status_box {
        background: #000000;
    }

    #box_r1 {
        background: #000000;
    }

    #box_r2 {
        background: #000000;
    }

    #box_r3 {
        background: #000000;
    }

    #box_r4 {
        background: #000000;
    }
    
    #label_time {
        color: #FFFFFF;
    }
    
    """

    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(bytes(css_str, 'utf-8'))

    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(Gdk.Screen.get_default(), css_provider,
                                          Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    sc_dbms.sc_init_database(namespace.dbname, namespace.user, namespace.password, namespace.host, namespace.port)

    try:
        sc_dbms.sc_connect()

        i = 1

        for connection in sc_dbms.ScConnections.select().join(sc_dbms.ScScales, JOIN.LEFT_OUTER).order_by(sc_dbms.ScScales.name):
            scale = sc_dbms.ScScales.get_by_id(connection.scale.id)

            btn1 = builder.get_object(f'toggle_r{i}_in')
            btn2 = builder.get_object(f'toggle_r{i}_out')

            btn1.connect('toggled', Handler.button_toggled, btn2, scale.id, 'up')
            btn2.connect('toggled', Handler.button_toggled, btn1, scale.id, 'down')

            builder.get_object(f'label_r{i}_name').set_text(scale.name)

            thr = threading.Thread(target=update_indicator, args=(i, btn1, btn2,
                builder.get_object(f'label_r{i}_value'), builder.get_object(f'label_r{i}_date'), builder.get_object(f'label_r{i}_time'), scale.id), daemon=True)

            thr.start()

            i += 1

            if i == 5:
                break

        sc_dbms.sc_close()

        for n in range(5 - i):
            builder.get_object(f'box_r{4 - n}').destroy()

        thr = threading.Thread(target=update_statusbar, args=(builder.get_object('label_time'),),daemon=True)
        thr.start()

        window = builder.get_object('window_main')
        window.connect('destroy', Handler.on_destroy)

        window.fullscreen()
        window.maximize()
        window.show_all()

        Gtk.main()
    except BaseException as ex:
        print(f'service stopped: {ex}')
    finally:
        sc_dbms.sc_close()


if __name__ == '__main__':
    main()
