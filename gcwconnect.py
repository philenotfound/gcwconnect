#!/usr/bin/env python

#	wificonfig.py
#
#	Requires: pygame
#			
#	Copyright (c) 2013 Hans Kokx
#	
#	Licensed under the GNU General Public License, Version 3.0 (the "License");
#	you may not use this file except in compliance with the License.
#	You may obtain a copy of the License at
#	
#	http://www.gnu.org/copyleft/gpl.html
#	
#	Unless required by applicable law or agreed to in writing, software
#	distributed under the License is distributed on an "AS IS" BASIS,
#	WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#	See the License for the specific language governing permissions and
#	limitations under the License.


'''

TODO:
* Add option to cancel connecting to a network
* Clean up host ap info display. It's ugly.

'''


import subprocess as SU
import sys, time, os, shutil, re
import pygame
from pygame.locals import *
import pygame.gfxdraw
from os import listdir

# What is our wireless interface?
wlan = "wlan0"

## That's it for options. Everything else below shouldn't be edited.
confdir = os.environ['HOME'] + "/.local/share/gcwconnect/"
netconfdir = confdir+"networks/"
sysconfdir = "/usr/local/etc/network/"
datadir = "/usr/share/gcwconnect/"
if not os.path.exists(datadir):
	datadir = "data/"

surface = pygame.display.set_mode((320,240))
selected_key = ''
passphrase = ''
active_menu = ''
encryptiontypes = ("WEP-40","WEP-128","WPA", "WPA2")
encryptionLabels = ('None', 'WEP', 'WPA', 'WPA2')
colors = {
		"darkbg": (41, 41, 41),
		"lightbg": (84, 84, 84),
		"activeselbg": (160, 24, 24),
		"inactiveselbg": (84, 84, 84),
		"activetext": (255, 255, 255),
		"inactivetext": (128, 128, 128),
		"lightgrey": (200,200,200),
		'logogcw': (255, 255, 255),
		'logoconnect': (216, 32, 32),
		"color": (255,255,255),
		"yellow": (128, 128, 0),
		"blue": (0, 0, 128),
		"red": (128, 0, 0),
		"green": (0, 128, 0),
		"black": (0, 0, 0),
		"white": (255, 255, 255),
		}


## Initialize the display, for pygame
if not pygame.display.get_init():
	pygame.display.init()
if not pygame.font.get_init():
	pygame.font.init()

surface.fill(colors["darkbg"])
pygame.mouse.set_visible(False)
pygame.key.set_repeat(199,69) #(delay,interval)

font_path = os.path.join(datadir, 'Inconsolata.otf')
font12 = pygame.font.Font(font_path, 12)

## File management
def createpaths(): # Create paths, if necessary
	if not os.path.exists(confdir):
		os.makedirs(confdir)
	if not os.path.exists(netconfdir):
		os.makedirs(netconfdir)
	if not os.path.exists(sysconfdir):
		os.makedirs(sysconfdir)

## Interface management
def ifdown(iface):
	SU.Popen(['ifdown', iface], close_fds=True).wait()
	SU.Popen(['ap', '--stop'], close_fds=True).wait()

def ifup(iface):
	return SU.Popen(['ifup', iface], close_fds=True).wait() == 0

# Returns False if the interface was previously enabled
def enableiface(iface):
	check = checkinterfacestatus(iface)
	if check:
		return False

	modal("Enabling WiFi...")
	drawinterfacestatus()
	pygame.display.update()

	SU.Popen(['rfkill', 'unblock', 'wlan'], close_fds=True).wait()
	while True:
		if SU.Popen(['/sbin/ifconfig', iface, 'up'], close_fds=True).wait() == 0:
			break
		time.sleep(0.1);
	return True

def disableiface(iface):
	SU.Popen(['rfkill', 'block', 'wlan'], close_fds=True).wait()

def getip(iface):
	with open(os.devnull, "w") as fnull:
		output = SU.Popen(['/sbin/ifconfig', iface],
				stderr=fnull, stdout=SU.PIPE, close_fds=True).stdout.readlines()

	for line in output:
		if line.strip().startswith("inet addr"):
			return str.strip(
					line[line.find('inet addr')+len('inet addr"') :
					line.find('Bcast')+len('Bcast')].rstrip('Bcast'))

def getcurrentssid(iface): # What network are we connected to?
	if not checkinterfacestatus(iface):
		return None

	with open(os.devnull, "w") as fnull:
		output = SU.Popen(['iwconfig', iface],
				stdout=SU.PIPE, stderr=fnull, close_fds=True).stdout.readlines()
	for line in output:
		if line.strip().startswith(iface):
			ssid = str.strip(line[line.find('ESSID')+len('ESSID:"'):line.find('Nickname:')+len('Nickname:')].rstrip(' Nickname:').rstrip('"'))
	return ssid

def checkinterfacestatus(iface):
	return getip(iface) != None

def connect(iface): # Connect to a network
	ssidconfig = re.escape(ssid)
	shutil.copy2(netconfdir+ssidconfig+".conf",
			sysconfdir+"config-"+iface+".conf")

	if checkinterfacestatus(iface):
		disconnect(iface)

	modal("Connecting...")
	if not ifup(wlan):
		modal('Connection failed!', wait=True)
		return False

	modal('Connected!', timeout=True)
	pygame.display.update()
	drawstatusbar()
	drawinterfacestatus()
	return True

def disconnect(iface):
	if checkinterfacestatus(iface):
		modal("Disconnecting...")
		ifdown(iface)

def getnetworks(iface): # Run iwlist to get a list of networks in range
	wasnotenabled = enableiface(iface)
	modal("Scanning...")

	with open(os.devnull, "w") as fnull:
		output = SU.Popen(['iwlist', iface, 'scan'],
				stdout=SU.PIPE, stderr=fnull, close_fds=True).stdout.readlines()
	for item in output:
		if item.strip().startswith('Cell'):
			# network is the current list corresponding to a MAC address {MAC:[]}
			network = networks.setdefault(parsemac(item), dict())

		elif item.strip().startswith('ESSID:'):
			network["ESSID"] = (parseessid(item))

		elif item.strip().startswith('IE:') and not item.strip().startswith('IE: Unknown') or item.strip().startswith('Encryption key:'):
			network["Encryption"] = (parseencryption(item))

		elif item.strip().startswith('Quality='):
			network["Quality"] = (parsequality(item))
		# Now the loop is over, we will probably find a MAC address and a new "network" will be created.
	redraw()

	if wasnotenabled:
		disableiface(iface)
	return networks

def listuniqssids():
	menuposition = 0
	uniqssid = {}
	uniqssids = {}

	for network, detail in networks.iteritems():
			if detail['ESSID'] not in uniqssids and detail['ESSID']:
				uniqssid = uniqssids.setdefault(detail['ESSID'], {})
				uniqssid["Network"] = detail
				uniqssid["Network"]["menu"] = menuposition
				uniqssid["Network"]["Encryption"] = detail['Encryption']
				menuposition += 1
	return uniqssids

## Parsing iwlist output for various components
def parsemac(macin):
	mac = str.strip(macin[macin.find("Address:")+len("Address: "):macin.find("\n")+len("\n")])
	return mac

