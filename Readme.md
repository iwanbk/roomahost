# Roomahost
An Open Source HTTP Relay written in Python with [Gevent](http://www.gevent.org).
With Roomahost, you can access your webserver on your local network from remote location(internet).


## Is this another dyndns?

No, with roomahost you do not need to:

* Have public IP

* Set port forwarding, even though your local web server located behind the NAT


## Usage
python server.py domain_to_serve.com

see docs/install_run_server.txt for more detailed instruction

Roomahost comes with simple JSON-RPC authentication server.
Please take a look at simple_rpcd.py file

## Website

http://cp.rh.labhijau.net

## Roomahost Terms

I borrow roomahost terms from TURN protocol:

* peer
something that accessing your local webserver from outer network via roomahost.
Usually, it is a browser.

* client
Roomahost client application that running in a computer inside your local network.

## About
Written by [Iwan Budi Kusnanto](http://ibk.labhijau.net)
