'''
Created on Oct 12, 2016

@author: mwitt_000
'''
import queue
import threading


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    #  @param cost - of the interface used in routing
    def __init__(self, cost=0, maxsize=0):
        self.in_queue = queue.Queue(maxsize);
        self.out_queue = queue.Queue(maxsize);
        self.cost = cost
    
    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
#                 if pkt_S is not None:
#                     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
#                 if pkt_S is not None:
#                     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None
        
    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
#             print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
#             print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)
            
        
## Implements a network layer packet (different from the RDT packet 
# from programming assignment 2).
# NOTE: This class will need to be extended to for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    ## packet encoding lengths 
    dst_addr_S_length = 5
    prot_S_length = 1
    
    ##@param dst_addr: address of the destination host
    # @param data_S: packet payload
    # @param prot_S: upper layer protocol for the packet (data, or control)
    def __init__(self, dst_addr, prot_S, data_S):
        self.dst_addr = dst_addr
        self.data_S = data_S
        self.prot_S = prot_S
        
    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()
        
    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst_addr).zfill(self.dst_addr_S_length)
        if self.prot_S == 'data':
            byte_S += '1'
        elif self.prot_S == 'control':
            byte_S += '2'
        else:
            raise('%s: unknown prot_S option: %s' %(self, self.prot_S))
        byte_S += self.data_S
        return byte_S
    
    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst_addr = int(byte_S[0 : NetworkPacket.dst_addr_S_length])
        prot_S = byte_S[NetworkPacket.dst_addr_S_length : NetworkPacket.dst_addr_S_length + NetworkPacket.prot_S_length]
        if prot_S == '1':
            prot_S = 'data'
        elif prot_S == '2':
            prot_S = 'control'
        else:
            raise('%s: unknown prot_S field: %s' %(self, prot_S))
        data_S = byte_S[NetworkPacket.dst_addr_S_length + NetworkPacket.prot_S_length : ]        
        return self(dst_addr, prot_S, data_S)
    

    

## Implements a network host for receiving and transmitting data
class Host:
    
    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False #for thread termination
    
    ## called when printing the object
    def __str__(self):
        return 'Host_%s' % (self.addr)
       
    ## create a packet and enqueue for transmission
    # @param dst_addr: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst_addr, data_S):
        p = NetworkPacket(dst_addr, 'data', data_S)
        print('%s: sending packet "%s"' % (self, p))
        self.intf_L[0].put(p.to_byte_S(), 'out') #send packets always enqueued successfully
        
    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.intf_L[0].get('in')
        if pkt_S is not None:
            print('%s: received packet "%s"' % (self, pkt_S))
       
    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return
        


