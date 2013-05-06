=========
sshhelper
=========

`shhhelper` is a simple script which helps 
you ssh into your machines conveniently.

This script keeps a config file in ~/.sshhelper_config,
you can add your hosts there

You should have **pexpect** and **configobj** to make this script
work.
    
    $ pip install pexpect configobj
    # or 
    $ easy_install pexpect configobj

Config File Format
==================

Default config file: ::

    [jump_host]
    # Jump host is used when the machine you want to ssh into is 
    # not available
    #
    # host = 127.0.0.1
    # username = "username"
    # password = "password"
    # port = 22

    [hosts]
    # Add your hosts here.
    # 
    # Available arguments
    # ~~~~~~~~~~~~~~~~~~~
    # 
    # - username
    # - password
    # - summary
    # - `short_name`, short name, you can use this name to log in.
    # - `port`, default to 22
    # - `ssh_args`, extra args , default to an empty string
    # - `commands`, a list of cmds you want to execute when
    #   logged into the host. use a basestring if it is a 
    #   regular command. and a 2-items list/tuple if it need
    #   to expect for the first item and then send the second
    #
    # [[127.0.0.1]]
    # username = "username"
    # password = "password"
    # short_name = "laptop"
    # summary = "my laptop"
    # port = 22
    # ssh_args = "-i your.pem"
    # commands = cd /data, ls


