#! /usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#

import pygtk
pygtk.require('2.0')
import sys, gtk, gobject, cairo
import math

from twisted.internet.gtk2reactor import Gtk2Reactor
import kademlia.protocol
kademlia.protocol.reactor = Gtk2Reactor()
import kademlia.node

import kademlia.contact
import kademlia.msgtypes

import hashlib

class EntangledViewer(gtk.DrawingArea):
    def __init__(self, node, *args, **kwargs):
        gtk.DrawingArea.__init__(self, *args, **kwargs)
        self.node = node
        self.timeoutID = gobject.timeout_add(5000, self.timeout)
        self.comms = {}
        self.incomingComms = {}
        # poison the node with our GUI hooks
        self.node._protocol.__gui = self
        self.node._protocol.__realSendRPC = self.node._protocol.sendRPC
        self.node._protocol.sendRPC = self.__guiSendRPC
    
        self.node._protocol.__realDatagramReceived = self.node._protocol.datagramReceived
        self.node._protocol.datagramReceived = self.__guiDatagramReceived
        
    def __guiSendRPC(self, contact, method, args, rawResponse=False):
        #print 'sending'
        self.drawComms(contact.id, method)
        return self.node._protocol.__realSendRPC(contact, method, args, rawResponse)
    
    def __guiDatagramReceived(self, datagram, address):
        msgPrimitive = self.node._protocol._encoder.decode(datagram)
        message = self.node._protocol._translator.fromPrimitive(msgPrimitive)
        if isinstance(message, kademlia.msgtypes.ErrorMessage):
            msg = 'error'
        elif isinstance(message, kademlia.msgtypes.ResponseMessage):
            msg = 'response'
        else:
            msg = message.request
        self.drawIncomingComms(message.nodeID, msg)
        return self.node._protocol.__realDatagramReceived(datagram, address)
    
    # Draw in response to an expose-event
    __gsignals__ = { "expose-event": "override" }
    
    # Handle the expose-event by drawing
    def do_expose_event(self, event):
        # Create the cairo context
        cr = self.window.cairo_create()
        # Restrict Cairo to the exposed area; avoid extra work
        cr.rectangle(event.area.x, event.area.y,
                event.area.width, event.area.height)
        cr.clip()

        self.draw(cr, *self.window.get_size())
    
    def draw(self, cr, width, height):
        # draw a rectangle for the background            
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # a circle for the local node
        cr.set_source_rgb(1.0, 0.0, 0.0)
        radius = min(width/5, height/5)
        
        w = width/2
        h = height/2
        s = radius / 2.0 - 20
        radial = cairo.RadialGradient(w/2, h/2, s, w+w/2, h+h/2, s)
        radial.add_color_stop_rgb(0,  0.6, 0, 0.2)
        radial.add_color_stop_rgb(1,  0.1, 0.2, 0.9)
        
        cr.arc(w, h, s, 0, 2 * math.pi)
        cr.set_source(radial)
        cr.fill()
        
        if len(self.comms):
            cr.set_line_width(5)
            cr.set_source_rgba(0, 0.7, 0.8, 0.5)
        else:
            cr.set_source_rgba(0.0, 0.0, 0.4, 0.7)
        cr.arc(w, h, s+1, 0, 2 * math.pi)
        
        cr.stroke()
        cr.set_line_width(2)
        
        blips = []
        kbucket = {}
        for i in range(len(self.node._routingTable._buckets)):
            for contact in self.node._routingTable._buckets[i]._contacts:    
                blips.append(contact)
                kbucket[contact.id] = i
        # ...and now circles for all the other nodes
        if len(blips) == 0:
            spacing = 180
        else:
            spacing = 360/(len(blips))
        degrees = 0
        radius = min(width/6, height/6) / 3 - 20
        if radius < 5:
            radius = 5
        r = width/2.5
        for blip in blips:
            x = r * math.cos(degrees * math.pi/180)
            y = r * math.sin(degrees * math.pi/180)    

            w = width/2 + x
            h = height/2 + y
            if w < 0:
                w = radius
            elif w > width:
                w = width-radius
            if h < 0:
                h = radius
            elif h > height:
                h = height - radius
                

            radial = cairo.RadialGradient(w-w/2, h-h/2, 5, w+w/2, h+h/2, 10)
            radial.add_color_stop_rgb(0,  0.4, 1, 0)
            radial.add_color_stop_rgb(1,  1, 0, 0)
            cr.arc(w, h, radius, 0, 2 * math.pi)
            cr.set_source(radial)
            cr.fill()
            
            cr.set_source_rgb(0.2,0.2,0.2)
            cr.set_font_size(12.0)
            cr.move_to(w+radius+5, h-10)
            cr.set_font_size(12.0)
            cr.show_text(blip.address)
            cr.move_to(w+radius+5, h+5)
            cr.show_text(str(blip.port))
            cr.set_source_rgb(1,1,1)
            
            cr.set_font_size(8.0)
            cr.set_source_rgb(0.4,0.4,0.4)
            cr.move_to(w+radius+5, h+17)
            cr.show_text('k-bucket: %d' % kbucket[blip.id])
            cr.set_font_size(14.0)
            cr.stroke()
            
            if blip.id in self.incomingComms:
                cr.set_source_rgba(0.8, 0.0, 0.0, 0.6) 
                cr.move_to(width/2, height/2)
                cr.line_to(w, h)
                cr.stroke()
                
                cr.move_to(width/2+x/3, height/2+y/3)
                cr.show_text(self.incomingComms[blip.id])
                cr.stroke()
                cr.set_line_width(5)
            
            else:
                cr.set_source_rgba(0.4, 0.0, 0.0, 0.7)
                
            cr.arc(w, h, radius+1, 0, 2 * math.pi)
            cr.stroke()
             
            if blip.id in self.comms:
                cr.set_line_width(5)
                cr.set_source_rgba(0.0, 0.7, 0.8, 0.4)
                cr.move_to(width/2, height/2)
                cr.line_to(w, h)
                cr.stroke()
                
                cr.set_source_rgba(0.0, 0.3, 0.8, 0.7)
                cr.move_to(width/2+x/1.2, height/2+y/1.2)
                cr.show_text(self.comms[blip.id])
                cr.stroke()
            cr.set_line_width(2)
            degrees += spacing
        
        cr.set_line_width(5)
        cr.set_source_rgba(0.6, 0.6, 0.6, 0.4)
        i = 0
        for lostComm in self.comms:
            if lostComm not in blips:
                cr.move_to(width/2, height/2)
                cr.line_to(100*i, 0)
                cr.stroke()
            i += 1
        
        

    def timeout(self):
        """ Timeout handler to update the GUI """
        #print 'timeout'
        self.window.invalidate_rect(self.allocation, False)
        return True
    
    def drawComms(self, contactID, msg):
        if contactID not in self.comms:
            self.comms[contactID] = msg
            gobject.timeout_add(750, self.removeComm, contactID)
            self.window.invalidate_rect(self.allocation, False)
    
    def drawIncomingComms(self, contactID, msg):
        if contactID not in self.incomingComms:
            self.incomingComms[contactID] = msg
            gobject.timeout_add(750, self.removeIncomingComm, contactID)
            self.window.invalidate_rect(self.allocation, False)
    
    def removeIncomingComm(self, contactID):
        try:
            del self.incomingComms[contactID]
        finally:
            self.window.invalidate_rect(self.allocation, False)
            return False
    
    def removeComm(self, contactID):
        try:
            del self.comms[contactID]
        finally:
            self.window.invalidate_rect(self.allocation, False)
            return False
        
    def publishValue(self, sender, keyFunc, valueFunc):
        key = keyFunc()
        
        h = hashlib.sha1()
        h.update(key)
        hKey = h.digest()
        
        value = valueFunc()
        self.node.iterativeStore(hKey, value)

    def getValue(self, sender, entryKey, showFunc):
        sender.set_sensitive(False)
        key = entryKey.get_text()
        entryKey.set_sensitive(False)
        print 'getValue called'
        h = hashlib.sha1()
        h.update(key)
        hKey = h.digest()
        
        def showValue(result):
            sender.set_sensitive(True)
            entryKey.set_sensitive(True)
            if type(result) == dict:
                value = result[hKey]
            else:
                value = '---not found---'
            showFunc(value)
        def error(failure):
            sender.set_sensitive(True)
            entryKey.set_sensitive(True)
        
        df = self.node.iterativeFindValue(hKey)
        df.addCallback(showValue)
        df.addErrback(error)
        

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print 'Usage:\n%s UDP_PORT KNOWN_NODE_IP KNOWN_NODE_PORT' % sys.argv[0]
        sys.exit(1)
    node = kademlia.node.Node()
    if len(sys.argv) == 4:
        knownNodes = [(sys.argv[2], int(sys.argv[3]))]
    else:
        knownNodes = None
    window = gtk.Window()
    window.set_default_size(640, 640)
    window.set_title('Entangled Viewer - DHT on port %s' % sys.argv[1])
    window.connect("delete-event", gtk.main_quit)
    
    vbox = gtk.VBox(spacing=3)
    window.add(vbox)
    vbox.show()
    
    widget = EntangledViewer(node)
    widget.show()
    
    vbox.pack_start(widget)
    
    hbox = gtk.HBox(False, 8)
    hbox.show()
    vbox.pack_start(hbox, expand=False, fill=False)
    label = gtk.Label("Key:")
    hbox.pack_start(label, False, False, 0)
    label.show()
    entryKey = gtk.Entry()
    hbox.pack_start(entryKey, expand=True, fill=True)
    entryKey.show()
    label = gtk.Label("Value:")
    hbox.pack_start(label, False, False, 0)
    label.show()
    entryValue = gtk.Entry()
    hbox.pack_start(entryValue, expand=True, fill=True)
    entryValue.show()
    
    button = gtk.Button('Publish')
    hbox.pack_start(button, expand=False, fill=False)
    button.connect("clicked", widget.publishValue, entryKey.get_text, entryValue.get_text)
    button.show()
    
    hbox = gtk.HBox(False, 8)
    hbox.show()
    vbox.pack_start(hbox, expand=False, fill=False)
    label = gtk.Label("Key:")
    hbox.pack_start(label, False, False, 0)
    label.show()
    entryKey = gtk.Entry()
    hbox.pack_start(entryKey, expand=True, fill=True)
    entryKey.show()
    label = gtk.Label("Value:")
    hbox.pack_start(label, False, False, 0)
    label.show()
    labelValue = gtk.Label('---unknown---')
    hbox.pack_start(labelValue, expand=True, fill=True)
    labelValue.show()
    
    button = gtk.Button('Retrieve')
    hbox.pack_start(button, expand=False, fill=False)
    button.connect("clicked", widget.getValue, entryKey, labelValue.set_text)
    button.show()
    
    
    #window.add(widget)
    window.present()
    node.joinNetwork(int(sys.argv[1]), knownNodes)