def parseessid(essid):
	essid = str.strip(essid[essid.find('ESSID:"')+len('ESSID:"'):essid.find('"\n')+len('"\n')].rstrip('"\n'))
	return essid

def parsequality(quality):
	quality = quality[quality.find("Quality=")+len("Quality="):quality.find(" S")+len(" S")].rstrip(" S")
	if len(quality) < 1:
		quality = '0/100'
	return quality

def parseencryption(encryption):
	encryption = str.strip(encryption)

	if encryption.startswith('Encryption key:off'):
	 	encryption = "none"
	elif encryption.startswith('Encryption key:on'):
		encryption = "WEP-40"
	elif encryption.startswith("IE: WPA"):
		encryption = "WPA"
	elif encryption.startswith("IE: IEEE 802.11i/WPA2"):
		encryption = "WPA2"
	else:
		encryption = "Encrypted (unknown)"
	return encryption

## Saved Networks menu
def getsavednets():
	uniqssid = {}
	uniqssids = {}
	menu = 1
	configs = [ f for f in listdir(netconfdir) ]
	for ssid in configs:
		conf = netconfdir+ssid
		ssid = ssid.split(".conf")[:-1][0]

		with open(conf) as f:
			for line in f:
				if "WLAN_PASSPHRASE" in line:
					key = str.strip(line[line.find('WLAN_PASSPHRASE="')
						+len('WLAN_PASSPHRASE="'):line.find('"\n')+len('"\n')].rstrip('"\n'))
				else:
					key = ''

		x = ssid.split("\\")
		ssid = ''
		for y in x:
			ssid += y

		uniqssid=uniqssids.setdefault(ssid, {'Network': {'ESSID': ssid, 'Key': key, 'menu': menu}})
		menu += 1
	uniq = uniqssids
	return uniq

def aafilledcircle(surface, color, center, radius):
	'''Helper function to draw anti-aliased circles using an interface similar
	to pygame.draw.circle.
	'''
	x, y = center
	pygame.gfxdraw.aacircle(surface, x, y, radius, color)
	pygame.gfxdraw.filled_circle(surface, x, y, radius, color)
	return Rect(x - radius, y - radius, radius * 2 + 1, radius * 2 + 1)

## Draw interface elements
class hint:
	global colors
	def __init__(self, button, text, x, y, bg=colors["darkbg"]):
		self.button = button
		self.text = text
		self.x = x
		self.y = y
		self.bg = bg
		self.drawhint()

	def drawhint(self):
		if self.button == 'l' or self.button == 'r':
			if self.button == 'l':
				aafilledcircle(surface, colors["black"], (self.x, self.y+5), 5)
				pygame.draw.rect(surface, colors["black"], (self.x-5, self.y+6, 10, 5))


			if self.button == 'r':
				aafilledcircle(surface, colors["black"], (self.x+15, self.y+5), 5)
				pygame.draw.rect(surface, colors["black"], (self.x+11, self.y+6, 10, 5))

			button = pygame.draw.rect(surface, colors["black"], (self.x, self.y, 15, 11))
			text = pygame.font.SysFont(None, 12).render(self.button.upper(), True, colors["white"], colors["black"])
			buttontext = text.get_rect()
			buttontext.center = button.center
			surface.blit(text, buttontext)

		if self.button == "select" or self.button == "start":
			lbox = aafilledcircle(surface, colors["black"], (self.x+5, self.y+4), 5)
			rbox = aafilledcircle(surface, colors["black"], (self.x+29, self.y+4), 5)
			straightbox = lbox.union(rbox)
			buttoncenter = straightbox.center
			if self.button == 'select':
				straightbox.y = lbox.center[1]
			straightbox.height = (straightbox.height + 1) / 2
			pygame.draw.rect(surface, colors["black"], straightbox)

			roundedbox = Rect(lbox.midtop, (rbox.midtop[0] - lbox.midtop[0], lbox.height - straightbox.height))
			if self.button == 'start':
				roundedbox.bottomleft = lbox.midbottom
			pygame.draw.rect(surface, colors["black"], roundedbox)
			text = pygame.font.SysFont(None, 11).render(self.button.upper(), True, colors["white"], colors["black"])
			buttontext = text.get_rect()
			buttontext.center = buttoncenter
			buttontext.move_ip(0, 1)
			surface.blit(text, buttontext)

			labelblock = pygame.draw.rect(surface, self.bg, (self.x+40,self.y,25,14))
			labeltext = pygame.font.SysFont(None, 12).render(self.text, True, colors["white"], self.bg)
			surface.blit(labeltext, labelblock)

		elif self.button in ('a', 'b', 'x', 'y'):
			if self.button == "a":
				color = colors["green"]
			elif self.button == "b":
				color = colors["blue"]
			elif self.button == "x":
				color = colors["red"]
			elif self.button == "y":
				color = colors["yellow"]

			labelblock = pygame.draw.rect(surface, self.bg, (self.x+10,self.y,35,14))
			labeltext = pygame.font.SysFont(None, 12).render(self.text, True, colors["white"], self.bg)
			surface.blit(labeltext, labelblock)

			button = aafilledcircle(surface, color, (self.x,self.y+4), 5) # (x, y)
			text = pygame.font.SysFont(None, 11).render(self.button.upper(), True, colors["white"], color)
			buttontext = text.get_rect()
			buttontext.center = button.center
			buttontext.move_ip(0, 1)
			surface.blit(text, buttontext)

		elif self.button in ('left', 'right', 'up', 'down'):

			# Vertical
			pygame.draw.rect(surface, colors["black"], (self.x+5, self.y-1, 4, 12))
			pygame.draw.rect(surface, colors["black"], (self.x+6, self.y-2, 2, 14))

			# Horizontal
			pygame.draw.rect(surface, colors["black"], (self.x+1, self.y+3, 12, 4))
			pygame.draw.rect(surface, colors["black"], (self.x, self.y+4, 14, 2))

			if self.button == "left":
				pygame.draw.rect(surface, colors["white"], (self.x+2, self.y+4, 3, 2))
			elif self.button == "right":
				pygame.draw.rect(surface, colors["white"], (self.x+9, self.y+4, 3, 2))
			elif self.button == "up":
				pygame.draw.rect(surface, colors["white"], (self.x+6, self.y+1, 2, 3))
			elif self.button == "down":
				pygame.draw.rect(surface, colors["white"], (self.x+6, self.y+7, 2, 3))

			labelblock = pygame.draw.rect(surface, self.bg, (self.x+20,self.y,35,14))
			labeltext = pygame.font.SysFont(None, 12).render(self.text, True, (255, 255, 255), self.bg)
			surface.blit(labeltext, labelblock)

class LogoBar(object):
	'''The logo area at the top of the screen.'''

	def __init__(self):
		gcw_font = pygame.font.Font(os.path.join(datadir, 'gcwzero.ttf'), 25)
		self.text1 = gcw_font.render('GCW', True, colors['logogcw'], colors['lightbg'])
		self.text2 = gcw_font.render('CONNECT', True, colors['logoconnect'], colors['lightbg'])

	def draw(self):
		pygame.draw.rect(surface, colors['lightbg'], (0,0,320,32))
		pygame.draw.line(surface, colors['white'], (0, 33), (320, 33))

		rect1 = self.text1.get_rect()
		rect1.topleft = (8 + 5 + 1, 5)
		surface.blit(self.text1, rect1)

		rect2 = self.text2.get_rect()
		rect2.topleft = rect1.topright
		surface.blit(self.text2, rect2)

