"""Keyboard controls that don't map to menu items.  Right now this is just
arrow keys, but it should be pretty easy to extend.
"""

import app
import eventloop
import tabs

UP = 1
DOWN = 2
LEFT = 3
RIGHT = 4

@eventloop.asUrgent
def handleKey(key, shiftDown, controlDown):
    if app.controller.playbackController.currentItem is None:
        handleKeyNoPlayback(key, shiftDown, controlDown)
    else:
        handleKeyPlayback(key, shiftDown, controlDown)

def handleKeyNoPlayback(key, shiftDown, controlDown):
    if key not in (UP, DOWN):
        return
    if app.controller.selection.tabListActive:
        selectionArea = app.controller.selection.tabListSelection
        iterator = tabs.tabIterator()
        area = 'tablist'
    else:
        selectionArea = app.controller.selection.itemListSelection
        if selectionArea.currentView is None:
            return
        iterator = selectionArea.currentView
        area = 'itemlist'
    if key == UP:
        toSelect = selectionArea.firstBeforeSelection(iterator)
    else:
        toSelect = selectionArea.firstAfterSelection(iterator)
    if toSelect is not None:
        if app.controller.selection.tabListActive:
            itemView = tabs.getViewForTab(toSelect)
        else:
            itemView = selectionArea.currentView
        app.controller.selection.selectItem(area, itemView, toSelect.getID(),
                shiftDown, controlDown)

def handleKeyPlayback(key, shiftDown, controlDown):
    if key == RIGHT:
        if controlDown:
            app.controller.playbackController.skip(1)
        else:
            time = app.controller.videoDisplay.getCurrentTime()
            app.controller.videoDisplay.setCurrentTime(time + 1.5)
    elif key == LEFT:
        if controlDown:
            app.controller.playbackController.skip(-1)
        else:
            time = app.controller.videoDisplay.getCurrentTime()
            app.controller.videoDisplay.setCurrentTime(time - 0.5)
    elif key == UP:
        volume = app.controller.videoDisplay.getVolume()
        app.controller.videoDisplay.setVolume(volume + 0.05)
    elif key == DOWN:
        volume = app.controller.videoDisplay.getVolume()
        app.controller.videoDisplay.setVolume(volume - 0.05)