## Implements a multi-interface router described in class
class Router:
    
    ##@param name: friendly router name for debugging
    # @param intf_cost_L: outgoing cost of interfaces (and interface number) 
    # @param rt_tbl_D: routing table dictionary (starting reachability), eg. {1: {1: 1}} # packet to host 1 through interface 1 for cost 1
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_cost_L, rt_tbl_D, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        #note the number of interfaces is set up by out_intf_cost_L
        self.intf_L = []
        for cost in intf_cost_L:
            self.intf_L.append(Interface(cost, max_queue_size))
        #set up the routing table for connected hosts
        self.rt_tbl_D = rt_tbl_D 

    ## called when printing the object
    def __str__(self):
        return 'Router_%s' % (self.name)

    ## look through the content of incoming interfaces and 
    # process data and control packets
    def process_queues(self):
        for i in range(len(self.intf_L)):
            pkt_S = None
            #get packet from interface i
            pkt_S = self.intf_L[i].get('in')
            #if packet exists make a forwarding decision
            if pkt_S is not None:
                p = NetworkPacket.from_byte_S(pkt_S) #parse a packet out
                if p.prot_S == 'data':
                    self.forward_packet(p,i)
                elif p.prot_S == 'control':
                    self.update_routes(p, i)
                else:
                    raise Exception('%s: Unknown packet type in packet %s' % (self, p))
            
    ## forward the packet according to the routing table
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def forward_packet(self, p, i):
        try:
            if(p.dst_addr in self.rt_tbl_D): #If destination is in the routing table, forward to the correct port
                inner = self.rt_tbl_D[p.dst_addr]
                interface = list(inner)[0]
            else: #Destination is not in the routing table
                interface = (i+1)%2
            self.intf_L[(i+1)%2].put(p.to_byte_S(), 'out', True)
            print('%s: forwarding packet "%s" from interface %d to %d' % (self, p, i, (i+1)%2))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass
        
    ## forward the packet according to the routing table
    #  @param p Packet containing routing information
    def update_routes(self, p, i):
        inTable = self.msgToTable(str(p.data_S))
        for key in inTable:
            newCost = inTable[key]
            if(key in self.rt_tbl_D):
                inDict = self.rt_tbl_D[key] #Get values from the message
                innerKey = list(inDict)[0]
                temp = inDict.values()
                curCost = list(temp)[0] #Current lowest cost in routing table
                
                if(i == 1): #If from interface 1, means from host 2
                    if(2 in self.rt_tbl_D):
                        inDict2 = self.rt_tbl_D[2]
                        temp2 = inDict2.values()
                        costTo = temp[0]
                    else:
                        costTo = 0
                else: #If from interface 0, means from host 1
                    if(1 in self.rt_tbl_D):
                        inDict2 = self.rt_tbl_D[1]
                        temp2 = inDict2.values()
                        costTo = temp[0]
                    else:
                        costTo = 0
                
                
                testCost = int(newCost) + int(costTo) #Add values to test
                if(testCost < int(curCost)): #If new route is shorter, update table and send routes
                    inDict[innerKey] = str(testCost)
                    self.send_routes(0) #Send routes on all ports
            else:
                newDict = {} #Haven't seen the node before
                newDict[1] = newCost
                self.rt_tbl_D[key] = newDict #Add to routing table
                self.send_routes(0) #Send routes on all ports
            
            
            
            
        print('%s: Received routing update %s from interface %d' % (self, p, i))
        
    ## send out route update
    # @param i Interface number on which to send out a routing update
    def send_routes(self, i):
        message = self.tableToMsg(self.rt_tbl_D) #Translate routing table to a string message
        p = NetworkPacket(0, 'control', message)
        try:
            for interface in range(2): #Send routes on all interfaces
                self.intf_L[interface].put(p.to_byte_S(), 'out', True)
            print('%s: sending routing update "%s" from interface %d' % (self, p, i))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass
        
    ## Print routing table
    def print_routes(self):
        print('%s: routing table' % self)
        print('       Cost to')
        hosts = '' #Columns
        interface0 = '0 ' #Interface 0 row of costs
        interface1 = '1 ' #Interface 1 row of costs
        for key in self.rt_tbl_D:
            hosts += str(str(key) + ' ') #Add the host column to the string
            value = self.rt_tbl_D[key]
            innerKey = list(value)[0] #Get the key from the inner dictionary, inner dictionary is key's value pair
            if(innerKey == 0):
                interface0 += str(str(value[innerKey]) + ' ') #Add cost to the interface0 row string
                interface1 += '- ' #Add a dash for no information about the cost
            else:
                interface0 += '- ' #Add a dash for no information about the cost
                interface1 += str(str(value[innerKey]) + ' ') #Add cost to the interface1 row string
        print('       ' + hosts)
        print('From ' + interface0)
        print('     ' + interface1 + '\n')
        #print(self.rt_tbl_D)
                
    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return 
    
    #Translate a table to string message
    def tableToMsg(self, rTable):
        message = ''
        for key in rTable:
            message += str(str(key)+',') #Add the destination value
            value = rTable[key]
            innerKey = list(value)[0]
            message += str(str(value[innerKey]) + '/') #Add the cost value
        return message
    
    #Translate a message to a routing table
    def msgToTable(self, message):
        table = {}
        list1 = message.split('/')
        for pair in list1:
            if(str(pair) != ''):
                message = str(pair)
                list2 = message.split(',') #Split the 2 values
                table[str(list2[0])] = str(list2[1]) #Add values to the table
        return table
        