def drawstatusbar(): # Set up the status bar
	global colors
	pygame.draw.rect(surface, colors['lightbg'], (0,224,320,16))
	pygame.draw.line(surface, colors['white'], (0, 223), (320, 223))
	wlantext = pygame.font.SysFont(None, 16).render("...", True, colors['white'], colors['lightbg'])
	wlan_text = wlantext.get_rect()
	wlan_text.topleft = (4, 227)
	surface.blit(wlantext, wlan_text)

def drawinterfacestatus(): # Interface status badge
	global colors
	wlanstatus = checkinterfacestatus(wlan)
	if not wlanstatus: 
		wlanstatus = wlan+" is off."
	else:
		wlanstatus = getcurrentssid(wlan)

	wlantext = pygame.font.SysFont(None, 16).render(wlanstatus, True, colors['white'], colors['lightbg'])
	wlan_text = wlantext.get_rect()
	wlan_text.topleft = (4, 227)
	surface.blit(wlantext, wlan_text)

	if checkinterfacestatus(wlan):
		text = pygame.font.SysFont(None, 16).render(getip(wlan), True, colors['activeselbg'], colors['lightbg'])
		interfacestatus_text = text.get_rect()
		interfacestatus_text.topright = (315, 227)
		surface.blit(text, interfacestatus_text)

def redraw():
	global colors
	surface.fill(colors['darkbg'])
	logoBar.draw()
	mainmenu()
	if wirelessmenu is not None:
		wirelessmenu.draw()
		pygame.draw.rect(surface, colors['darkbg'], (0, 208, 320, 16))
		hint("select", "Edit", 4, 210)
		hint("a", "Connect", 75, 210)
		hint("b", "/", 130, 210)
		hint("left", "Back", 145, 210)
	if active_menu == "main":
		pygame.draw.rect(surface, colors['darkbg'], (0, 208, 320, 16))
		hint("a", "Select", 8, 210)
	if active_menu == "saved":
		hint("y", "Forget", 195, 210)

	drawstatusbar()
	drawinterfacestatus()
	pygame.display.update()

def modal(text, wait=False, timeout=False, query=False):
	global colors
	dialog = pygame.draw.rect(surface, colors['lightbg'], (64,88,192,72))
	pygame.draw.rect(surface, colors['white'], (62,86,194,74), 2)

	text = pygame.font.SysFont(None, 16).render(text, True, colors['white'], colors['lightbg'])
	modal_text = text.get_rect()
	modal_text.center = dialog.center

	surface.blit(text, modal_text)
	pygame.display.update()

	if wait:
		abutton = hint("a", "Continue", 205, 145, colors['lightbg'])
		pygame.display.update()
	elif timeout:
		time.sleep(2.5)
		redraw()
	elif query:
		abutton = hint("a", "Confirm", 150, 145, colors['lightbg'])
		bbutton = hint("b", "Cancel", 205, 145, colors['lightbg'])
		pygame.display.update()
		while True:
			for event in pygame.event.get():
				if event.type == KEYDOWN:
					if event.key == K_LCTRL:
						return True
					elif event.key == K_LALT:
						return



	if not wait:
		return

	while True:
		for event in pygame.event.get():
			if event.type == KEYDOWN and event.key == K_LCTRL:
				redraw()
				return

## Connect to a network
def writeconfig(): # Write wireless configuration to disk
	global passphrase
	global encryption
	try:
		encryption
	except NameError:
		encryption = uniq[ssid]['Network']['Encryption']

	if passphrase:
		if passphrase == "none":
			passphrase = ""

	ssidconfig = re.escape(ssid)
	conf = netconfdir+ssidconfig+".conf"

	f = open(conf, "w")
	f.write('WLAN_ESSID="'+ssid+'"\n')

	if encryption == "WEP-128":
		encryption = "wep"
		f.write('WLAN_PASSPHRASE="s:'+passphrase+'"\n')
	else:
		f.write('WLAN_PASSPHRASE="'+passphrase+'"\n')
		if encryption == "WEP-40":
			encryption = "wep"
		elif encryption == "WPA":
			encryption = "wpa"
		elif encryption == "WPA2":
			encryption = "wpa2"

	
	f.write('WLAN_ENCRYPTION="'+encryption+'"\n')
	f.write('WLAN_DHCP_RETRIES=20\n')
	f.close()

## HostAP
def startap():
	global wlan
	if checkinterfacestatus(wlan):
		disconnect(wlan)

	modal("Creating AP...")
	if SU.Popen(['ap', '--start'], close_fds=True).wait() == 0:
		modal('AP created!', timeout=True)
	else:
		modal('Failed to create AP...', wait=True)
	redraw()
	return True

## Input methods

