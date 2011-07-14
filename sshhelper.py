#!/usr/bin/env python
# coding: utf-8
"""
sshhelper
Author: piglei2007@gmail.com
Version: 1.0
"""
import re
import os
import sys
import struct
import fcntl
import termios
import signal
import pexpect
import subprocess

# when a host is not available directly, if you've
# configured a JUMP_HOST, the script will ssh into the
# JUMP_HOST and ssh to the host.
#JUMP_HOST = ("127.0.0.1", "username", "password")

# enable this line if you have no jump host
JUMP_HOST = None

# IP: username, password, port, commands
#
#   - *port* is not required and it's default to 22
#   - *commands* is a list of cmds you want to execute when
#     logged into the host. use a basestring if it is a 
#     regular command. and a 2-items list/tuple if it need
#     to expect for the first item and then send the second
#     item
#   
# examples:
#       {"192.168.1.1": {
#            "username": "jim",     *required*
#            "password": "pw123",   *required*
#            "ssh_arg": "",
#            "port": 22,
#            "commands": [
#                "su",
#                ["Password: ", "test123"]
#            ],
#        }}
KNOWN_HOSTS = {
    # "127.0.0.1": {"username": "username", "password": "password"},
    # "127.0.0.1": {"username": "username", "password": "password", "commands": [
    #    "sudo su",
    #    ("Password: ", "zhulei123"),
    #    "su - caifeng"
    #]},
}
# EXIT_CODES
TIMEOUT = 1
CANNOT_CONNECT = 2
REFUSED = 3
ARGS_ERROR = 99
NOT_EXIST = 100

USAGE = '''
usage:

    %s (IP or short name)
    
    you can type a full ip like 192.168.11.3 or a short name like 
    11.3 to ssh into it.

    available ips:

        %s
''' % (sys.argv[0], ("\n" + " "*8).join(sorted(KNOWN_HOSTS.keys())))

class SSHhandler(object):

    ssh_newkey = 'Are you sure you want to continue connecting'      
    port_default = 22
    dot = re.compile(r'[#$] ')

    def __init__(self, host, username, password, port=22, ssh_args="", is_jump=False):
        self.host = host
        self.username = username
        self.password = password
        self.port = port or self.port_default
        assert self.port > 0 and self.port < 65536, "port number must between 0 and 65535"
        self.is_jump = is_jump
        self.ssh_args = ssh_args

    def login(self):
        print "Start login into %s, please wait..." % self.host
        if self._need_jump():
            print "%s is not availble directly." % self.host
            if self.is_jump or not JUMP_HOST:
                sys.exit(CANNOT_CONNECT)
            
            print "Using the jump server %s." % JUMP_HOST[0]
            jump = SSHhandler(is_jump=True, *JUMP_HOST)
            jump.login()
            self.child = jump.child
       
        ssh_command = "/usr/bin/ssh %s -l %s -p %s %s" % (self.ssh_args, self.username, self.port, self.host)
        if not hasattr(self, "child"):
            self.child = pexpect.spawn(ssh_command)
            # add signal when changing parent.size
            signal.signal(signal.SIGWINCH, self._set_term_size)
        else:
            self.child.expect(self.dot)
            self.child.sendline(ssh_command)
        
        # several situations
        #   1. timeout
        #   2. host is unknown
        #   3. need password
        #   4. no need password
        #   5. Connection refused
        i = self.child.expect([
            pexpect.TIMEOUT,
            self.ssh_newkey,
            '(?i)password: ',
            self.dot, 
            "(?i)Connection refused"
        ])
        # timeout
        if i == 0:
            self._connection_failed(TIMEOUT)
        if i == 3:
            return
        if i == 4:
            self._connection_failed(REFUSED)
        # accept the public key
        if i == 1:
            self.child.sendline("yes")
            i = self.child.expect([pexpect.TIMEOUT, 'password: '])
            if i == 0:
                self._connection_failed(TIMEOUT)
        self.child.sendline(self.password)

    def execute(self, cmd):
        """
        execute a command
        """
        if isinstance(cmd, str):
            cmd = [cmd,]
        if len(cmd) == 2:
            print "expecting %s" % cmd[0]
            self.child.expect([cmd[0], self.dot])
        else:
            self.child.expect(self.dot)
        print "executing %s" % cmd[-1]
        self.child.sendline(cmd[-1])

    def interact(self):
        # resize it first
        self._set_term_size(None, None)
        self.child.interact()

    def _need_jump(self):
        """
        use `ping` to check if the host is available now
        """
        code = subprocess.call("ping %s -c 1 -W 3" % self.host, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        return bool(code)

    def _connection_failed(self, exit_code=TIMEOUT):
        print "Could not ssh into %s" % self.host
        print self.child.before, self.child.after
        sys.exit(exit_code)

    def _set_term_size(self, sig, data):
        """Set the term size to parent's size"""
        s = struct.pack("HHHH", 0, 0, 0, 0)
        a = struct.unpack('hhhh', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ , s))
        self.child.setwinsize(a[0],a[1])


def ip_autocomplete(ip):
    """autocomplete for a ip address"""
    ips = []
    for _ip in KNOWN_HOSTS.keys():
        if _ip == ip:
            return [_ip]
        if ip in _ip:
            ips.append(_ip)
    return ips

if __name__ == "__main__":
    if not len(sys.argv) == 2:
        print USAGE
        sys.exit(ARGS_ERROR)
    
    hosts = ip_autocomplete( sys.argv[1] )
    if not hosts:
        print "%s is not a valid ip address." % sys.argv[1]
        print USAGE
        sys.exit(NOT_EXIST)

    if len(hosts) != 1:
        print "Cann't ssh because %s matches multi hosts.\n    %s" % (sys.argv[1], "\n    ".join(hosts))
        sys.exit(ARGS_ERROR)

    host = hosts[0]
    values = KNOWN_HOSTS.get(host)

    ssh = SSHhandler(
        host,
        values["username"],
        values.get("password", ""),
        port = values.get("port"),
        ssh_args = values.get("ssh_args", "")
    )

    try:
        ssh.login()
    except KeyboardInterrupt, e:
        print "Canceling ..."
        sys.exit(1)

    commands = values.get("commands", [])
    for cmd in commands:
        ssh.execute(cmd)

    ssh.interact()
