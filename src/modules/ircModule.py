################################################################################
#   (c) 2010, The Honeynet Project
#   Author: Patrik Lantz  patrik@pjlantz.com
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
################################################################################

import re
from utils import *
import moduleManager
from twisted.internet import reactor, defer
from twisted.internet.protocol import Protocol, ClientFactory

@moduleManager.register("irc")
def setup_module(config, hash):
    """
    Function to register modules, simply
    implement this to pass along the config
    to the module object and return it back
    """

    return IRC(config, hash)

class IRC(moduleInterface.Module):
    """
    Implementation of a irc client to do irc based
    botnet monitoring
    """

    def __init__(self, config, hash):
        """
        Constructor sets up configs and moduleCoordinator object
        """
        
        self.hash = hash
        self.config = config
        self.prox = proxySelector.ProxySelector()
         
    def run(self):
        """
        Start execution
        """

        factory = IRCClientFactory(self.hash, self.config)
        host = self.config['botnet']
        port = int(self.config['port'])
        proxyInfo = self.prox.getRandomProxy()
        if proxyInfo == None:
            self.connector = reactor.connectTCP(host, port, factory)
        else:
            proxyHost = proxyInfo['HOST']
            proxyPort = proxyInfo['PORT']
            proxyUser = proxyInfo['USER']
            proxyPass = proxyInfo['PASS']
            socksify = socks5.ProxyClientCreator(reactor, factory)
            if len(proxyUser) == 0:
                self.connector = socksify.connectSocks5Proxy(host, port, proxyHost, proxyPort, "HALE")
            else:
                self.connector = socksify.connectSocks5Proxy(host, port, proxyHost, proxyPort, "HALE", proxyUser, proxyPass)
        
    def stop(self):
        """
        Stop execution
        """

        self.connector.disconnect()
        
                
    def getConfig(self):
        """
        Return specific configuration used by this module
        """
        
        return self.config
        
class IRCProtocol(Protocol):
    """
    Protocol taking care of connection, incoming
    data and outgoing
    """

    factory = None

    def connectionMade(self):
        """
        When connection is made
        """
        
        if self.factory.getConfig()['password'] != 'None':
            self.transport.write(self.factory.getConfig()['pass_grammar'] + ' ' + self.factory.getConfig()['password'] + '\r\n') # connect with pass
        self.transport.write(self.factory.getConfig()['nick_grammar'] + ' ' + self.factory.getConfig()['nick'] + '\r\n') # send NICK grammar
        self.transport.write(self.factory.getConfig()['user_grammar'] + ' ' + self.factory.getConfig()['username'] + ' ' +  
        self.factory.getConfig()['username'] + ' ' + self.factory.getConfig()['username'] + ' :' + 
        self.factory.getConfig()['realname'] + '\r\n') # sebd USER grammar

    def dataReceived(self, data):
        """
        Data is received
        """
        
        checkHost = data.split(':')[1].split(' ')[0].strip()
        
        if data.find(self.factory.getConfig()['ping_grammar']) != -1: # ping
            self.transport.write(self.factory.getConfig()['pong_grammar'] + ' ' + data.split()[1] + '\r\n') # send pong
            if self.factory.getFirstPing():
				if self.factory.getConfig()['channel_pass'] != 'None': # joing with pass
				    self.transport.write(self.factory.getConfig()['join_grammar'] + ' ' + self.factory.getConfig()['channel'] + ' ' + 
				    self.factory.getConfig()['channel_pass'] + '\r\n')
				else:
				    self.transport.write(self.factory.getConfig()['join_grammar'] + ' ' + self.factory.getConfig()['channel'] + '\r\n') # join without pass
				self.factory.setFirstPing()
        elif data.find(self.factory.getConfig()['topic_grammar']) != -1: # topic
           self.factory.putLog(data)
        elif data.find(self.factory.getConfig()['currenttopic_grammar']) != -1: # currenttopic
           firstline = data.split('\r\n')[0].split(self.factory.getConfig()['nick'])[1].strip()
           chan = firstline.split(' ')[0].strip()
           topic = firstline.split(' ')[1].strip()
           secondline = data.split('\r\n')[1].split(self.factory.getConfig()['channel'])[1].strip()
           setby = secondline.split(' ')[0].strip()
           logmsg = 'CURRENTTOPIC ' + chan + ' ' + topic + ' set by ' + setby
           self.factory.putLog(logmsg)
        elif data.find(self.factory.getConfig()['privmsg_grammar']) != -1: # privmsg
            if not data.find(self.factory.getConfig()['version_grammar']) != -1:
                self.factory.putLog(data)
        else: # unrecognized commands
            self.expr = re.compile('!~.*?@')
            match = self.expr.findall(checkHost)
            if match:
                foundGrammar = False
                grammars = self.factory.getConfig().values()
                command = data.split(':')[1].split(' ')[1]
                if command not in grammars:
                    self.factory.putLog(data)
	      
        #urlHandler.URLHandler(self.factory.getConfig(), data).start() # TODO without threads
        
class IRCClientFactory(ClientFactory):
    """
    Clientfactory for the IRCProtocol
    """

    protocol = IRCProtocol # tell base class what proto to build

    def __init__(self, hash, config):
        """
        Constructor, sets first ping received flag
        and config to be used
        """
        
        self.config = config
        self.firstPing = True
        self.hash = hash

    def getConfig(self):
        """
        Returns config 
        """
        
        return self.config
        
    def putLog(self, log):
        moduleCoordinator.ModuleCoordinator().addEvent(moduleCoordinator.LOG_EVENT, log, self.hash, self.config)
        
    def getFirstPing(self):
        """
        Returns get first ping flag
        """
        
        return self.firstPing
        
    def __call__(self):
        """
        Used by the socks5 module to return
        the protocol handled by this factory
        """
        
        p = self.protocol()
        p.factory = self
        return p
        
    def setFirstPing(self):
        """
        Set first ping flag to indicate
        that it has been received
        """
        
        self.firstPing = False
