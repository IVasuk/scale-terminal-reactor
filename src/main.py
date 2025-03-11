#!/usr/bin/env python3
import os

import gi
import threading
import time
import argparse

from peewee import JOIN

import src.sc_dbms as sc_dbms
from src.sc_dbms import ScScales

gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

CURRDIR = os.path.dirname(os.path.abspath(__file__))

LOCK = threading.Lock()


def set_label_value_background(self):
    pass
    #
    # if DATAMODEL.status == 2:
    #     css_str = """
    #         #label_time {
    #         background: #008000;
    #     }"""
    #
    #     if sc.has_class('black'):
    #         sc.remove_class('black')
    #
    #     if sc.has_class('red'):
    #         sc.remove_class('red')
    #
    #     sc.add_class('green')
    # elif DATAMODEL.status in (-3, -2, -1, 3):
    #     css_str = """
    #      #label_time {
    #          background: #FF0000;
    #      }"""
    #
    #     if sc.has_class('black'):
    #         sc.remove_class('black')
    #
    #     if sc.has_class('green'):
    #         sc.remove_class('green')
    #
    #     sc.add_class('green')
    # else:
    #     css_str = """
    #      #label_time {
    #          background: #000000;
    #      }"""
    #
    #     if sc.has_class('red'):
    #         sc.remove_class('red')
    #
    #     if sc.has_class('green'):
    #         sc.remove_class('green')
    #
    #     sc.add_class('black')
    #
    # css_provider = Gtk.CssProvider()
    # css_provider.load_from_data(bytes(css_str, 'utf-8'))
    #
    # sc.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)


class Handler:
    @staticmethod
    def on_destroy(window):
        Gtk.main_quit()

    @staticmethod
    def button_toggled(cur_btn, con_btn, scale_id, operation):
        if sc_dbms.sc_is_closed():
            cur_btn.set_active(False)
            con_btn.set_active(False)

            return True

        sc_scale = sc_dbms.ScScales.get_by_id(scale_id)

        if not (cur_btn.get_active()):
            con_btn.set_sensitive(True)
            sc_scale.operation = None
        else:
            con_btn.set_sensitive(False)
            sc_scale.operation = operation

        sc_scale.save()


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--host', required=False, type=str, default='localhost')
    parser.add_argument('-p', '--port', required=False, type=str, default='5432')
    parser.add_argument('-d', '--dbname', required=False, type=str, default='scaledb')
    parser.add_argument('-u', '--user', required=False, type=str, default='scale')
    parser.add_argument('-pas', '--password', required=False, type=str, default='scale')

    return parser


def update_labels(label_value, str_value, label_time, str_time):
    label_value.set_text(str_value)
    label_time.set_text(str_time)

    return False


def update_indicator(label_value, label_time, scale_id):
    while True:
        try:
            sc_dbms.sc_connect()

            while True:
                sc_scale = sc_dbms.ScScales.get_by_id(scale_id)

                GLib.idle_add(update_labels, label_value, str(sc_scale.basic_value), label_time,
                              str(sc_scale.last_seen.strftime('%d.%m.%Y\n%H:%M:%S')))

                time.sleep(1)
        except BaseException as ex:
            with LOCK:
                print(ex)
        finally:
            if not sc_dbms.sc_is_closed():
                #                print(f'{id}: closing dbms ...')
                sc_dbms.sc_close()
        #                print(f'{id}: closing dbms OK')

        time.sleep(1)


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

    #box_r1 {
        background: #000000;
    }

    #label_r1_name {
        color: #FFFFFF;
    }

    #label_r1_time {
        color: #FFFFFF;
    }

    #label_r1_value {
        color: #FFFFFF;
    }

    #box_r2 {
        background: #000000;
    }

    #label_r2_name {
        color: #FFFFFF;
    }

    #label_r2_time {
        color: #FFFFFF;
    }

    #label_r2_value {
        color: #FFFFFF;
    }
    
    #box_r3 {
        background: #000000;
    }

    #label_r3_name {
        color: #FFFFFF;
    }

    #label_r3_time {
        color: #FFFFFF;
    }

    #label_r3_value {
        color: #FFFFFF;
    }

    #box_r4 {
        background: #000000;
    }

    #label_r4_name {
        color: #FFFFFF;
    }

    #label_r4_time {
        color: #FFFFFF;
    }

    #label_r4_value {
        color: #FFFFFF;
    }
    """

    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(bytes(css_str, 'utf-8'))

    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(Gdk.Screen.get_default(), css_provider,
                                          Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    window = builder.get_object('window_main')
    window.connect('destroy', Handler.on_destroy)

    window.fullscreen()
    window.maximize()
    window.show_all()

    sc_dbms.sc_init_database(namespace.dbname, namespace.user, namespace.password, namespace.host, namespace.port)

    try:
        sc_dbms.sc_connect()

        threads = []

        i = 1

        for connection in sc_dbms.ScConnections.select().join(ScScales, JOIN.LEFT_OUTER).order_by(ScScales.name):
            scale = sc_dbms.ScScales.get_by_id(connection.scale.id)

            btn1 = builder.get_object(f'toggle_r{i}_in')
            btn2 = builder.get_object(f'toggle_r{i}_out')

            btn1.connect('toggled', Handler.button_toggled, btn2, scale.id, 'up')
            btn2.connect('toggled', Handler.button_toggled, btn1, scale.id, 'down')

            if scale.operation == 'up':
                btn1.set_active(True)
                btn2.set_active(False)
            elif scale.operation == 'down':
                btn1.set_active(False)
                btn2.set_active(True)
            else:
                btn1.set_active(False)
                btn2.set_active(False)

            builder.get_object(f'label_r{i}_name').set_text(scale.name)

            thr = threading.Thread(target=update_indicator, args=(
                builder.get_object(f'label_r{i}_value'), builder.get_object(f'label_r{i}_time'), scale.id), daemon=True)

            thr.start()

            threads.append(thr)

            i += 1

            if i == 5:
                break

        for n in range(5 - i):
            builder.get_object(f'box_r{4 - n}').destroy()

        Gtk.main()
    except BaseException as ex:
        print(f'service stopped: {ex}')
    finally:
        sc_dbms.sc_close()


if __name__ == '__main__':
    main()
