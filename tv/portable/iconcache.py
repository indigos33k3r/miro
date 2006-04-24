import item
import os
import threading
from download_utils import grabURL
from fasttypes import LinkedList
import config
import time

class IconCacheUpdater:
    def __init__ (self):
        self.idle = LinkedList()
        self.vital = LinkedList()
        self.cond = threading.Condition()

        for i in xrange(3):
            thread = threading.Thread(target=self.consumer_thread,\
                                      name="Icon Cache Updater %d" % (i + 1,))
            thread.setDaemon(True)
            thread.start()

    def requestUpdate (self, item, is_vital = False):
        self.cond.acquire()
        item.dbItem.beginRead()
        try:
            if (item.filename):
                is_vital = False
        finally:
            item.dbItem.endRead()
        if (is_vital):
            self.vital.prepend(item)
        else:
            self.idle.prepend(item)
        self.cond.notify()
        self.cond.release()

    def consumer_thread (self):
        while (True):
            is_vital = False
            self.cond.acquire()
            while (len(self.vital) == 0 and len(self.idle) == 0):
                self.cond.wait()
            if (len(self.vital) > 0):
                item = self.vital.pop()
                is_vital = True
            else:
                item = self.idle.pop()
            self.cond.release()
            item.updateIconCache()
            if (not is_vital):
                time.sleep(0.001)

    def clearVital (self):
        self.cond.acquire()
        self.vital = LinkedList()
        self.cond.release()

iconCacheUpdater = IconCacheUpdater()
icon_cache_filename_lock = threading.Lock()
icon_cache_updating_cond = threading.Condition()
class IconCache:
    def __init__ (self, dbItem, is_vital = False):
        self.etag = None
        self.modified = None
        self.filename = None
        self.url = None

        self.updated = False
        self.updating = False
        self.dbItem = dbItem

        self.requestUpdate (is_vital=is_vital)

    ##
    # Finds a filename that's unused and similar the the file we want
    # to download
    def nextFreeFilename(self, name):
        if not os.access(name,os.F_OK):
            return name
        parts = name.split('.')
        count = 1
        if len(parts) == 1:
            newname = "%s.%s" % (name, count)
            while os.access(newname,os.F_OK):
                count += 1
                newname = "%s.%s" % (name, count)
        else:
            parts[-1:-1] = [str(count)]
            newname = '.'.join(parts)
            while os.access(newname,os.F_OK):
                count += 1
                parts[-2] = str(count)
                newname = '.'.join(parts)
        return newname

    def updateIconCache (self):
        try:
            icon_cache_updating_cond.acquire()
            try:
                self.dbItem.beginRead()
                try:
                    updating = self.updating
                finally:
                    self.dbItem.endRead()
    
                while (updating):
                    icon_cache_updating_cond.wait()
                    self.dbItem.beginRead()
                    try:
                        updating = self.updating
                    finally:
                        self.dbItem.endRead()
                
                self.dbItem.beginRead()
                try:
                    filename = self.filename
                    etag = self.etag
                    modified = self.modified
                    updated = self.updated
                    old_url = self.url
                    url = self.dbItem.getThumbnailURL ()
                finally:
                    self.dbItem.endRead()
    
                # Only verify each icon once per run unless the url changes
                if (updated and url == old_url):
                    return
    
                self.dbItem.beginRead()
                try:
                    self.updating = True
                finally:
                    self.dbItem.endRead()
    
            finally:
                icon_cache_updating_cond.release()
    
            try:
                cachedir = os.path.join (config.get (config.SUPPORT_DIRECTORY), "icon-cache")
    
                try:
                    os.makedirs (cachedir)
                except:
                    pass
        
                # If we have sufficiently cached data, let the server know that.
                info = None
                try:
                    if (url == old_url and filename and os.access (filename, os.R_OK)):
                        info = grabURL (url, etag=etag, modified=modified)
                    else:
                        info = grabURL (url)
                except:
                    pass
        
                # Error during download, or no url.  To reflect that,
                # clear the cache if there was one before.
                if (info == None):
                    try:
                        if (filename):
                            os.remove (filename)
                    except:
                        pass
                    self.dbItem.beginChange()
                    try:
                        self.url = url
                        self.filename = None
                        self.etag = None
                        self.modified = None
                    finally:
                        self.dbItem.endChange()
                    return
            
                # Our cache is good.  Hooray!
                if (info['status'] == 304):
                    print "Cache good: %s!" % url
                    self.dbItem.beginRead()
                    try:
                        self.updated = True
                    finally:
                        self.dbItem.endRead()
                    return
            
                # We have to update it, and if we can't write to the file, we
                # should pick a new filename.
                if (filename and not os.access (filename, os.R_OK | os.W_OK)):
                    filename = None
    
                # Download to a temp file.
                if (filename):
                    tmp_filename = filename + ".part"
                else:
                    tmp_filename = os.path.join(cachedir, info["filename"]) + ".part"
            
                # Once we open the output file, we can release the filename
                # lock, since the file has been created.
                icon_cache_filename_lock.acquire()
                try:
                    tmp_filename = self.nextFreeFilename (tmp_filename)
                    output = file (tmp_filename, 'w')
                finally:
                    icon_cache_filename_lock.release()
            
                # Do the download without the icon_cache_filename_lock in case there are multiple threads downloading.
                input = info["file-handle"]
                data = input.read(1024)
                while (data and data != ""):
                    output.write(data)
                    data = input.read(1024)
                output.close()
                input.close()
            
                # We're moving the file into place here, so we have to
                # grab the icon_cache_filename_lock again.  We acquire the
                # lock no matter whether or not we're calling
                # nextFreeFilename, since we remove the file in the middle
                # (which we do because windows doesn't have atomic rename
                # over an existing file.)
                icon_cache_filename_lock.acquire()
                try:
                    if (filename == None):
                        filename = os.path.join(cachedir, info["filename"])
                        filename = self.nextFreeFilename (filename)
                    try:
                        os.remove (filename)
                    except:
                        pass
                    try:
                        os.rename (tmp_filename, filename)
                    except:
                        filename = None
                finally:
                    icon_cache_filename_lock.release()
        
                self.dbItem.beginChange()
                try:
                    self.filename = filename
                    if (info.has_key ("etag")):
                        self.etag = info["etag"]
                    else:
                        self.etag = None
                    if (info.has_key ("modified")):
                        self.modified = info["modified"]
                    else:
                        self.modified = None
                finally:
                    self.dbItem.endChange()
            finally:
                icon_cache_updating_cond.acquire()
                try:
                    self.dbItem.beginRead()
                    try:
                        self.updating = False
                    finally:
                        self.dbItem.endRead()
                finally:
                    icon_cache_updating_cond.notifyAll()
                    icon_cache_updating_cond.release()
        except:
            pass

    def requestUpdate (self, is_vital = False):
        if hasattr (self, "updating") and hasattr (self, "dbItem"):
            iconCacheUpdater.requestUpdate (self, is_vital = is_vital)

    def onRestore(self):
        self.updated = False
        self.updating = False
        self.requestUpdate ()
