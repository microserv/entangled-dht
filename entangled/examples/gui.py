#! /usr/bin/env python
import pygtk
pygtk.require('2.0')
import sys, gtk, gobject, cairo
import math

from twisted.internet.gtk2reactor import Gtk2Reactor
import kademlia.protocol
kademlia.protocol.reactor = Gtk2Reactor()
import kademlia.node

import kademlia.contact

class EntangledViewer(gtk.DrawingArea):
    def __init__(self, node, *args, **kwargs):
        gtk.DrawingArea.__init__(self, *args, **kwargs)
        self.node = node
        self.timeoutID = gobject.timeout_add(5000, self.timeout)
        self.comms = []
        self.incomingComms = []
        # poison the contact with our GUI hooks
        kademlia.contact.Contact.__getattr__ = EntangledViewer.__guiContactGetAtrr
        kademlia.contact.Contact.__gui = self
        self.node.__gui = self
        self.node.__realAddContact = self.node.addContact
        self.node.addContact = self.__guiNodeAddContact
    
    
    @staticmethod
    def __guiContactGetAtrr(self, name):
        """ Overridden "poisoned" method
        """
        self.__gui.drawComms(self.id)
        def _sendRPC(*args, **kwargs):
            return self._networkProtocol.sendRPC(self, name, args, **kwargs)
        return _sendRPC
    
    def __guiNodeAddContact(self, contact):
        """ Overridden "poisoned" method
        """
        self.drawIncomingComms(contact.id)
        return self.node.__realAddContact(contact)
    
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
        #print 'draw'
        #cr.set_source_rgb(0.5, 0.5, 0.5)
        #cr.rectangle(0, 0, width, height)
        #cr.fill()

        # draw a rectangle
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.rectangle(0, 0, width, height)
        cr.fill()


        #radial = cairo.RadialGradient(width/6, height/6, width/2,  width, height, width/2)
        #radial.add_color_stop_rgb(0,  1.0, 0, 0)
        #radial.add_color_stop_rgb(1,  0, 0, 1)

        #for i in range(1, 10):
        #    for j in range(1, 10):
        #        cr.rectangle(i*20.0, j*20.0, 10, 10)
        #cr.set_source(radial)
        #cr.fill()



        # draw lines
        #cr.set_source_rgb(0.0, 0.0, 0.8)
        #cr.move_to(width / 3.0, height / 3.0)
        #cr.rel_line_to(0, height / 6.0)
        #cr.move_to(2 * width / 3.0, height / 3.0)
        #cr.rel_line_to(0, height / 6.0)
        #cr.stroke()

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
        cr.arc(w, h, s+1, 0, 2 * math.pi)
        cr.set_source_rgba(0.0, 0.0, 0.4, 0.7)
        cr.stroke()
        #cr.stroke()
        #cr.arc(width / 2.0, height / 2.0, radius / 3.0 - 10, math.pi / 3, 2 * math.pi / 3)
        #cr.stroke()
        
        #cr.set_source_rgb(0.5, 0.5, 0.5)
        #cr.arc(width / 2.0, height / 2.0, radius / 2.0 - 20, 0, 2 * math.pi)
        #cr.fill()
        
        blips = []
        for i in range(160):
            for contact in self.node._buckets[i]._contacts:
                
                blips.append((i, contact))
        if len(blips) == 0:
            return
        # ...and now circles for all the other nodes
        spacing = 360/(len(blips))
        degrees = 0
        radius = min(width/6, height/6) / 3 - 20
        if radius < 5:
            radius = 5
        r = width/2.5
        for blip in blips:
            x = r * math.cos(degrees * math.pi/180)
            y = r * math.sin(degrees * math.pi/180)    

            #print 'bucket:',i
            #print 'degrees:',degrees
            #print 'x:',x
            #print 'y:',y
            #print 'r:',r
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
            
            cr.arc(w, h, radius+1, 0, 2 * math.pi)
            cr.set_source_rgba(0.4, 0.0, 0.0, 0.7)
            cr.stroke()
            
            if blip[1] in self.comms:
                cr.set_source_rgba(0.0, 0.0, 0.8, 0.8)
                cr.move_to(width/2, height/2)
                cr.line_to(w, h)
                cr.stroke()
                gobject.timeout_add(500, self.removeComm, blip[1])
            
            if blip[1] in self.incomingComms:
                cr.set_source_rgba(0.8, 0.0, 0.0, 0.8)
                cr.move_to(width/2, height/2)
                cr.line_to(w, h)
                cr.stroke()
                gobject.timeout_add(500, self.removeIncomingComm, blip[1])
            
            degrees += spacing

    def timeout(self):
        """ Timeout handler to update the GUI """
        print 'timeout'
        self.window.invalidate_rect(self.allocation, False)
        return True
    
    def drawComms(self, contactID):
        self.comms.append(contactID)
        self.window.invalidate_rect(self.allocation, False)
    
    def drawIncomingComms(self, contactID):
        self.incomingComms.append(contactID)
        self.window.invalidate_rect(self.allocation, False)
    
    def removeIncomingComm(self, contactID):
        try:
            self.incomingComms.remove(contactID)
            self.window.invalidate_rect(self.allocation, False)
        except ValueError:
            pass
        return False
    
    def removeComm(self, contactID):
        try:
            self.comms.remove(contactID)
            self.window.invalidate_rect(self.allocation, False)
        except ValueError:
            pass
        return False

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
    window.connect("delete-event", gtk.main_quit)
    widget = EntangledViewer(node)
    widget.show()
    window.add(widget)
    window.present()
    node.joinNetwork(int(sys.argv[1]), knownNodes)
