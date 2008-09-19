# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""Defines the channel settings panel."""

import logging

from miro import config, prefs, messages
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import cellpack, imagepool, widgetutil, window
from miro.plat import resources
from miro.plat.frontends.widgets.widgetset import Rect
from miro.dialogs import BUTTON_DONE
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.frontends.widgets import separator
from miro.frontends.widgets import style
from miro.frontends.widgets.widgetutil import build_hbox
from miro.util import clampText, returnsUnicode

@returnsUnicode
def get_formatted_default_expiration():
    """Returns the 'system' expiration delay as a formatted string
    """
    expiration = float(config.get(prefs.EXPIRE_AFTER_X_DAYS))
    formatted_expiration = u''
    if expiration < 0:
        formatted_expiration = _('never')
    elif expiration < 1.0:
        hours = int(expiration * 24.0)
        formatted_expiration = ngettext("%(count)d hour",
                                        "%(count)d hours",
                                        hours,
                                        {"count": hours})
    elif expiration >= 1 and expiration < 30:
        days = int(expiration)
        formatted_expiration = ngettext("%(count)d day",
                                        "%(count)d days",
                                        days,
                                        {"count": days})
    elif expiration >= 30:
        months = int(expiration / 30)
        formatted_expiration = ngettext("%(count)d month",
                                        "%(count)d months",
                                        months,
                                        {"count": months})
    return formatted_expiration

def _build_header(channel):
    v = widgetset.VBox()
    lab = widgetset.Label(clampText(channel.name, 60))
    lab.set_bold(True)
    v.pack_start(widgetutil.align_left(lab))

    lab = widgetset.Label(clampText(channel.url, 80))
    v.pack_start(widgetutil.align_left(lab))

    v.pack_start(separator.HThinSeparator(style.TAB_LIST_SEPARATOR_COLOR), padding=5)

    return v

def _build_video_expires(channel):
    lab = widgetset.Label(_("Videos expire after"))
    expire_options = [
        ("system", _("Default (%(expiration)s)",
                     {"expiration": get_formatted_default_expiration()})),
        ("24", _("1 day")),
        ("72", _("3 days")),
        ("144", _("6 days")),
        ("240", _("10 days")),
        ("720", _("1 month")),
        ("never", _("never"))
    ]
    expire_values = [e[0] for e in expire_options]
    expire_combo = widgetset.OptionMenu([e[1] for e in expire_options])

    if channel.expire == "system":
        selected = expire_values.index("system")
    elif channel.expire == "never":
        selected = expire_values.index("never")
    else:
        try:
            selected = expire_values.index(str(channel.expire_time))
        except ValueError:
            selected = 0
    expire_combo.set_selected(selected)

    def expire_changed(widget, index):
        value = expire_options[index][0]

        if value == "system":
            expire_type = "system"
            expire_time = config.get(prefs.EXPIRE_AFTER_X_DAYS)
        elif value == "never":
            expire_type = "never"
            expire_time = 0
        else:
            expire_type = "feed"
            expire_time = int(value)

        messages.SetChannelExpire(channel, expire_type, expire_time).send_to_backend()
    expire_combo.connect('changed', expire_changed)

    return build_hbox((lab, expire_combo), padding=2)

def _build_auto_download(channel):
    auto_download_cbx = widgetset.Checkbox(_("Don't Auto Download when more than"))
    auto_download_entry = widgetset.TextEntry()
    auto_download_entry.set_width(5)
    lab = widgetset.Label(_("videos are waiting unwatched."))

    if channel.max_new == u"unlimited":
        auto_download_cbx.set_checked(False)
        auto_download_entry.set_text("3")
        auto_download_entry.disable_widget()
    else:
        auto_download_cbx.set_checked(True)
        auto_download_entry.set_text(str(channel.max_new))
        auto_download_entry.enable_widget()

    def textentry_changed(widget):
        try:
            v = int(widget.get_text().strip())
            if v <= 0:
                widget.set_text("0")
                v = 0

            messages.SetChannelMaxNew(channel, int(v)).send_to_backend()
        except ValueError, ve:
            pass

    def checkbox_changed(widget):
        if widget.get_checked():
            auto_download_entry.enable_widget()
            textentry_changed(auto_download_entry)
        else:
            auto_download_entry.disable_widget()
            messages.SetChannelMaxNew(channel, u"unlimited").send_to_backend()

    auto_download_entry.connect('changed', textentry_changed)
    auto_download_cbx.connect('toggled', checkbox_changed)

    return build_hbox((auto_download_cbx, auto_download_entry, lab), padding=2)

def _build_remember_items(channel):
    lab = widgetset.Label(_("Remember"))
    older_options = [
        ("-1", _("Default (%(number)s)",
                 {"number": config.get(prefs.MAX_OLD_ITEMS_DEFAULT)})),
        ("0", "0"),
        ("20", "20"),
        ("50", "50"),
        ("100", "100"),
        ("1000", "1000")
    ]
    older_values = [o[0] for o in older_options]
    older_combo = widgetset.OptionMenu([o[1] for o in older_options])
    lab2 = widgetset.Label(_("older items in this feed in addition to the current contents."))

    if channel.max_old_items == u"system":
        selected = older_values.index("-1")
    else:
        try:
            selected = older_values.index(str(channel.max_old_items))
        except ValueError:
            selected = 0
    older_combo.set_selected(selected)

    def older_changed(widget, index):
        value = older_options[index][0]

        if value == u"system":
            messages.SetChannelMaxOldItems(channel, -1).send_to_backend()
        else:
            messages.SetChannelMaxOldItems(channel, int(value)).send_to_backend()

    older_combo.connect('changed', older_changed)

    return build_hbox((lab, older_combo, lab2), padding=2)

def _build_clear_older_items_now(channel):
    button = widgetset.Button(_("Clear older items now"))
    lab = widgetset.Label("")

    def _handle_clicked(widget):
        messages.CleanChannel(channel.id).send_to_backend()
        # FIXME - we don't really know if it got cleaned or if it errored out
        # at this point.  but ...  we need to give some kind of feedback to
        # the user and it's not likely that it failed and if it did, it'd
        # be in the logs.
        lab.set_text(_("Old items have been removed."))
    button.connect('clicked', _handle_clicked)

    return build_hbox((button, lab), padding=2)

def run_dialog(channel):
    """Displays the channel settings panel dialog."""
    pref_window = widgetset.Dialog(_("Channel Settings"))
    try:
        try:
            v = widgetset.VBox(spacing=10)

            v.pack_start(_build_header(channel))
            v.pack_start(_build_video_expires(channel))
            v.pack_start(_build_remember_items(channel))
            v.pack_start(_build_auto_download(channel))
            v.pack_start(_build_clear_older_items_now(channel))

            pref_window.set_extra_widget(v)
            pref_window.add_button(BUTTON_DONE.text)
            pref_window.run()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("channel settings panel threw exception.")
    finally:
        pref_window.destroy()
