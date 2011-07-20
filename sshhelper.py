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
from configobj import ConfigObj

# EXIT_CODES
TIMEOUT = 1
CANNOT_CONNECT = 2
REFUSED = 3
ARGS_ERROR = 99
NOT_EXIST = 100

def int_get(raw, default=None):
    try:
        return int(raw)
    except:
        return default

# This is the default config path
config_path = os.path.join(os.environ["HOME"], ".sshhelper_config")
CONFIG_TMPL = '''[jump_host]
# jump host is used when the machine you want to ssh into is 
# not available
#
# host = 127.0.0.1
# username = "username"
# password = "password"
# port = 22

[hosts]
# add your hosts here.
# 
# - username is the username your want to use
# - password is the password your want to use
# - summary
# - port is the ssh port, default to 22
# - ssh_args is the extra args , default to an empty string
# - commands is a list of cmds you want to execute when
#   logged into the host. use a basestring if it is a 
#   regular command. and a 2-items list/tuple if it need
#   to expect for the first item and then send the second
#
# [[127.0.0.1]]
# username = "username"
# password = "password"
# summary = "my laptop"
# port = 22
# ssh_args = "-i your.pem"
# commands = cd /data, ls
'''

def load_config(config_path):
    """Load config from config file"""
    global KNOWN_HOSTS, JUMP_HOST
    if not os.path.exists(config_path):
        open(config_path, 'w').write(CONFIG_TMPL)
    config = ConfigObj(infile=config_path)
    KNOWN_HOSTS = config.get("hosts", {})
    JUMP_HOST = config.get("jump_host")

load_config(config_path)

def get_hosts_list():
    ret = []
    for k in sorted(KNOWN_HOSTS.keys()):
        ret.append( "        %-20s # %s" % (k, KNOWN_HOSTS[k].get("summary", "")))
    return "\n".join(ret)

USAGE = '''
usage:

    %s (hostname or short name)
    
    you can type a full hostname like 192.168.11.3 or a short name like 
    11.3 to ssh into it.
    
    - modify %s to add your hosts.
    - available hosts:

%s
''' % (sys.argv[0], config_path, get_hosts_list() if KNOWN_HOSTS else "no available hosts")

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
            
            print "Using the jump server %s." % JUMP_HOST["host"]
            jump = SSHhandler(is_jump=True, **JUMP_HOST)
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
        port = int_get(values.get("port"), 22),
        ssh_args = values.get("ssh_args", "")
    )

    try:
        ssh.login()
    except KeyboardInterrupt, e:
        print "Canceling ..."
        sys.exit(1)

    commands = values.get("commands", [])
    for cmd in commands:
        # if cmd contains a ",", split it into a list
        if "," in cmd:
            cmd = cmd.split(",")
        ssh.execute(cmd)

    ssh.interact()
