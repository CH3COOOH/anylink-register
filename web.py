import re
import json
import sqlite3
import time
import os
import sys
import random
import string

import pyotp
from websocket_server import WebsocketServer
from azlib import pr

LEN_IV = 16
STR_SUCCESS = '''Thank you for your registration.<br>
If you do not know how to use it, please read this: <br>
For mobile devices: <a href="https://henchat.net/%e6%80%9d%e7%a7%91ssl%e8%99%9a%e6%8b%9f%e4%b8%93%e7%94%a8%e7%ba%bfanyconnect%e5%ae%a2%e6%88%b7%e7%ab%af%e9%85%8d%e7%bd%ae%ef%bc%88ios%e7%af%87%ef%bc%89/">CLICK ME</a><br>
For PC: <a href="https://henchat.net/%e6%80%9d%e7%a7%91ssl%e8%99%9a%e6%8b%9f%e4%b8%93%e7%94%a8%e7%ba%bfanyconnect%e5%ae%a2%e6%88%b7%e7%ab%af%e9%85%8d%e7%bd%ae%ef%bc%88pc%e7%af%87%ef%bc%89/">CLICK ME</a><br>
'''

class Util:
	def isKeywordsIn(self, key_list, text):
		for k in key_list:
			if k in text:
				return True
		return False

	def check_msg(self, text):
		if len(text) > 128 or self.isKeywordsIn('*;()', text):
			return -1
		try:
			getInfo = eval(text)
		except:
			return -1
		if type(getInfo) != list:
			return -1
		if len(getInfo) != 4:
			return -1
		return getInfo

	def check_input_info(self, inputList):
		## [user, passwd, email]
		if len(inputList[0]) < 5:
			print('Wrong username.')
			return False
		if len(inputList[1]) < 8:
			print('Wrong password.')
			return False
		if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", inputList[2]) == None:
			print('Wrong mail.')
			return False
		return True

class DBOP:
	def __init__(self, isDemo, iv_path, db_path=None):
		self.iv_path = iv_path
		self.ivs = self.load_iv()
		self.db_path = None
		if isDemo == False:
			self.db_path = db_path
		self.demo_mode = 	isDemo

	def load_iv(self):
		with open(self.iv_path, 'r') as o:
			return json.load(o)['iv']
	
	def add_iv(self, iv_new):
		self.ivs.append(iv_new)
		return 0

	def update_iv(self):
		with open(self.iv_path, 'w') as o:
			json.dump({'iv': self.ivs}, o)
		return 0
	
	def get_ivs(self):
		return self.ivs

	def use_iv(self, iv):
		print(iv)
		print(self.ivs)
		if iv in self.ivs:
			del self.ivs[self.ivs.index(iv)]
			self.update_iv()
			return 0
		else:
			return -1

	def update_db(self, username, passwd, email):
		sTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
		if self.demo_mode == False:
			con = sqlite3.connect(self.db_path)
			cur = con.cursor()
			## Is username used
			if len(list(cur.execute('SELECT * FROM User WHERE Username=\'%s\'' % username))) > 0:
				return -1
			lastline = list(cur.execute('SELECT * FROM User ORDER BY Id DESC LIMIT 1'))
			if len(lastline) == 0:
				newid = 0
			else:
				newid = lastline[-1][0] + 1
			# sql = 'INSERT INTO User VALUES (%d, \'%s\', \'%s\', \'%s\', \'%s\', \'%s\', 1, \'[\"ops\"]\', 1, 0, \'%s\', \'%s\', \'\')'\
				# % (newid, username, username, email, passwd, pyotp.random_base32(), sTime, sTime)
			sql = f"INSERT INTO User VALUES ({newid}, \'{username}\', \'{username}\', \'{email}\', \'{passwd}\', \'{pyotp.random_base32()}\', 1, \'[\"ops\"]\', 1, 0, \'{sTime}\', \'{sTime}\', \'\')"
			cur.execute(sql)
			con.commit()
			con.close()
		else:
			sql = f"INSERT INTO User VALUES (0, \'{username}\', \'{username}\', \'{email}\', \'{passwd}\', \'{pyotp.random_base32()}\', 1, \'[\"ops\"]\', 1, 0, \'{sTime}\', \'{sTime}\', \'\')"
		print(sql)
		return 0

class Srv:
	def __init__(self, host, port, isDemo, iv_path, superuser, log_level, db_path=None):
		self.host = host
		self.port = port
		self.admin = superuser
		self.ut = Util()
		self.db = DBOP(isDemo, iv_path, db_path)
		self.log = pr.Log(show_level=log_level)

	def _close_session(self, client):
		client["handler"].send_close(1000, b'')

	def _msgReceived(self, client, server, msg):
		self.log.print(msg, level=0)
		getInfo = self.ut.check_msg(msg)
		if getInfo == -1:
			self._close_session(client)
			return -1
		username, passwd, email, iv = getInfo
		## Superuser Mode
		## -----------------
		if username == self.admin[0] and passwd == self.admin[1]:
			self.log.print("Superuser login.", level=1)
			if iv == '0':
				server.send_message(client, '*** AVAILABLE IVC ***<br>' + '<br>'.join(self.db.get_ivs()))
				return 0
			if iv == '1':
				iv_gen = ''.join(random.sample(string.ascii_letters + string.digits, LEN_IV))
				self.db.add_iv(iv_gen)
				self.db.update_iv()
				server.send_message(client, iv_gen)
				return 0
			if len(iv) != LEN_IV:
				server.send_message(client, "Invalid IVC!<br>")
				self.log.print("Attempt of adding an invalid IVC.", level=1)
				return -1
			if iv in self.db.get_ivs():
				server.send_message(client, "Same IVC exist.<br>")
				return -1
			self.db.add_iv(iv)
			self.db.update_iv()
			server.send_message(client, "OK<br>")
			self.log.print(f"New IV added: {iv}", level=1)
			return 1
		## -----------------
		if self.ut.check_input_info(getInfo) == False:
			self._close_session(client)
			self.log.print("Attempt of wrong input from a wild user.", level=2)
			return -1
		if self.db.use_iv(iv) == -1:
			self._close_session(client)
			self.log.print("Attempt of an invalid IVC from a wild user.", level=2)
			return -1

		## Everything is OK, create new user
		if self.db.update_db(username, passwd, email) == 0:
			server.send_message(client, STR_SUCCESS)
			self.log.print("New user added.", level=1)
		else:
			server.send_message(client, "Maybe the username is used... Please try another one.<br>")
		self._close_session(client)
		return 0

	def start(self):
		server = WebsocketServer(port=self.port, host=self.host)
		server.set_fn_message_received(self._msgReceived)
		self.log.print(f"Listening on {self.host}:{self.port}...", 1)
		server.run_forever()

if __name__ == '__main__':
	with open(sys.argv[1], 'r') as o:
		conf = json.load(o)
	if conf['db_path'] == None:
		print('*** RUNNING IN DEMO MODE ***')
		s = Srv(conf['srv_host'], conf['srv_port'], True, conf['iv_path'], conf['admin'], conf['log_level'])
	else:
		s = Srv(conf['srv_host'], conf['srv_port'], False, conf['iv_path'], conf['admin'], conf['log_level'], db_path=conf['db_path'])
	s.start()