keyLayouts = {
	'qwertyNormal': (
			('`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '='),
			('q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\\'),
			('a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', '\''),
			('z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/'),
			),
	'qwertyShift': (
			('~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '+'),
			('Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{', '}', '|'),
			('A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':', '"'),
			('Z', 'X', 'C', 'V', 'B', 'N', 'M', '<', '>', '?'),
			),
	'wep': (
			('1', '2', '3', '4'),
			('5', '6', '7', '8'),
			('9', '0', 'A', 'B'),
			('C', 'D', 'E', 'F'),
			),
	}
keyboardCycleOrder = ('wep', 'qwertyNormal', 'qwertyShift')
def nextKeyboard(board):
	return keyboardCycleOrder[
			(keyboardCycleOrder.index(board) + 1) % len(keyboardCycleOrder)
			]

class key:
	global colors
	def __init__(self):
		self.key = []
		self.selection_color = colors['activeselbg']
		self.text_color = colors['activetext']
		self.selection_position = (0,0)
		self.selected_item = 0

	def init(self, key, row, column):
		self.key = key
		self.row = row
		self.column = column
		self.drawkey()

	def drawkey(self):
		key_width = 16
		key_height = 16

		top = 136 + self.row * 20
		left = 32 + self.column * 20

		if len(self.key) > 1:
			key_width = 36
		keybox = pygame.draw.rect(surface, colors['lightbg'], (left,top,key_width,key_height))
		text = pygame.font.SysFont(None, 16).render(self.key, True, colors['white'], colors['lightbg'])
		label = text.get_rect()
		label.center = keybox.center
		surface.blit(text, label)

class radio:
	global colors
	def __init__(self):
		self.key = []
		self.selection_color = colors['activeselbg']
		self.text_color = colors['activetext']
		self.selection_position = (0,0)
		self.selected_item = 0

	def init(self, key, row, column):
		self.key = key
		self.row = row
		self.column = column
		self.drawkey()

	def drawkey(self):
		key_width = 64
		key_height = 16

		top = 136 + self.row * 20
		left = 32 + self.column * 64

		if len(self.key) > 1:
			key_width = 64
		radiobutton = aafilledcircle(surface, colors['white'], (left, top), 8)
		aafilledcircle(surface, colors['darkbg'], (left, top), 6)
		text = pygame.font.SysFont(None, 16).render(self.key, True, (255, 255, 255), colors['darkbg'])
		label = text.get_rect()
		label.left = radiobutton.right + 8
		label.top = radiobutton.top + 4
		surface.blit(text, label)

def getSSID():
	global passphrase
	displayinputlabel("ssid")
	drawkeyboard("qwertyNormal")
	getinput("qwertyNormal", "ssid")
	ssid = passphrase
	passphrase = ''
	return ssid

def drawEncryptionType():
	global colors
	# Draw top background 
	pygame.draw.rect(surface, colors['darkbg'], (0,40,320,140))

	# Draw footer
	pygame.draw.rect(surface, colors['lightbg'], (0,224,320,16))
	pygame.draw.line(surface, colors['white'], (0, 223), (320, 223))
	hint("select", "Cancel", 4, 227, colors['lightbg'])
	hint("a", "Enter", 285, 227, colors['lightbg'])

	# Draw the keys
	z = radio()
	for i, label in enumerate(encryptionLabels):
		z.init(label, 0, i)

	pygame.display.update()

def displayencryptionhint():
	global colors
	global encryption

	try:
		if encryption:
			if encryption == "wep":
				encryption = "WEP-40"
	except:
		pass

	try:
		if encryption:
			pygame.draw.rect(surface, colors['darkbg'], (2,100,320,34))
			hint("l", "L", 16, 113)
			hint("r", "R", 289, 113)

			pos = 1
			for enc in encryptiontypes:
				x = (pos * 60) - 20
				labelblock = pygame.draw.rect(surface, colors['darkbg'], (x, 111,25,14))
				labeltext = font12.render(enc.center(10, ' '), True, colors["white"], colors['darkbg'])
				surface.blit(labeltext, labelblock)
				pos += 1
			pygame.display.update()
	except NameError:
		pass

def chooseencryption(direction):
	global selected_key

	encryption = ''

	if direction == "left":
		selected_key[0] = (selected_key[0] - 1) % len(encryptionLabels)

	elif direction == "right":
		selected_key[0] = (selected_key[0] + 1) % len(encryptionLabels)

	elif direction == "select":
		encryption = encryptionLabels[selected_key[0]]
		if encryption == "WEP":
			encryption = "WEP-40"

	elif direction == "init":
		selected_key = [0,0]

	drawEncryptionType()
	pos = (32 + selected_key[0] * 64, 136)
	aafilledcircle(surface, colors['activeselbg'], pos, 6)
	pygame.display.update()

	return encryption

def prevEncryption():
	global encryption

	for i, s in enumerate(encryptiontypes):
		if encryption in s:
			x = encryptiontypes.index(s)-1
			try:
				encryption = encryptiontypes[x]
				return
			except IndexError:
				encryption = encryptiontypes[:-1]
				return

def nextEncryption():
	global encryption

	for i, s in enumerate(encryptiontypes):
		if encryption in s:
			x = encryptiontypes.index(s)+1
			try:
				encryption = encryptiontypes[x]
				return
			except IndexError:
				encryption = encryptiontypes[0]
				return

def getEncryptionType():
	chooseencryption("init")
	while True:
		for event in pygame.event.get():
			if event.type == KEYDOWN:
				if event.key == K_LEFT:		# Move cursor left
					chooseencryption("left")
				if event.key == K_RIGHT:	# Move cursor right
					chooseencryption("right")
				if event.key == K_LCTRL:	# A button
					return chooseencryption("select")
				if event.key == K_ESCAPE:	# Select key
					return 'cancel'

def drawkeyboard(board):
	global colors

	# Draw keyboard background 
	pygame.draw.rect(surface, colors['darkbg'], (0,134,320,106))

	# Draw bottom background
	pygame.draw.rect(surface, colors['lightbg'], (0,224,320,16))
	pygame.draw.line(surface, colors['white'], (0, 223), (320, 223))

	hint("select", "Cancel", 4, 227, colors['lightbg'])
	hint("start", "Finish", 75, 227, colors['lightbg'])
	hint("x", "Delete", 155, 227, colors['lightbg'])
	if not board == "wep":
		hint("y", "Shift", 200, 227, colors['lightbg'])
		hint("b", "Space", 240, 227, colors['lightbg'])

	else:
		hint("y", "Full KB", 200, 227, colors['lightbg'])

	hint("a", "Enter", 285, 227, colors['lightbg'])

	# Draw the keys
	z = key()
	for row, rowData in enumerate(keyLayouts[board]):
		for column, label in enumerate(rowData):
			z.init(label, row, column)

	pygame.display.update()

def getinput(board, kind, ssid=""):
	selectkey(board, kind)
	if kind == "key":
		displayencryptionhint()
		pos = 1
		for enc in encryptiontypes:
			x = (pos * 60) - 20
			if enc == encryption:
				labelblock = pygame.draw.rect(surface, colors['white'], (x, 111,25,14))
				labeltext = font12.render(enc.center(10, ' '), True, colors["activetext"], colors['activeselbg'])
				surface.blit(labeltext, labelblock)
			else:
				pos += 1
		pygame.display.update()
	return softkeyinput(board, kind, ssid)

def softkeyinput(keyboard, kind, ssid):
	global passphrase
	global encryption
	global securitykey
	def update():
		displayinputlabel("key")
		displayencryptionhint()
		pos = 1
		for enc in encryptiontypes:
			x = (pos * 60) - 20
			if enc == encryption:
				labelblock = pygame.draw.rect(surface, colors['white'], (x, 111,25,14))
				labeltext = font12.render(enc.center(10, ' '), True, colors["activetext"], colors['activeselbg'])
				surface.blit(labeltext, labelblock)
			else:
				pos += 1
		pygame.display.update()

	while True:
		event = pygame.event.wait()

		if event.type == KEYDOWN:
			if event.key == K_RETURN:		# finish input
				selectkey(keyboard, kind, "enter")
				redraw()
				if ssid == '':
					return False
				writeconfig()
				connect(wlan)
				return True

			if event.key == K_UP:		# Move cursor up
				selectkey(keyboard, kind, "up")
			if event.key == K_DOWN:		# Move cursor down
				selectkey(keyboard, kind, "down")
			if event.key == K_LEFT:		# Move cursor left
				selectkey(keyboard, kind, "left")
			if event.key == K_RIGHT:	# Move cursor right
				selectkey(keyboard, kind, "right")
			if event.key == K_LCTRL:	# A button
				selectkey(keyboard, kind, "select")
			if event.key == K_LALT:		# B button
				if encryption != "WEP-40":
					selectkey(keyboard, kind, "space")
			if event.key == K_SPACE:	# Y button (swap keyboards)
				keyboard = nextKeyboard(keyboard)
				drawkeyboard(keyboard)
				selectkey(keyboard, kind, "swap")
			if event.key == K_LSHIFT:	# X button
				selectkey(keyboard, kind, "delete")
			if event.key == K_ESCAPE:	# Select key
				passphrase = ''
				try:
					encryption
				except NameError:
					pass
				else:
					del encryption

				try:
					securitykey
				except NameError:
					pass
				else:
					del securitykey
				redraw()
				return False
			if kind == "key":
				if event.key == K_TAB:			# L shoulder button
					prevEncryption()
					update()
				if event.key == K_BACKSPACE:	# R shoulder button
					nextEncryption()
					update()

def displayinputlabel(kind, size=24): # Display passphrase on screen
	global colors
	global encryption

	def update():
		displayencryptionhint()
		pos = 1
		for enc in encryptiontypes:
			x = (pos * 60) - 20
			if enc == encryption:
				labelblock = pygame.draw.rect(surface, colors['white'], (x, 111,25,14))
				labeltext = font12.render(enc.center(10, ' '), True, colors["activetext"], colors['activeselbg'])
				surface.blit(labeltext, labelblock)
			else:
				pos += 1

	if kind == "ssid":
		# Draw SSID and encryption type labels
		pygame.draw.rect(surface, colors['darkbg'], (2,100,320,34))
		labelblock = pygame.draw.rect(surface, colors['white'], (0,35,320,20))
		labeltext = pygame.font.SysFont(None, 18).render("Enter new SSID", True, colors['lightbg'], colors['white'])
		label = labeltext.get_rect()
		label.center = labelblock.center
		surface.blit(labeltext, label)

	elif kind == "key":
		displayencryptionhint()
		# Draw SSID and encryption type labels
		labelblock = pygame.draw.rect(surface, colors['white'], (0,35,320,20))
		if len(ssid) >= 13:
			labeltext = font12.render("Enter "+encryption+" for "+"%s..."%(ssid[:13]), True, colors['lightbg'], colors['white'])
		else:
			labeltext = font12.render("Enter "+encryption+" key for "+ssid, True, colors['lightbg'], colors['white'])
		label = labeltext.get_rect()
		label.center = labelblock.center
		surface.blit(labeltext, label)
		update()

	# Input area
	bg = pygame.draw.rect(surface, colors['white'], (0, 55, 320, 45))
	text = "[ "
	text += passphrase
	text += " ]"
	pw = pygame.font.SysFont(None, size).render(text, True, (0, 0, 0), colors['white'])
	pwtext = pw.get_rect()
	pwtext.center = bg.center
	surface.blit(pw, pwtext)
	pygame.display.update()

def selectkey(keyboard, kind, direction=""):
	def highlightkey(keyboard, pos='[0,0]'):
		drawkeyboard(keyboard)
		pygame.display.update()

		left_margin = 32
		top_margin = 136

		if pos[0] > left_margin:
			x = left_margin + (16 * (pos[0]))
		else:
			x = left_margin + (16 * pos[0]) + (pos[0] * 4)
			

		if pos[1] > top_margin:
			y = top_margin + (16 * (pos[1]))
		else:
			y = top_margin + (16 * pos[1]) + (pos[1] * 4)

		pointlist = [
				(x, y),
				(x + 16, y),
				(x + 16, y + 16),
				(x, y + 16),
				(x, y)
				]
		lines = pygame.draw.lines(surface, (255,255,255), True, pointlist, 1)
		pygame.display.update()

	global selected_key
	global passphrase

	if not selected_key:
		selected_key = [0,0]

	def clampRow():
		selected_key[1] = min(selected_key[1], len(layout) - 1)
	def clampColumn():
		selected_key[0] = min(selected_key[0], len(layout[selected_key[1]]) - 1)

	layout = keyLayouts[keyboard]
	if direction == "swap":
		# Clamp row first since each row can have a different number of columns.
		clampRow()
		clampColumn()
	elif direction == "up":
		selected_key[1] = (selected_key[1] - 1) % len(layout)
		clampColumn()
	elif direction == "down":
		selected_key[1] = (selected_key[1] + 1) % len(layout)
		clampColumn()
	elif direction == "left":
		selected_key[0] = (selected_key[0] - 1) % len(layout[selected_key[1]])
	elif direction == "right":
		selected_key[0] = (selected_key[0] + 1) % len(layout[selected_key[1]])
	elif direction == "select":
		passphrase += layout[selected_key[1]][selected_key[0]]
		if len(passphrase) > 20:
			logoBar.draw()
			displayinputlabel(kind, 12)
		else:
			displayinputlabel(kind)
	elif direction == "space":
		passphrase += ' '
		if len(passphrase) > 20:
			logoBar.draw()
			displayinputlabel(kind, 12)
		else:
			displayinputlabel(kind)
	elif direction == "delete":
		if len(passphrase) > 0:
			passphrase = passphrase[:-1]
			logoBar.draw()
			if len(passphrase) > 20:
				displayinputlabel(kind, 12)
			else:
				displayinputlabel(kind)

	highlightkey(keyboard, selected_key)

class Menu:
	global colors
	font = pygame.font.SysFont
	dest_surface = pygame.Surface
	canvas_color = colors["darkbg"]

	elements = []

	def __init__(self):
		self.set_elements([])
		self.selected_item = 0
		self.origin = (0,0)
		self.menu_width = 0
		self.menu_height = 0
		self.selection_color = colors["activeselbg"]
		self.text_color = colors["activetext"]
		self.font = pygame.font.Font(font_path, 16)

	def move_menu(self, top, left):
		self.origin = (top, left)

	def set_colors(self, text, selection, background):
		self.text_color = text
		self.selection_color = selection

	def set_elements(self, elements):
		self.elements = elements

	def get_position(self):
		return self.selected_item

	def get_selected(self):
		return self.elements[self.selected_item]

	def init(self, elements, dest_surface):
		self.set_elements(elements)
		self.dest_surface = dest_surface
		
	def draw(self,move=0):
		if len(self.elements) == 0:
			return

		self.selected_item = (self.selected_item  + move) % len(self.elements)

		# Which items are to be shown?
		if self.selected_item <= 2: # We're at the top
			visible_elements = self.elements[0:6]
			selected_within_visible = self.selected_item
		elif self.selected_item >= len(self.elements) - 3: # We're at the bottom
			visible_elements = self.elements[-6:]
			selected_within_visible = self.selected_item - (len(self.elements) - len(visible_elements))
		else: # The list is larger than 5 elements, and we're in the middle
			visible_elements = self.elements[self.selected_item - 2:self.selected_item + 3]
			selected_within_visible = 2

		# What width does everything have?
		max_width = max([self.get_item_width(visible_element) for visible_element in visible_elements])
		# And now the height
		heights = [self.get_item_height(visible_element) for visible_element in visible_elements]
		total_height = sum(heights)

		# Background
		menu_surface = pygame.Surface((max_width, total_height))
		menu_surface.fill(self.canvas_color)

		# Selection
		left = 0
		top = sum(heights[0:selected_within_visible])
		width = max_width
		height = heights[selected_within_visible]
		selection_rect = (left, top, width, height)
		pygame.draw.rect(menu_surface,self.selection_color,selection_rect)

		# Clear any error elements
		error_rect = (left+width+8, 35, 192, 172)
		pygame.draw.rect(surface,colors['darkbg'],error_rect)

		# Elements
		top = 0
		for i in xrange(len(visible_elements)):
			self.render_element(menu_surface, visible_elements[i], 0, top)
			top += heights[i]
		self.dest_surface.blit(menu_surface,self.origin)
		return self.selected_item

	def get_item_height(self, element):
		render = self.font.render(element, 1, self.text_color)
		spacing = 5
		return render.get_rect().height + spacing * 2

	def get_item_width(self, element):
		render = self.font.render(element, 1, self.text_color)
		spacing = 5
		return render.get_rect().width + spacing * 2

	def render_element(self, menu_surface, element, left, top):
		render = self.font.render(element, 1, self.text_color)
		spacing = 5
		menu_surface.blit(render, (left + spacing, top + spacing, render.get_rect().width, render.get_rect().height))

class NetworksMenu(Menu):
	global colors
	def set_elements(self, elements):
		self.elements = elements

	def get_item_width(self, element):
		if len(str(element[0])) > 16:
			the_ssid = "%s..."%(element[0][:16])
		else:
			the_ssid = element[0].ljust(19)

		render = self.font.render(the_ssid, 1, self.text_color)
		spacing = 15
		return render.get_rect().width + spacing * 2

	def get_item_height(self, element):
		render = self.font.render(element[0], 1, self.text_color)
		spacing = 5
		return (render.get_rect().height + spacing * 2) + 5

	def render_element(self, menu_surface, element, left, top):

		if len(str(element[0])) > 17:
			the_ssid = "%s..."%(element[0][:14])
		else:
			the_ssid = element[0].ljust(17)

		def qualityPercent(x):
			percent = (float(x.split("/")[0]) / float(x.split("/")[1])) * 100
			if percent > 100:
				percent = 100
			return int(percent)
		## Wifi signal icons
		percent = qualityPercent(element[1])

		if percent >= 6 and percent <= 24:
			signal_icon = 'wifi-0.png'
		elif percent >= 25 and percent <= 49:
			signal_icon = 'wifi-1.png'
		elif percent >= 50 and percent <= 74:
			signal_icon = 'wifi-2.png'
		elif percent >= 75:
			signal_icon = 'wifi-3.png'
		else:
			signal_icon = 'transparent.png'

		## Encryption information
		enc_type = element[2]
		if enc_type == "NONE" or enc_type == '':
			enc_icon = "open.png"
			enc_type = "Open"
		elif enc_type == "WPA" or enc_type == "wpa":
			enc_icon = "closed.png"
		elif enc_type == "WPA2" or enc_type == "wpa2":
			enc_icon = "closed.png"
		elif enc_type == "WEP-40" or enc_type == "WEP-128" or enc_type == "wep" or enc_type == "WEP":
			enc_icon = "closed.png"
			enc_type = "WEP"
		else:
			enc_icon = "unknown.png"
			enc_type = "(Unknown)"


		qual_img = pygame.image.load((os.path.join(datadir, signal_icon))).convert_alpha()
		enc_img = pygame.image.load((os.path.join(datadir, enc_icon))).convert_alpha()

		boldtext = pygame.font.Font(font_path, 16)
		subtext = font12

		ssid = boldtext.render(the_ssid, 1, self.text_color)
		enc = subtext.render(enc_type, 1, colors["lightgrey"])
		strength = subtext.render(str(str(percent) + "%").rjust(4), 1, colors["lightgrey"])
		qual = subtext.render(element[1], 1, colors["lightgrey"])
		spacing = 2

		menu_surface.blit(ssid, (left + spacing, top, ssid.get_rect().width, ssid.get_rect().height))
		menu_surface.blit(enc, (left + enc_img.get_rect().width + 12, top + 18, enc.get_rect().width, enc.get_rect().height))
		menu_surface.blit(enc_img, pygame.rect.Rect(left + 8, (top + 24) - (enc_img.get_rect().height / 2), enc_img.get_rect().width, enc_img.get_rect().height))
		# menu_surface.blit(strength, (left + 137, top + 18, strength.get_rect().width, strength.get_rect().height))
		# menu_surface.blit(qual_img, pygame.rect.Rect(left + 140, top + 2, qual_img.get_rect().width, qual_img.get_rect().height))
		menu_surface.blit(qual_img, pygame.rect.Rect(left + 140, top + 8, qual_img.get_rect().width, qual_img.get_rect().height))
		pygame.display.flip()

	def draw(self,move=0):
		if len(self.elements) == 0:
			return

		if move != 0:
			self.selected_item += move
			if self.selected_item < 0:
				self.selected_item = 0
			elif self.selected_item >= len(self.elements):
				self.selected_item = len(self.elements) - 1

		# Which items are to be shown?
		if self.selected_item <= 2: # We're at the top
			visible_elements = self.elements[0:5]
			selected_within_visible = self.selected_item
		elif self.selected_item >= len(self.elements) - 3: # We're at the bottom
			visible_elements = self.elements[-5:]
			selected_within_visible = self.selected_item - (len(self.elements) - len(visible_elements))
		else: # The list is larger than 5 elements, and we're in the middle
			visible_elements = self.elements[self.selected_item - 2:self.selected_item + 3]
			selected_within_visible = 2

		# What width does everything have?
		max_width = max([self.get_item_width(visible_element) for visible_element in visible_elements])

		# And now the height
		heights = [self.get_item_height(visible_element) for visible_element in visible_elements]
		total_height = sum(heights)

		# Background
		menu_surface = pygame.Surface((max_width, total_height))
		menu_surface.fill(self.canvas_color)

		# Selection
		left = 0
		top = sum(heights[0:selected_within_visible])
		width = max_width
		height = heights[selected_within_visible]
		selection_rect = (left, top, width, height)
		pygame.draw.rect(menu_surface,self.selection_color,selection_rect)

		# Elements
		top = 0
		for i in xrange(len(visible_elements)):
			self.render_element(menu_surface, visible_elements[i], 0, top)
			top += heights[i]
		self.dest_surface.blit(menu_surface,self.origin)
		return self.selected_item

def to_menu(new_menu):
	global colors
	if new_menu == "main":
		menu.set_colors(colors['activetext'], colors['activeselbg'], colors['darkbg'])
		if wirelessmenu is not None:
			wirelessmenu.set_colors(colors['inactivetext'], colors['inactiveselbg'], colors['darkbg'])
	elif new_menu == "ssid" or new_menu == "saved":
		menu.set_colors(colors['inactivetext'], colors['inactiveselbg'], colors['darkbg'])
		wirelessmenu.set_colors(colors['activetext'], colors['activeselbg'], colors['darkbg'])
	return new_menu

wirelessmenu = None
menu = Menu()
menu.move_menu(8, 41)

def mainmenu():
	global wlan
	elems = ['Quit']

	try:
		ap = getcurrentssid(wlan).split("-")[1]
		file = open('/sys/class/net/wlan0/address', 'r')
		mac = file.read().strip('\n').replace(":", "")
		file.close()
		if mac == ap:
			elems = ['AP info'] + elems
	except:
		elems = ['Create AP'] + elems

	elems = ["Saved Networks", 'Scan for APs', "Manual Setup"] + elems

	if checkinterfacestatus(wlan):
		elems = ['Disconnect'] + elems

	menu.init(elems, surface)
	menu.draw()

def apinfo():
	global wlan

	try:
		ap = getcurrentssid(wlan).split("-")[1]
		file = open('/sys/class/net/wlan0/address', 'r')
		mac = file.read().strip('\n').replace(":", "")
		file.close()
		if mac == ap:
			font18 = pygame.font.Font(font_path, 18)
			font64 = pygame.font.Font(font_path, 64)

			ssidlabel = "SSID"
			renderedssidlabel = font64.render(ssidlabel, True, colors["lightbg"], colors["darkbg"])
			ssidlabelelement = renderedssidlabel.get_rect()
			ssidlabelelement.right = 300
			ssidlabelelement.top = 34
			surface.blit(renderedssidlabel, ssidlabelelement)

			ssid = getcurrentssid(wlan)
			renderedssid = font18.render(ssid, True, colors["white"], colors["darkbg"])
			ssidelement = renderedssid.get_rect()
			ssidelement.right = 315
			ssidelement.top = 96
			surface.blit(renderedssid, ssidelement)

			enclabel = "Key"
			renderedenclabel = font64.render(enclabel, True, colors["lightbg"], colors["darkbg"])
			enclabelelement = renderedenclabel.get_rect()
			enclabelelement.right = 300
			enclabelelement.top = 114
			surface.blit(renderedenclabel, enclabelelement)

			renderedencp = font18.render(mac, True, colors["white"], colors["darkbg"])
			encpelement = renderedencp.get_rect()
			encpelement.right = 315
			encpelement.top = 180
			surface.blit(renderedencp, encpelement)

			pygame.display.update()
	except:
		text = ":("
		renderedtext = pygame.font.SysFont(None, 72).render(text, True, colors["lightbg"], colors["darkbg"])
		textelement = renderedtext.get_rect()
		textelement.left = 192
		textelement.top = 96
		surface.blit(renderedtext, textelement)
		pygame.display.update()

def create_wireless_menu():
	global wirelessmenu
	wirelessmenu = NetworksMenu()
	wirelessmenu.move_menu(150,40)

def destroy_wireless_menu():
	global wirelessmenu
	wirelessmenu = None

def create_saved_networks_menu():
	global uniq
	global colors
	uniq = getsavednets()
	if len(uniq) < 1:
		text = ":("
		renderedtext = pygame.font.SysFont(None, 72).render(text, True, colors["lightbg"], colors["darkbg"])
		textelement = renderedtext.get_rect()
		textelement.left = 192
		textelement.top = 96
		surface.blit(renderedtext, textelement)
		pygame.display.update()
	else:
		wirelessitems = []
		l = []
		for item in sorted(uniq.iterkeys(), key=lambda x: uniq[x]['Network']['menu']):
			for network, detail in uniq.iteritems():
				if network == item:
					try:
						detail['Network']['Quality']
					except KeyError:
						detail['Network']['Quality'] = "0/1"
					try:
						detail['Network']['Encryption']
					except KeyError:
						detail['Network']['Encryption'] = ""
					ssid = detail['Network']['ESSID']
					ssidconfig = re.escape(ssid)
					try:
						conf = netconfdir+ssidconfig+".conf"
						with open(conf) as f:
							for line in f:
								if "WLAN_ENCRYPTION" in line:
									detail['Network']['Encryption'] = str.strip(line[line.find('WLAN_ENCRYPTION="')
										+len('WLAN_ENCRYPTION="'):line.find('"\n')+len('"\n')].rstrip('"\n'))
								if "WLAN_PASSPHRASE" in line:
									uniq[network]['Network']['Key'] = str.strip(line[line.find('WLAN_PASSPHRASE="')
										+len('WLAN_PASSPHRASE="'):line.find('"\n')+len('"\n')].rstrip('"\n'))
					except:
						conf = netconfdir+ssid+".conf"
						with open(conf) as f:
							for line in f:
								if "WLAN_ENCRYPTION" in line:
									detail['Network']['Encryption'] = str.strip(line[line.find('WLAN_ENCRYPTION="')
										+len('WLAN_ENCRYPTION="'):line.find('"\n')+len('"\n')].rstrip('"\n'))
								if "WLAN_PASSPHRASE" in line:
									uniq[network]['Network']['Key'] = str.strip(line[line.find('WLAN_PASSPHRASE="')
										+len('WLAN_PASSPHRASE="'):line.find('"\n')+len('"\n')].rstrip('"\n'))
									## TODO: fix for 128-bit wep
					menuitem = [ detail['Network']['ESSID'], detail['Network']['Quality'], detail['Network']['Encryption'].upper()]
					l.append(menuitem)
		create_wireless_menu()
		wirelessmenu.init(l, surface)
		wirelessmenu.draw()
if __name__ == "__main__":
	# Persistent variables
	networks = {}
	uniqssids = {}
	active_menu = "main"

	try:
		createpaths()
	except:
		pass ## Can't create directories. Great for debugging on a pc.

	logoBar = LogoBar()

	redraw()
	while True:
		time.sleep(0.01)
		for event in pygame.event.get():
			## GCW-Zero keycodes:
			# A = K_LCTRL
			# B = K_LALT
			# X = K_LSHIFT
			# Y = K_SPACE
			# L = K_TAB
			# R = K_BACKSPACE
			# start = K_RETURN
			# select = K_ESCAPE
			# power up = K_KP0
			# power down = K_PAUSE

			if event.type == QUIT:
				pygame.display.quit()
				sys.exit()

			elif event.type == KEYDOWN:
				if event.key == K_PAUSE: # Power down
					pass
				elif event.key == K_TAB: # Left shoulder button
					pass
				elif event.key == K_BACKSPACE: # Right shoulder button
					pass
				elif event.key == K_KP0:	# Power up
					pass
				elif event.key == K_UP: # Arrow up the menu
					if active_menu == "main":
						menu.draw(-1)
					elif active_menu == "ssid" or active_menu == "saved":
						wirelessmenu.draw(-1)
				elif event.key == K_DOWN: # Arrow down the menu
					if active_menu == "main":
						menu.draw(1)
					elif active_menu == "ssid" or active_menu == "saved":
						wirelessmenu.draw(1)
				elif event.key == K_RIGHT:
					if wirelessmenu is not None and active_menu == "main":
						active_menu = to_menu("ssid")
						redraw()
				elif event.key == K_LALT or event.key == K_LEFT:
					if active_menu == "ssid" or active_menu == "saved":
						destroy_wireless_menu()
						active_menu = to_menu("main")
						del uniq
						redraw()
					elif event.key == K_LALT:
						pygame.display.quit()
						sys.exit()
				elif event.key == K_SPACE:
					if active_menu == "saved":
						if len(str(wirelessmenu.get_selected()[0])) > 16:
							the_ssid = "%s..."%(wirelessmenu.get_selected()[0][:16])
						else:
							the_ssid = wirelessmenu.get_selected()[0]
						confirm = modal("Forget "+the_ssid+"?", query=True)
						if confirm:
							os.remove(netconfdir+re.escape(str(wirelessmenu.get_selected()[0]))+".conf")
						create_saved_networks_menu()
						redraw()
						if len(uniq) < 1:
							destroy_wireless_menu()
							active_menu = to_menu("main")
							redraw()
				elif event.key == K_LCTRL or event.key == K_RETURN:
					# Main menu
					if active_menu == "main":
						if menu.get_selected() == 'Disconnect':
							disconnect(wlan)
							redraw()
						elif menu.get_selected() == 'Scan for APs':
							try:
								getnetworks(wlan)
								uniq = listuniqssids()
							except:
								uniq = {}
								text = ":("
								renderedtext = pygame.font.SysFont(None, 72).render(text, True, colors["lightbg"], colors["darkbg"])
								textelement = renderedtext.get_rect()
								textelement.left = 192
								textelement.top = 96
								surface.blit(renderedtext, textelement)
								pygame.display.update()

							wirelessitems = []
							l = []
							if len(uniq) < 1:
								text = ":("
								renderedtext = pygame.font.SysFont(None, 72).render(text, True, colors["lightbg"], colors["darkbg"])
								textelement = renderedtext.get_rect()
								textelement.left = 192
								textelement.top = 96
								surface.blit(renderedtext, textelement)
								pygame.display.update()
							else:
								for item in sorted(uniq.iterkeys(), key=lambda x: uniq[x]['Network']['menu']):
									for network, detail in uniq.iteritems():
										if network == item:
											try:
												detail['Network']['Quality']
											except KeyError:
												detail['Network']['Quality'] = "0/1"
											try:
												detail['Network']['Encryption']
											except KeyError:
												detail['Network']['Encryption'] = ""

											menuitem = [ detail['Network']['ESSID'], detail['Network']['Quality'], detail['Network']['Encryption']]
											l.append(menuitem)

								create_wireless_menu()
								wirelessmenu.init(l, surface)
								wirelessmenu.draw()

								active_menu = to_menu("ssid")
								redraw()
						elif menu.get_selected() == 'Manual Setup':
							ssid = ''
							encryption = ''
							passphrase = ''
							selected_key = ''
							securitykey = ''

							# Get SSID from the user
							ssid = getSSID()
							if ssid == '':
								pass
							else:
								ssidconfig = re.escape(ssid)
								drawEncryptionType()
								encryption = getEncryptionType()
								displayinputlabel("key")
								displayencryptionhint()
								
								# Get key from the user
								if not encryption == 'None':
									if encryption == "WPA":
										drawkeyboard("qwertyNormal")
										securitykey = getinput("qwertyNormal", "key", ssid)
									elif encryption == "WPA2":
										drawkeyboard("qwertyNormal")
										securitykey = getinput("qwertyNormal", "key", ssid)
									elif encryption == "WEP-40":
										drawkeyboard("wep")
										securitykey = getinput("wep", "key", ssid)
									elif encryption == 'cancel':
										del encryption, ssid, ssidconfig, securitykey
										redraw()
								else:
									encryption = "none"
									redraw()
									writeconfig()
									connect(wlan)
								try:
									encryption
								except NameError:
									pass

						elif menu.get_selected() == 'Saved Networks':
							create_saved_networks_menu()
							try:
								active_menu = to_menu("saved")
								redraw()
							except:
								active_menu = to_menu("main")
							
						elif menu.get_selected() == 'Create AP':
							startap()

						elif menu.get_selected() == 'AP info':
							apinfo()

						elif menu.get_selected() == 'Quit':
							pygame.display.quit()
							sys.exit()

					# SSID menu		
					elif active_menu == "ssid":
						ssid = ""
						for network, detail in uniq.iteritems():
							position = str(wirelessmenu.get_position())
							if str(detail['Network']['menu']) == position:
								if detail['Network']['ESSID'].split("-")[0] == "gcwzero":
									ssid = detail['Network']['ESSID']
									ssidconfig = re.escape(ssid)
									conf = netconfdir+ssidconfig+".conf"
									encryption = "WPA2"
									passphrase = ssid.split("-")[1]
									writeconfig()
									connect(wlan)
								else:
									ssid = detail['Network']['ESSID']
									ssidconfig = re.escape(ssid)
									conf = netconfdir+ssidconfig+".conf"
									encryption = detail['Network']['Encryption']
									if not os.path.exists(conf):
										if encryption == "none":
											passphrase = "none"
											encryption = "none"
											writeconfig()
											connect(wlan)
										elif encryption == "WEP-40" or encryption == "WEP-128":
											passphrase = ''
											selected_key = ''
											securitykey = ''
											displayinputlabel("key")
											drawkeyboard("wep")
											encryption = "wep"
											passphrase = getinput("wep", "key", ssid)
										else:
											passphrase = ''
											selected_key = ''
											securitykey = ''
											displayinputlabel("key")
											drawkeyboard("qwertyNormal")
											passphrase = getinput("qwertyNormal", "key", ssid)
									else:
										connect(wlan)
								break

					# Saved Networks menu
					elif active_menu == "saved":
						ssid = ''
						for network, detail in uniq.iteritems():
							position = str(wirelessmenu.get_position()+1)
							if str(detail['Network']['menu']) == position:
								encryption = detail['Network']['Encryption']
								ssid = str(detail['Network']['ESSID'])
								ssidconfig = re.escape(ssid)
								shutil.copy2(netconfdir+ssidconfig+".conf", sysconfdir+"config-"+wlan+".conf")
								passphrase = detail['Network']['Key']
								connect(wlan)
								break

				elif event.key == K_ESCAPE:
					if active_menu == "ssid": # Allow us to edit the existing key
						ssid = ""
						for network, detail in uniq.iteritems():
							position = str(wirelessmenu.get_position())
							if str(detail['Network']['menu']) == position:
								ssid = network
								encryption = detail['Network']['Encryption']
								if detail['Network']['Encryption'] == "none":
									pass
								elif detail['Network']['Encryption'] == "wep":
									passphrase = ''
									selected_key = ''
									securitykey = ''
									displayinputlabel("key")
									drawkeyboard("wep")
									getinput("wep", "key", ssid)
								else:
									passphrase = ''
									selected_key = ''
									securitykey = ''
									displayinputlabel("key")
									drawkeyboard("qwertyNormal")
									getinput("qwertyNormal", "key", ssid)

					if active_menu == "saved": # Allow us to edit the existing key
						ssid = ''

						for network, detail in uniq.iteritems():
							position = str(wirelessmenu.get_position()+1)
							if str(detail['Network']['menu']) == position:
								ssid = network
								passphrase = uniq[network]['Network']['Key']
								encryption = uniq[network]['Network']['Encryption'].upper()
								if uniq[network]['Network']['Encryption'] == "none":
									pass
								elif uniq[network]['Network']['Encryption'] == "wep":
									passphrase = ''
									selected_key = ''
									securitykey = ''
									encryption = "WEP-40"
									displayinputlabel("key")
									drawkeyboard("wep")
									getinput("wep", "key", ssid)
								else:
									passphrase = ''
									selected_key = ''
									securitykey = ''
									displayinputlabel("key")
									drawkeyboard("qwertyNormal")
									getinput("qwertyNormal", "key", ssid)


		pygame.display.update()
